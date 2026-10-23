import glob
import html
import json
import os
import re
import select
import struct
import subprocess
import sys
import time
import zipfile

from PySide6.QtCore import QEvent, QRect, QSize, QRect, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QCursor, QIcon,
                           QPainter, QPalette, QPen, QPixmap, QKeySequence)
from PySide6.QtWidgets import (QApplication, QColorDialog, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QSplitter, QStyle, QStyledItemDelegate,
                               QListWidget, QListWidgetItem, QMenuBar,
                               QPushButton, QVBoxLayout, QWidget, QSizePolicy, QMenu)

CONFIG_DIR = os.path.expanduser("~/.config/launcher")
IMG_DIR = os.path.join(CONFIG_DIR, "img")
PROGRESS_FILE = os.path.join(CONFIG_DIR, "worker_progress.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
CUSTOM_COLORS_FILE = os.path.join(CONFIG_DIR, "custom_colors.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "worker.lock")

_script_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(_script_dir, "roms"), exist_ok=True)
os.makedirs(os.path.join(_script_dir, "bios"), exist_ok=True)

DEFAULT_SETTINGS = {
    "rom_dir": os.path.join(_script_dir, "roms"), 
    "favorites": [], 
    "language": "it"
}

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

DOT = 24
COLOR_NEUTRAL = "#ffffff"
COLOR_WORKER_LABEL = "#ffd60a"
COLOR_ACCENT = "#0089cf"

SHORT_PLATFORM_NAMES = {
    "atari - 2600": "Atari 2600",
    "commodore - 64": "Commodore 64",
    "dos": "DOS",
    "mame": "Arcade (MAME)",
    "nintendo - game boy": "Game Boy",
    "nintendo - game boy advance": "Game Boy Advance",
    "nintendo - game boy color": "Game Boy Color",
    "nintendo - gamecube": "GameCube",
    "nintendo - nintendo 64": "Nintendo 64",
    "nintendo - nintendo entertainment system": "Nintendo (NES)",
    "nintendo - super nintendo entertainment system": "Super Nintendo (SNES)",
    "nintendo - wii": "Nintendo Wii",
    "sega - master system - mark iii": "Sega Master System",
    "sega - mega drive - genesis": "Sega Mega Drive",
    "sony - playstation": "PlayStation",
    "sony - playstation 1": "PlayStation",
    "sony - playstation 2": "PlayStation 2",
    "xbox": "Xbox",
    "microsoft - xbox": "Xbox"
}

PLATFORM_COLORS = {
    "dos": "#9c6b3f",
    "mame": "#dc8add",
    "nintendo - game boy": "#8b956d",
    "nintendo - game boy advance": "#582092",
    "nintendo - game boy color": "#c8206d",
    "nintendo - gamecube": "#ff375f",
    "nintendo - nintendo 64": "#2ec27e",
    "nintendo - nintendo entertainment system": "#ff375f",
    "nintendo - super nintendo entertainment system": "#e5a50a",
    "nintendo - wii": "#94dee3",
    "sega - master system - mark iii": "#229ED9",
    "sega - mega drive - genesis": "#229ED9",
    "sony - playstation": "#a9b2bd",
    "sony - playstation 1": "#a9b2bd",
    "sony - playstation 2": "#1a75ff",
    "xbox": "#9bf00b",
    "microsoft - xbox": "#9bf00b"
}

SUB_COLOR = {}

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_custom_colors(custom_colors):
    try:
        with open(CUSTOM_COLORS_FILE, "w", encoding="utf-8") as f:
            json.dump(custom_colors, f, indent=2)
    except Exception:
        pass

_custom_colors = load_json(CUSTOM_COLORS_FILE)
if isinstance(_custom_colors, dict):
    for _k, _v in _custom_colors.items():
        PLATFORM_COLORS[_k] = _v
        SUB_COLOR[_k] = _v

def _norm_sub(raw):
    return raw.replace("_-_", " - ").replace("_", " ").strip().lower() if raw else ""

def get_color_for_brand(subfolder):
    if not subfolder:
        return COLOR_ACCENT
    if subfolder in SUB_COLOR:
        return SUB_COLOR[subfolder]
    norm = _norm_sub(subfolder)
    return PLATFORM_COLORS.get(norm, COLOR_ACCENT)

AUTHOR, YEAR = "Jonathan Sanfilippo", "2026"
STATO = "#2c2c35"
FONDO, PANNELLO, CERCA = "#17171b", "#17171b", "#252428"
TASTO, SCELTO, TESTO, GRIGIO = "#2c2c35", "#424250", "#e0e0e0", "#9e9e9e"
IN_ONDA = "#3b2f4f"

def make_dot(color, size=16):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    r = size * 0.35
    p.drawEllipse(size / 2.0 - r, size / 2.0 - r, 2 * r, 2 * r)
    p.end()
    return QIcon(pm)

STYLE = f"""
QWidget {{ background: {FONDO}; color: {TESTO}; }}
QLabel {{ background: transparent; }}
QWidget#side, QWidget#folders {{ background: {PANNELLO}; }}
QMenuBar {{ background: {PANNELLO}; color: #ffffff; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; }}
QMenuBar::item:selected {{ background: {CERCA}; }}
QMenu {{ background: {CERCA}; color: {TESTO}; border: 1px solid {SCELTO}; }}
QMenu::item {{ padding: 5px 24px; }}
QMenu::item:selected {{ background: {IN_ONDA}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {SCELTO}; margin: 4px 0; }}
QLineEdit {{ background: {CERCA}; color: {TESTO}; border: none; border-radius: 18px;
            padding: 0 14px 0 4px; min-height: 36px; selection-background-color: {IN_ONDA}; }}
QListWidget {{ background: {PANNELLO}; border: none; outline: 0; }}
QListWidget[gamepad="true"] {{ border: 1px solid {COLOR_ACCENT}; }}
QListWidget::item:selected, QListWidget::item:selected:!active
    {{ background: {CERCA}; color: #ffffff; }}
QPushButton {{ background: {TASTO}; color: {TESTO}; border: none; border-radius: 6px;
              padding: 8px; }}
QPushButton:hover {{ background: {SCELTO}; }}
QSplitter::handle {{ background: {SCELTO}; }}
QWidget#status {{ background: {STATO}; min-height: 28px; max-height: 28px; }}
QWidget#status QLabel {{ color: #ffffff; line-height: 28px; }}
"""

def lens_icon():
    pm = QPixmap(20, 20)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(GRIGIO), 2)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawEllipse(3, 3, 10, 10)
    p.drawLine(11, 11, 16, 16)
    p.end()
    return QIcon(pm)

ROW_H = 46

class GameDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_H)

    def paint(self, painter, option, index):
        painter.save()
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            painter.fillRect(r, QColor(CERCA))

        x = r.left() + 10
        w = r.width() - 20

        # Titolo del gioco (in alto)
        name = painter.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight, w)
        painter.setPen(QColor("#ffffff" if selected else TESTO))
        painter.drawText(QRect(x, r.top() + 5, w, 16), Qt.AlignLeft | Qt.AlignVCenter, name)

        # Configurazione font per la seconda riga (Anno + Dot + Piattaforma)
        f = painter.font()
        if f.pointSizeF() > 0:
            f.setPointSizeF(max(f.pointSizeF() - 1.5, 8))
            painter.setFont(f)

        fm = painter.fontMetrics()
        cur_x = x

        year_str = index.data(Qt.UserRole + 1) or ""
        dot_color = index.data(Qt.UserRole + 2) or COLOR_ACCENT
        subfolder_str = index.data(Qt.UserRole + 5) or ""

        # 1. Anno in BIANCO
        if year_str and year_str != "?":
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRect(cur_x, r.top() + 24, w, 16), Qt.AlignLeft | Qt.AlignVCenter, year_str)
            cur_x += fm.horizontalAdvance(year_str) + 6

        # 2. Pallino colorato della piattaforma
        if subfolder_str:
            dot_size = 8
            dot_y = r.top() + 24 + (16 - dot_size) // 2
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(dot_color))
            painter.drawEllipse(cur_x, dot_y, dot_size, dot_size)
            cur_x += dot_size + 6

            # 3. Nome piattaforma col suo colore
            painter.setPen(QColor(dot_color))
            painter.drawText(QRect(cur_x, r.top() + 24, w, 16), Qt.AlignLeft | Qt.AlignVCenter, subfolder_str)

        painter.restore()

class FolderDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 34)

    def paint(self, painter, option, index):
        painter.save()
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            painter.fillRect(r, QColor(CERCA))
            
        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            icon.paint(painter, QRect(r.left() + 4, r.top() + (r.height() - DOT) // 2, DOT, DOT))
            
        x = r.left() + DOT + 10
        w = r.width() - DOT - 18
        
        name = painter.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight, w)
        painter.setPen(QColor("#ffffff" if selected else TESTO))
        painter.drawText(QRect(x, r.top(), w, r.height()), Qt.AlignLeft | Qt.AlignVCenter, name)
        
        painter.restore()

class SearchBox(QLineEdit):
    def __init__(self, placeholder="Search"):
        super().__init__()
        self.setPlaceholderText(placeholder)
        pal = self.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(GRIGIO))
        self.setPalette(pal)
        self.addAction(lens_icon(), QLineEdit.LeadingPosition)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clear()
        else:
            super().keyPressEvent(e)

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

def clean_platform_display(sub):
    if not sub: 
        return ""
    key = sub.replace("_-_", " - ").replace("_", " ").strip().lower()
    if key in SHORT_PLATFORM_NAMES:
        return SHORT_PLATFORM_NAMES[key]
    return sub.replace("_-_", " ").replace("-", " ").replace("_", " ")

def clean_game_title(raw_title):
    if not raw_title:
        return ""
    # Rimuove codici parentesi come (Europe), (En,Fr,De), (Rev 1), [!], (v1.0), ecc.
    t = re.sub(r'[\(\[\<].*?[\)\]\>]', '', raw_title)
    return t.strip() or raw_title

def list_roms_recursive(rom_dir):
    results = []
    if not rom_dir or not os.path.isdir(rom_dir):
        return results
    valid_exts = ('.sms', '.bin', '.sfc', '.smc', '.md', '.gen', '.nes', '.gb', '.gba', '.z64', '.n64', '.iso', '.rvz', '.chd', '.zip', '.cue', '.img')

    for libretro_sys in os.listdir(rom_dir):
        sys_path = os.path.join(rom_dir, libretro_sys)
        if not os.path.isdir(sys_path):
            continue

        target_scan_path = sys_path
        if ("playstation" in libretro_sys.lower() or "dos" in libretro_sys.lower()) and os.path.isdir(os.path.join(sys_path, "roms")):
            target_scan_path = os.path.join(sys_path, "roms")

        for base_name in os.listdir(target_scan_path):
            game_dir = os.path.join(target_scan_path, base_name)
            if not os.path.isdir(game_dir):
                if base_name.lower().endswith(valid_exts):
                    f = base_name
                    base_game_name = os.path.splitext(f)[0]
                    subfolder = clean_platform_display(libretro_sys)
                    _c = PLATFORM_COLORS.get(_norm_sub(libretro_sys))
                    if _c and subfolder and subfolder not in SUB_COLOR:
                        SUB_COLOR[subfolder] = _c
                    results.append((base_game_name, os.path.join(target_scan_path, f), subfolder, target_scan_path))
                continue

            files_in_game = os.listdir(game_dir)
            valid_files = [f for f in files_in_game if f.lower().endswith(valid_exts)]
            if not valid_files:
                continue

            cue_files = [f for f in valid_files if f.lower().endswith('.cue')]
            if cue_files:
                chosen_file = cue_files[0]
            else:
                chosen_file = valid_files[0]

            rom_path = os.path.join(game_dir, chosen_file)
            subfolder = clean_platform_display(libretro_sys)
            _c = PLATFORM_COLORS.get(_norm_sub(libretro_sys))
            if _c and subfolder and subfolder not in SUB_COLOR:
                SUB_COLOR[subfolder] = _c

            results.append((base_name, rom_path, subfolder, game_dir))

    return sorted(results, key=lambda x: x[0].lower())

class EmulatorRunnerThread(QThread):
    finished = Signal()
    def __init__(self, exec_command):
        super().__init__()
        self.exec_command = exec_command

    def run(self):
        try:
            subprocess.run(self.exec_command)
        except Exception as e:
            print(f"Errore avvio emulatore: {e}")
        self.finished.emit()

class GamepadThread(QThread):
    up_pressed = Signal()
    down_pressed = Signal()
    left_pressed = Signal()
    right_pressed = Signal()
    a_pressed = Signal()
    b_pressed = Signal()

    def __init__(self):
        super().__init__()
        self.running = True
        self.enabled = True

    def run(self):
        while self.running:
            js_devices = sorted(glob.glob("/dev/input/js*"))
            if not js_devices:
                self.msleep(1000)
                continue
            fd = None
            try:
                fd = os.open(js_devices[0], os.O_RDONLY | os.O_NONBLOCK)
            except Exception:
                self.msleep(1000)
                continue

            axis = {}
            active_dir = None
            next_repeat = 0

            while self.running:
                r, _, _ = select.select([fd], [], [], 0.02)
                if r:
                    try:
                        data = os.read(fd, 8)
                    except Exception:
                        break
                    if len(data) == 8:
                        t, val, ev_type, num = struct.unpack("IhBB", data)
                        ev_type &= ~0x80
                        if self.enabled:
                            if ev_type == 1 and val == 1:
                                if num == 0: self.a_pressed.emit()
                                elif num == 1: self.b_pressed.emit()
                            elif ev_type == 2:
                                axis[num] = val

                if not self.enabled:
                    self.msleep(20)
                    continue

                y_val = axis.get(1, 0)
                if abs(y_val) < 15000: y_val = axis.get(7, 0)
                x_val = axis.get(0, 0)
                if abs(x_val) < 15000: x_val = axis.get(6, 0)

                cur_dir = None
                if y_val < -15000: cur_dir = "UP"
                elif y_val > 15000: cur_dir = "DOWN"
                elif x_val < -15000: cur_dir = "LEFT"
                elif x_val > 15000: cur_dir = "RIGHT"

                now = time.time()
                if cur_dir != active_dir:
                    active_dir = cur_dir
                    if active_dir:
                        self.emit_dir(active_dir)
                        next_repeat = now + 0.280
                elif active_dir and now >= next_repeat:
                    self.emit_dir(active_dir)
                    next_repeat = now + 0.090
                self.msleep(10)

            if fd is not None:
                try: os.close(fd)
                except Exception: pass

    def emit_dir(self, direction):
        if direction == "UP": self.up_pressed.emit()
        elif direction == "DOWN": self.down_pressed.emit()
        elif direction == "LEFT": self.left_pressed.emit()
        elif direction == "RIGHT": self.right_pressed.emit()

class SMSLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Retro Hub Launcher")
        self.resize(1100, 660)

        self.settings = dict(DEFAULT_SETTINGS)
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                self.settings.update(json.load(f))
        except Exception:
            pass

        if not self.settings.get("rom_dir") or not os.path.isdir(self.settings["rom_dir"]):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            local_roms = os.path.join(script_dir, "roms")
            if os.path.isdir(local_roms):
                self.settings["rom_dir"] = local_roms
                save_settings(self.settings)

        self.start_background_worker()

        self.roms_data = list_roms_recursive(self.settings["rom_dir"])
        self.all_item_cache = {}
        self.meta = {}
        self.emu_thread = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.fill_list)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self.poll_background_updates)
        self.poll_timer.start()

        self.search = SearchBox("Cerca gioco...")
        self.search.textChanged.connect(self.on_search_changed)

        self.list = QListWidget()
        self.list.setIconSize(QSize(DOT, DOT))
        self.list.setItemDelegate(GameDelegate(self.list))
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.list.viewport().setMouseTracking(True)
        self.list.viewport().installEventFilter(self)

        self.items = {}
        self.list.currentItemChanged.connect(self.show_game)
        self.list.itemActivated.connect(lambda _i: self.launch())

        left = QVBoxLayout()
        left.setContentsMargins(10, 10, 10, 10)
        left.addWidget(self.search)
        left.addWidget(self.list)
        side = QWidget()
        side.setObjectName("side")
        side.setLayout(left)

        self.cover = QLabel("Caricamento...")
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setMinimumSize(250, 300)
        self.cover.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.info = QLabel("Pronto per giocare...")
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.btn = QPushButton("Avvia")
        self.btn.clicked.connect(self.launch)

        self.fav_btn = QPushButton("Preferito")
        self.fav_btn.clicked.connect(self.toggle_favorite)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn, 3)
        btn_layout.addWidget(self.fav_btn, 1)

        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(14, 10, 14, 10)
        center_layout.addWidget(self.cover, 3)
        center_layout.addWidget(self.info, 1)
        center_layout.addLayout(btn_layout)

        center_container = QWidget()
        center_container.setLayout(center_layout)

        self.library_header_lbl = QLabel("<b>Piattaforme</b>")
        self.folders_list = QListWidget()
        self.folders_list.setIconSize(QSize(DOT, DOT))
        self.folders_list.setItemDelegate(FolderDelegate(self.folders_list))
        self.folders_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.folders_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.folders_list.viewport().setMouseTracking(True)
        self.folders_list.viewport().installEventFilter(self)

        self.folders_list.currentItemChanged.connect(lambda *_: self.fill_list())

        folders_layout = QVBoxLayout()
        folders_layout.setContentsMargins(10, 10, 10, 10)
        folders_layout.addWidget(self.library_header_lbl)
        folders_layout.addWidget(self.folders_list)
        folders_widget = QWidget()
        folders_widget.setObjectName("folders")
        folders_widget.setLayout(folders_layout)

        splitter_main = QSplitter(Qt.Horizontal)
        splitter_main.addWidget(side)
        splitter_main.addWidget(center_container)
        splitter_main.addWidget(folders_widget)
        splitter_main.setSizes([300, 500, 300])

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(splitter_main)

        self.menu_bar_widget = self.build_menu()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setMenuBar(self.menu_bar_widget)
        lay.setSpacing(0)
        lay.addLayout(body)

        status = QWidget()
        status.setObjectName("status")
        sl = QHBoxLayout(status)
        sl.setContentsMargins(12, 4, 12, 4)
        self.count_lbl = QLabel("Pronto")
        self.prog_lbl = QLabel("Worker inattivo")
        sl.addWidget(self.count_lbl)
        sl.addSpacing(18)
        sl.addWidget(self.prog_lbl)
        sl.addStretch(1)
        self.copy_lbl = QLabel("\u00a9 %s %s \u00b7 MIT license" % (YEAR, AUTHOR))
        self.copy_lbl.setStyleSheet("color: #ffffff;")
        sl.addWidget(self.copy_lbl)
        lay.addWidget(status)

        self.setStyleSheet(STYLE)
        self.build_item_cache()
        self.update_folders_list()
        self.fill_list()

        QApplication.instance().installEventFilter(self)

        self.gamepad = GamepadThread()
        self.gamepad.up_pressed.connect(self.on_pad_up)
        self.gamepad.down_pressed.connect(self.on_pad_down)
        self.gamepad.left_pressed.connect(self.on_pad_left)
        self.gamepad.right_pressed.connect(self.on_pad_right)
        self.gamepad.a_pressed.connect(self.launch)
        self.gamepad.b_pressed.connect(self.toggle_favorite)
        self.gamepad.start()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            self.clear_gamepad_focus()

        if event.type() == QEvent.MouseMove and obj in (self.list.viewport(), self.folders_list.viewport()):
            widget = self.list if obj == self.list.viewport() else self.folders_list
            if widget.itemAt(event.pos()) is not None:
                obj.setCursor(Qt.PointingHandCursor)
            else:
                obj.setCursor(Qt.ArrowCursor)

        return super().eventFilter(obj, event)

    def set_gamepad_focus(self, target_widget):
        self.list.setProperty("gamepad", "true" if target_widget == self.list else "false")
        self.folders_list.setProperty("gamepad", "true" if target_widget == self.folders_list else "false")
        self.list.style().unpolish(self.list)
        self.list.style().polish(self.list)
        self.folders_list.style().unpolish(self.folders_list)
        self.folders_list.style().polish(self.folders_list)

    def clear_gamepad_focus(self):
        self.list.setProperty("gamepad", "false")
        self.folders_list.setProperty("gamepad", "false")
        self.list.style().unpolish(self.list)
        self.list.style().polish(self.list)
        self.folders_list.style().unpolish(self.folders_list)
        self.folders_list.style().polish(self.folders_list)

    def on_pad_up(self):
        if not self.isVisible(): return
        w = self.focusWidget()
        if w == self.folders_list:
            r = self.folders_list.currentRow()
            if r > 0: self.folders_list.setCurrentRow(r - 1)
            target = self.folders_list
        else:
            r = self.list.currentRow()
            if r > 0: self.list.setCurrentRow(r - 1)
            target = self.list
        self.set_gamepad_focus(target)

    def on_pad_down(self):
        if not self.isVisible(): return
        w = self.focusWidget()
        if w == self.folders_list:
            r = self.folders_list.currentRow()
            if r < self.folders_list.count() - 1: self.folders_list.setCurrentRow(r + 1)
            target = self.folders_list
        else:
            r = self.list.currentRow()
            if r < self.list.count() - 1: self.list.setCurrentRow(r + 1)
            target = self.list
        self.set_gamepad_focus(target)

    def on_pad_left(self):
        if not self.isVisible(): return
        self.folders_list.setFocus()
        self.set_gamepad_focus(self.folders_list)

    def on_pad_right(self):
        if not self.isVisible(): return
        self.list.setFocus()
        self.set_gamepad_focus(self.list)

    def start_background_worker(self):
        worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py")
        if os.path.exists(worker_script) and not os.path.exists(LOCK_FILE):
            try:
                subprocess.Popen([sys.executable, worker_script])
            except Exception:
                pass

    def poll_background_updates(self):
        current_roms = list_roms_recursive(self.settings["rom_dir"])
        if current_roms != self.roms_data:
            self.roms_data = current_roms
            self.build_item_cache()
            self.update_folders_list()
            self.fill_list()

        prog_data = load_json(PROGRESS_FILE)
        is_locked = os.path.exists(LOCK_FILE)
        if prog_data:
            task = prog_data.get("task", "Elaborazione...")
            current = prog_data.get("current", 0)
            total = prog_data.get("total", 0)
            if task == "Completato" and not is_locked:
                self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> Pronto (Completato)")
            else:
                pct = int((current / total) * 100) if total > 0 else 0
                self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> {task} ({current}/{total} - {pct}%)")
        else:
            txt = "avvio in corso..." if is_locked else "inattivo o completato"
            self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> {txt}")

    def build_item_cache(self):
        self.all_item_cache = {}
        for item_tuple in self.roms_data:
            name, path, subfolder, game_dir = item_tuple
            meta_file = os.path.join(game_dir, "metadata.json")
            m = load_json(meta_file)
            
            # Pulisce il titolo del gioco per la visualizzazione nella lista
            raw_title = m.get("title", name)
            desc = clean_game_title(raw_title)
            year_val = str(m.get("year", "?")) if m.get("year") else "?"
            
            unique_key = f"{subfolder}_{name}"
            self.meta[unique_key] = m
            self.all_item_cache[unique_key] = {
                "name": name,
                "desc": desc,
                "year": year_val,
                "path": path,
                "subfolder": subfolder,
                "game_dir": game_dir
            }

    def update_folders_list(self):
        curr_item = self.folders_list.currentItem()
        curr_data = curr_item.data(Qt.UserRole) if curr_item else "all"

        self.folders_list.blockSignals(True)
        self.folders_list.clear()

        total_count = len(self.roms_data)
        favs = set(self.settings.get("favorites", []))
        fav_count = sum(1 for item in self.roms_data if f"{item[2]}_{item[0]}" in favs or item[0] in favs)

        it_all = QListWidgetItem(f"Tutti i giochi ({total_count})")
        it_all.setIcon(make_dot(COLOR_NEUTRAL))
        it_all.setData(Qt.UserRole, "all")
        self.folders_list.addItem(it_all)

        it_fav = QListWidgetItem(f"Preferiti ({fav_count})")
        it_fav.setIcon(make_dot(COLOR_NEUTRAL))
        it_fav.setData(Qt.UserRole, "favorites")
        self.folders_list.addItem(it_fav)

        subfolders = sorted(list(set(sub for _, _, sub, _ in self.roms_data if sub)))
        for sub in subfolders:
            count = sum(1 for _, _, s, _ in self.roms_data if s == sub)
            brand_color = get_color_for_brand(sub)
            it_sub = QListWidgetItem(f"{sub} ({count})")
            it_sub.setIcon(make_dot(brand_color))
            it_sub.setData(Qt.UserRole, f"sub_{sub}")
            self.folders_list.addItem(it_sub)

        for i in range(self.folders_list.count()):
            item = self.folders_list.item(i)
            if item.data(Qt.UserRole) == curr_data:
                self.folders_list.setCurrentItem(item)
                break
        if not self.folders_list.currentItem() and self.folders_list.count() > 0:
            self.folders_list.setCurrentRow(0)

        self.folders_list.blockSignals(False)

    def reload_roms(self):
        self.start_background_worker()
        self.roms_data = list_roms_recursive(self.settings["rom_dir"])
        self.build_item_cache()
        self.update_folders_list()
        self.fill_list()

    def build_menu(self):
        bar = QMenuBar()
        file_menu = bar.addMenu("File")
        
        a_refresh = QAction("Aggiorna ROM", self)
        a_refresh.setShortcut(QKeySequence.Refresh)
        a_refresh.triggered.connect(self.reload_roms)
        file_menu.addAction(a_refresh)

        file_menu.addSeparator()
        a_quit = QAction("Esci", self)
        a_quit.triggered.connect(self.close)
        file_menu.addAction(a_quit)

        sett = bar.addMenu("Impostazioni")
        a_rom = QAction("Cartella ROM...", self)
        a_rom.triggered.connect(self.set_folder)
        sett.addAction(a_rom)

        return bar

    def set_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Seleziona cartella ROM")
        if d:
            self.settings["rom_dir"] = d
            save_settings(self.settings)
            self.reload_roms()

    def toggle_favorite(self):
        if not self.isVisible(): return
        unique_key = self.current_name()
        if not unique_key: return
        favs = self.settings.setdefault("favorites", [])
        if unique_key in favs: favs.remove(unique_key)
        else: favs.append(unique_key)
        save_settings(self.settings)
        self.update_favorite_button(unique_key)
        self.update_folders_list()

    def update_favorite_button(self, unique_key):
        favs = self.settings.get("favorites", [])
        star = "★" if unique_key in favs else "☆"
        self.fav_btn.setText(f"{star} Preferito")

    def on_search_changed(self):
        self.search_timer.stop()
        self.search_timer.start()

    def fill_list(self):
        q = self.search.text().lower()
        curr_item = self.folders_list.currentItem()
        curr_data = curr_item.data(Qt.UserRole) if curr_item else "all"
        favs = set(self.settings.get("favorites", []))

        self.list.setUpdatesEnabled(False)
        self.list.blockSignals(True)
        self.list.clear()
        self.items = {}

        if not self.all_item_cache and self.roms_data:
            self.build_item_cache()

        filtered = []
        q_tokens = q.split() if q else []

        for item_tuple in self.roms_data:
            name, _, subfolder, _ = item_tuple
            unique_key = f"{subfolder}_{name}"
            
            if curr_data == "favorites" and unique_key not in favs and name not in favs:
                continue
            elif curr_data and curr_data.startswith("sub_"):
                target_sub = curr_data[4:]
                if subfolder != target_sub:
                    continue

            if q_tokens:
                m = self.meta.get(unique_key, {})
                title = m.get("title", name).lower()
                hay = f"{title} {name} {subfolder}"
                if not all(t in hay for t in q_tokens):
                    continue
            filtered.append(unique_key)

        filtered.sort(key=lambda uk: self.meta.get(uk, {}).get("title", uk).lower())

        for unique_key in filtered:
            data = self.all_item_cache.get(unique_key)
            if data:
                subfolder = data.get("subfolder", "")
                dot_color = get_color_for_brand(subfolder)
                
                it = QListWidgetItem(data["desc"])
                it.setData(Qt.UserRole, unique_key)
                it.setData(Qt.UserRole + 1, data["year"])
                it.setData(Qt.UserRole + 2, dot_color)
                it.setData(Qt.UserRole + 5, subfolder)
                
                self.items[unique_key] = it
                self.list.addItem(it)

        self.list.blockSignals(False)
        if self.list.count() and not self.list.currentItem():
            self.list.setCurrentRow(0)
        self.list.setUpdatesEnabled(True)
        self.update_status()

    def update_status(self):
        total_games = len(self.roms_data)
        parts = [f"<span style='color:{COLOR_NEUTRAL};'>●</span> <span style='color:#ffffff;'>{total_games} giochi</span>"]
        self.count_lbl.setText(" \u00b7 ".join(parts))

    def current_name(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def show_game(self, *_):
        unique_key = self.current_name()
        if not unique_key: return
        data = self.all_item_cache.get(unique_key, {})
        m = self.meta.get(unique_key, {})
        
        name = data.get("name", unique_key)
        rom_path = data.get("path", "")
        filename_with_ext = os.path.basename(rom_path) if rom_path else name

        title = html.escape(m.get("title", data.get("desc", name)))
        platform = html.escape(m.get("platform", data.get("subfolder", "")))
        year_val = html.escape(str(data.get("year", m.get("year", "?"))))
        filename_display = html.escape(filename_with_ext)

        rows = [
            ("Piattaforma", platform),
            ("Anno", year_val),
            ("ROM", filename_display)
        ]

        txt = f"<b>{title}</b>"
        LABEL_COLORS = {
            "Piattaforma": "#26a69a",
            "Anno": "#e5a50a",
            "ROM": "#b1b1b1"
        }
        for k, v in rows:
            color = LABEL_COLORS.get(k, "#ffffff")
            txt += f"<br><span style='color:{color}'>{k}:</span> {v}"

        self.info.setText(txt)
        self.set_cover(unique_key)
        self.update_favorite_button(unique_key)

    def set_cover(self, unique_key):
        data = self.all_item_cache.get(unique_key, {})
        game_dir = data.get("game_dir", "")
        name = data.get("name", unique_key)
        
        if game_dir:
            cover_path = os.path.join(game_dir, "cover.png")
        else:
            cover_path = os.path.join(IMG_DIR, name + ".png")

        if os.path.exists(cover_path):
            pm = QPixmap(cover_path)
            scaled_pm = pm.scaled(self.cover.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cover.setPixmap(scaled_pm)
        else:
            self.cover.clear()
            self.cover.setText("Nessuna immagine")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        unique_key = self.current_name()
        if unique_key: self.set_cover(unique_key)

    def launch(self, *_):
        if (self.emu_thread is not None and self.emu_thread.isRunning()) or not self.isVisible(): return
        unique_key = self.current_name()
        if not unique_key and self.roms_data:
            item = self.roms_data[0]
            unique_key = f"{item[2]}_{item[0]}"

        if unique_key:
            data = self.all_item_cache.get(unique_key)
            if data and data.get("game_dir"):
                meta_path = os.path.join(data["game_dir"], "metadata.json")
                m = load_json(meta_path)
                exec_command = m.get("exec_command", [])
                
                if exec_command:
                    if hasattr(self, "gamepad"): self.gamepad.enabled = False
                    self.hide()
                    
                    self.emu_thread = EmulatorRunnerThread(exec_command)
                    self.emu_thread.finished.connect(self.on_game_finished)
                    self.emu_thread.start()

    def on_game_finished(self):
        if hasattr(self, "gamepad"): self.gamepad.enabled = True
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if hasattr(self, "gamepad"):
            self.gamepad.running = False
            self.gamepad.wait()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SMSLauncher()
    w.show()
    sys.exit(app.exec())
