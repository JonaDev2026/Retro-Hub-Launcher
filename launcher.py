import glob
import hashlib
import html
import json
import os
import re
import select
import struct
import subprocess
import sys
import time
import pygame

from PySide6.QtCore import QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QIcon,
                           QPainter, QPalette, QPen, QPixmap, QKeySequence)
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QSplitter, QStyle, QStyledItemDelegate,
                               QListWidget, QListWidgetItem, QMenuBar,
                               QPushButton, QVBoxLayout, QWidget, QSizePolicy)

CONFIG_DIR = os.path.expanduser("~/.config/sms_launcher")
IMG_DIR = os.path.join(CONFIG_DIR, "img")
META_FILE = os.path.join(CONFIG_DIR, "meta.json")
PROGRESS_FILE = os.path.join(CONFIG_DIR, "worker_progress.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "worker.lock")

_script_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(_script_dir, "roms"), exist_ok=True)
os.makedirs(os.path.join(_script_dir, "import"), exist_ok=True)

DEFAULT_SETTINGS = {"rom_dir": "", "favorites": [], "language": "en"}

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

DOT = 24
COLOR_NEUTRAL = "#ffffff"  # Bianco pulito per Tutti i giochi e Preferiti
COLOR_WORKER_LABEL = "#ffd60a"

# Palette di 12 colori brillanti ottimizzati per il tema scuro
BRAND_PALETTE = [
    "#0089cf", "#ff375f", "#30d158", "#ff9f0a", "#bf5af2",
    "#5ac8fa", "#ffcc00", "#ff2d55", "#5856d6", "#4cd964",
    "#d1d1d6", "#ff9500"
]

# Mappatura fissa per i brand più famosi con i loro colori originali
FIXED_BRAND_COLORS = {
    "sega": "#0089cf",
    "nintendo": "#ff375f",
    "sony": "#d1d1d6",
    "atari": "#ff9f0a",
    "snk": "#ffcc00",
    "nec": "#bf5af2"
}

def get_color_for_brand(subfolder):
    if not subfolder:
        return BRAND_PALETTE[0]
    
    sub_lower = subfolder.lower()
    for brand, color in FIXED_BRAND_COLORS.items():
        if brand in sub_lower:
            return color
            
    # Assegnazione deterministica basata su hash per gli altri brand
    h = int(hashlib.md5(subfolder.encode('utf-8')).hexdigest(), 16)
    return BRAND_PALETTE[h % len(BRAND_PALETTE)]

AUTHOR, YEAR = "Jonathan Sanfilippo", "2026"
STATO = "#0c0c0c"
FONDO, PANNELLO, CERCA = "#121212", "#131215", "#252428"
TASTO, SCELTO, TESTO, GRIGIO = "#2c2c2c", "#3a3a3a", "#e0e0e0", "#9e9e9e"
IN_ONDA = "#3b2f4f"

LANGS = {
    "en": {
        "search_placeholder": "Search game...",
        "play": "Play",
        "favorite": "Favorite",
        "library": "Platforms",
        "all_games": "All games",
        "favorites": "Favorites",
        "worker_inactive": "Background worker inactive",
        "worker_starting": "starting...",
        "worker_idle": "inactive or completed",
        "ready": "Ready",
        "no_rom_folder": "No ROM folder set",
        "select_rom_start": "Select a ROM folder to start.",
        "menu_file": "File",
        "menu_refresh": "Refresh ROMs",
        "menu_quit": "Quit",
        "menu_settings": "Settings",
        "menu_rom_folder": "ROM folder...",
        "menu_language": "Language",
        "games_count": "games",
        "no_images": "No image",
        "loading_bg": "Loading in background...",
        "loading": "Loading...",
        "ready_to_play": "Ready to play...",
        "year": "Year",
        "platform": "Platform",
        "region": "Region",
        "revision": "Revision"
    },
    "it": {
        "search_placeholder": "Cerca gioco...",
        "play": "Avvia",
        "favorite": "Preferito",
        "library": "Piattaforme",
        "all_games": "Tutti i giochi",
        "favorites": "Preferiti",
        "worker_inactive": "Worker inattivo",
        "worker_starting": "avvio in corso...",
        "worker_idle": "inattivo o completato",
        "ready": "Pronto",
        "no_rom_folder": "Nessuna cartella ROM impostata",
        "select_rom_start": "Seleziona una cartella ROM per iniziare.",
        "menu_file": "File",
        "menu_refresh": "Aggiorna ROM",
        "menu_quit": "Esci",
        "menu_settings": "Impostazioni",
        "menu_rom_folder": "Cartella ROM...",
        "menu_language": "Lingua",
        "games_count": "giochi",
        "no_images": "Nessuna immagine",
        "loading_bg": "Caricamento in background...",
        "loading": "Caricamento...",
        "ready_to_play": "Pronto per giocare...",
        "year": "Anno",
        "platform": "Piattaforma",
        "region": "Regione",
        "revision": "Revisione"
    }
}

def make_dot(color):
    pm = QPixmap(DOT, DOT)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    r = DOT * 0.22
    p.drawEllipse(DOT / 2.0 - r, DOT / 2.0 - r, 2 * r, 2 * r)
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
QListWidget:focus {{ border: 1px solid {BRAND_PALETTE[0]}; }}
QListWidget::item:selected, QListWidget::item:selected:!active
    {{ background: {CERCA}; color: #ffffff; }}
QPushButton {{ background: {TASTO}; color: {TESTO}; border: none; border-radius: 6px;
              padding: 8px; }}
QPushButton:hover {{ background: {SCELTO}; }}
QSplitter::handle {{ background: {SCELTO}; }}
QWidget#status {{ background: {STATO}; }}
QWidget#status QLabel {{ color: #ffffff; }}
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
            
        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            icon.paint(painter, QRect(r.left() + 4, r.top() + (r.height() - DOT) // 2, DOT, DOT))
        x = r.left() + DOT + 10
        w = r.width() - DOT - 18
        
        name = painter.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight, w)
        painter.setPen(QColor("#ffffff" if selected else TESTO))
        painter.drawText(QRect(x, r.top() + 7, w, 16), Qt.AlignLeft | Qt.AlignVCenter, name)
        
        f = painter.font()
        if f.pointSizeF() > 0:
            f.setPointSizeF(max(f.pointSizeF() - 1.5, 7))
            painter.setFont(f)
            
        fm = painter.fontMetrics()
        cur_x = x

        year_str = index.data(Qt.UserRole + 1) or ""
        subfolder_str = index.data(Qt.UserRole + 5) or ""
        dot_color = index.data(Qt.UserRole + 2) or BRAND_PALETTE[0]

        if year_str:
            painter.setPen(QColor(GRIGIO))
            painter.drawText(QRect(cur_x, r.top() + 25, w, 15), Qt.AlignLeft | Qt.AlignVCenter, year_str)
            cur_x += fm.horizontalAdvance(year_str) + 4

        if year_str and subfolder_str:
            painter.setPen(QColor(GRIGIO))
            sep = " \u00b7 "
            painter.drawText(QRect(cur_x, r.top() + 25, w, 15), Qt.AlignLeft | Qt.AlignVCenter, sep)
            cur_x += fm.horizontalAdvance(sep) + 2

        if subfolder_str:
            painter.setPen(QColor(dot_color))
            painter.drawText(QRect(cur_x, r.top() + 25, w, 15), Qt.AlignLeft | Qt.AlignVCenter, subfolder_str)

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

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

def clean_platform_display(sub):
    if not sub: return ""
    if "Master_System" in sub: return "Sega Master System"
    elif "Mega_Drive" in sub: return "Sega Mega Drive"
    elif "Super_Nintendo" in sub or "SNES" in sub: return "Super Nintendo"
    elif "Nintendo_Entertainment_System" in sub or "NES" in sub: return "Nintendo NES"
    elif "Game_Boy_Advance" in sub: return "Game Boy Advance"
    elif "Game_Boy" in sub: return "Game Boy"
    elif "Nintendo_64" in sub: return "Nintendo 64"
    elif "PlayStation" in sub or "PSX" in sub: return "Sony PlayStation"
    return sub.replace("_-_", " ").replace("-", " ").replace("_", " ")

def list_roms_recursive(rom_dir):
    results = []
    if not rom_dir or not os.path.isdir(rom_dir):
        return results
    valid_exts = ('.sms', '.bin', '.sfc', '.smc', '.md', '.gen', '.nes', '.gb', '.gba', '.z64', '.n64', '.iso', '.zip')
    
    for root, dirs, files in os.walk(rom_dir):
        for f in files:
            if f.lower().endswith(valid_exts):
                base_name = os.path.splitext(f)[0]
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(root, rom_dir)
                parts = rel_path.split(os.sep)
                raw_sub = parts[0] if len(parts) > 0 and parts[0] != "." else ""
                subfolder = clean_platform_display(raw_sub)
                results.append((base_name, full_path, subfolder, root))
    return sorted(results, key=lambda x: x[0].lower())

def folder_size(path):
    total = 0
    for root, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total

def fmt_size(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, u) if u != "B" else "%d B" % n
        n /= 1024
    return "%.1f TB" % n

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

class EmulatorRunnerThread(QThread):
    finished = Signal()
    def __init__(self, rom_path, subfolder=""):
        super().__init__()
        self.rom_path = rom_path
        self.subfolder = subfolder

    def run(self):
        cores_base = os.path.expanduser("~/.var/app/org.libretro.RetroArch/config/retroarch/cores/")
        
        sub_lower = self.subfolder.lower()
        if "super nintendo" in sub_lower or "snes" in sub_lower:
            core_name = "snes9x_libretro.so"
        elif "nes" in sub_lower or "nintendo entertainment system" in sub_lower:
            core_name = "fceumm_libretro.so"
        elif "game boy advance" in sub_lower or "gba" in sub_lower:
            core_name = "vba_next_libretro.so"
        elif "game boy" in sub_lower:
            core_name = "gambatte_libretro.so"
        elif "nintendo 64" in sub_lower or "n64" in sub_lower:
            core_name = "mupen64plus_next_libretro.so"
        elif "master system" in sub_lower or "sms" in sub_lower:
            core_name = "genesis_plus_gx_libretro.so"
        else:
            core_name = "genesis_plus_gx_libretro.so"
            
        core_path = os.path.join(cores_base, core_name)
        cmd = ["flatpak", "run", "org.libretro.RetroArch", "-L", core_path, self.rom_path]
        try:
            subprocess.run(cmd)
        except Exception:
            pass
        self.finished.emit()

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
        self.worker_was_active = os.path.exists(LOCK_FILE)

        self.meta = load_json(META_FILE)
        self.roms_data = list_roms_recursive(self.settings["rom_dir"])
        self.rom_size = 0
        self.all_item_cache = {}
        self.emu_thread = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.fill_list)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self.poll_background_updates)
        self.poll_timer.start()

        self.search = SearchBox(self.tr("search_placeholder"))
        self.search.textChanged.connect(self.on_search_changed)

        self.list = QListWidget()
        self.list.setIconSize(QSize(DOT, DOT))
        self.list.setItemDelegate(GameDelegate(self.list))
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

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

        self.cover = QLabel(self.tr("loading"))
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setMinimumSize(250, 300)
        self.cover.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.info = QLabel(self.tr("ready_to_play"))
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.btn = QPushButton(self.tr("play"))
        self.btn.clicked.connect(self.launch)

        self.fav_btn = QPushButton(self.tr("favorite"))
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

        self.library_header_lbl = QLabel()
        self.folders_list = QListWidget()
        self.folders_list.setIconSize(QSize(DOT, DOT))
        self.folders_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.folders_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
        status.setFixedHeight(26)
        sl = QHBoxLayout(status)
        sl.setContentsMargins(12, 0, 12, 0)
        self.count_lbl = QLabel(self.tr("ready"))
        self.prog_lbl = QLabel(self.tr("worker_inactive"))
        sl.addWidget(self.count_lbl)
        sl.addSpacing(18)
        sl.addWidget(self.prog_lbl)
        sl.addStretch(1)
        self.copy_lbl = QLabel("\u00a9 %s %s \u00b7 MIT license" % (YEAR, AUTHOR))
        self.copy_lbl.setStyleSheet("color: #ffffff;")
        sl.addWidget(self.copy_lbl)
        lay.addWidget(status)

        self.setStyleSheet(STYLE)
        self.update_library_header()
        self.build_item_cache()
        self.update_folders_list()
        self.fill_list()
        self.list.setFocus()

        self.gamepad = GamepadThread()
        self.gamepad.up_pressed.connect(self.on_pad_up)
        self.gamepad.down_pressed.connect(self.on_pad_down)
        self.gamepad.left_pressed.connect(self.on_pad_left)
        self.gamepad.right_pressed.connect(self.on_pad_right)
        self.gamepad.a_pressed.connect(self.launch)
        self.gamepad.b_pressed.connect(self.toggle_favorite)
        self.gamepad.start()

        if not self.settings["rom_dir"]:
            self.cover.setText(self.tr("no_rom_folder"))
            self.info.setText(self.tr("select_rom_start"))
            QTimer.singleShot(100, self.first_run)
        else:
            QTimer.singleShot(200, self.compute_folder_size_async)

    def on_pad_up(self):
        if not self.isVisible(): return
        w = self.focusWidget()
        if w == self.folders_list:
            r = self.folders_list.currentRow()
            if r > 0: self.folders_list.setCurrentRow(r - 1)
        else:
            r = self.list.currentRow()
            if r > 0: self.list.setCurrentRow(r - 1)

    def on_pad_down(self):
        if not self.isVisible(): return
        w = self.focusWidget()
        if w == self.folders_list:
            r = self.folders_list.currentRow()
            if r < self.folders_list.count() - 1: self.folders_list.setCurrentRow(r + 1)
        else:
            r = self.list.currentRow()
            if r < self.list.count() - 1: self.list.setCurrentRow(r + 1)

    def on_pad_left(self):
        if not self.isVisible(): return
        self.folders_list.setFocus()

    def on_pad_right(self):
        if not self.isVisible(): return
        self.list.setFocus()

    def tr(self, key):
        lang = self.settings.get("language", "en")
        return LANGS.get(lang, LANGS["en"]).get(key, key)

    def set_language(self, lang_code):
        self.settings["language"] = lang_code
        save_settings(self.settings)
        self.retranslate_ui()

    def retranslate_ui(self):
        new_bar = self.build_menu()
        self.layout().setMenuBar(new_bar)
        self.menu_bar_widget.deleteLater()
        self.menu_bar_widget = new_bar

        self.search.setPlaceholderText(self.tr("search_placeholder"))
        self.update_library_header()
        self.update_folders_list()
        self.fill_list()
        curr = self.current_name()
        if curr: self.show_game()
        self.update_status()
        self.btn.setText(self.tr("play"))
        self.update_favorite_button(curr if curr else "")

    def update_library_header(self):
        self.library_header_lbl.setText(f"<b>{self.tr('library')}</b>")

    def start_background_worker(self):
        worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py")
        if os.path.exists(worker_script) and not os.path.exists(LOCK_FILE):
            try:
                subprocess.Popen([sys.executable, worker_script])
            except Exception:
                pass

    def compute_folder_size_async(self):
        if self.settings["rom_dir"] and os.path.isdir(self.settings["rom_dir"]):
            self.rom_size = folder_size(self.settings["rom_dir"])
            self.update_status()

    def poll_background_updates(self):
        import_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "import")
        has_imports = os.path.isdir(import_dir) and len(os.listdir(import_dir)) > 0
        is_locked = os.path.exists(LOCK_FILE)

        if has_imports and not is_locked:
            self.start_background_worker()

        current_roms = list_roms_recursive(self.settings["rom_dir"])
        if current_roms != self.roms_data:
            self.roms_data = current_roms
            self.meta = load_json(META_FILE)
            self.build_item_cache()
            self.update_folders_list()
            self.fill_list()
            self.compute_folder_size_async()
            curr = self.current_name()
            if curr:
                self.set_cover(curr)

        prog_data = load_json(PROGRESS_FILE)
        if prog_data:
            task = prog_data.get("task", "Elaborazione...")
            # Sicurezza: tronca i nomi troppo lunghi per evitare che allarghino la finestra
            if len(task) > 35:
                task = task[:32] + "..."
                
            current = prog_data.get("current", 0)
            total = prog_data.get("total", 0)
            if task == "Completato" and not is_locked:
                self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> Pronto (Completato)")
            else:
                pct = int((current / total) * 100) if total > 0 else 0
                self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> {task} ({current}/{total} - {pct}%)")
        else:
            txt = self.tr("worker_starting") if is_locked else self.tr("worker_idle")
            self.prog_lbl.setText(f"<span style='color:{COLOR_WORKER_LABEL};'>Worker:</span> {txt}")

    def build_item_cache(self):
        self.all_item_cache = {}
        for item_tuple in self.roms_data:
            name, path, subfolder, game_dir = item_tuple
            
            meta_file = os.path.join(game_dir, "metadata.json")
            m = load_json(meta_file)
            if not m:
                m = self.meta.get(name, {})
                
            desc = m.get("title", name)
            year_val = m.get("year", "?")
            
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

        # "Tutti i giochi" con dot bianco neutro
        it_all = QListWidgetItem(f"{self.tr('all_games')}  ({total_count})")
        it_all.setIcon(make_dot(COLOR_NEUTRAL))
        it_all.setData(Qt.UserRole, "all")
        self.folders_list.addItem(it_all)

        # "Preferiti" con dot bianco neutro
        it_fav = QListWidgetItem(f"{self.tr('favorites')}  ({fav_count})")
        it_fav.setIcon(make_dot(COLOR_NEUTRAL))
        it_fav.setData(Qt.UserRole, "favorites")
        self.folders_list.addItem(it_fav)

        subfolders = sorted(list(set(sub for _, _, sub, _ in self.roms_data if sub)))
        for sub in subfolders:
            count = sum(1 for _, _, s, _ in self.roms_data if s == sub)
            brand_color = get_color_for_brand(sub)
            it_sub = QListWidgetItem(f"{sub}  ({count})")
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

    def first_run(self):
        d = QFileDialog.getExistingDirectory(self, self.tr("menu_rom_folder"))
        if d:
            self.settings["rom_dir"] = d
            save_settings(self.settings)
            self.reload_roms()

    def reload_roms(self):
        self.start_background_worker()
        self.worker_was_active = True
        self.roms_data = list_roms_recursive(self.settings["rom_dir"])
        self.meta = load_json(META_FILE)
        self.build_item_cache()
        self.update_folders_list()
        self.fill_list()
        self.compute_folder_size_async()

    def build_menu(self):
        bar = QMenuBar()
        file_menu = bar.addMenu(self.tr("menu_file"))
        
        a_refresh = QAction(self.tr("menu_refresh"), self)
        a_refresh.setShortcut(QKeySequence.Refresh)
        a_refresh.triggered.connect(self.reload_roms)
        file_menu.addAction(a_refresh)

        file_menu.addSeparator()
        a_quit = QAction(self.tr("menu_quit"), self)
        a_quit.triggered.connect(self.close)
        file_menu.addAction(a_quit)

        sett = bar.addMenu(self.tr("menu_settings"))
        a_rom = QAction(self.tr("menu_rom_folder"), self)
        a_rom.triggered.connect(lambda: self.set_folder("rom_dir"))
        sett.addAction(a_rom)
        sett.addSeparator()

        lang_menu = sett.addMenu(self.tr("menu_language"))
        lang_grp = QActionGroup(self)
        lang_grp.setExclusive(True)
        current_lang = self.settings.get("language", "en")
        for l_code, l_label in (("en", "English"), ("it", "Italiano")):
            a = QAction(l_label, self, checkable=True)
            a.setChecked(current_lang == l_code)
            a.triggered.connect(lambda _c, code=l_code: self.set_language(code))
            lang_grp.addAction(a)
            lang_menu.addAction(a)

        return bar

    def set_folder(self, key):
        d = QFileDialog.getExistingDirectory(self, self.tr("menu_rom_folder"))
        if d:
            self.settings[key] = d
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
        self.fav_btn.setText(f"{star} {self.tr('favorite')}")

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
                m = self.meta.get(unique_key, self.meta.get(name, {}))
                title = m.get("title", name).lower()
                year = str(m.get("year", ""))
                region = m.get("region", "").lower()
                revision = m.get("revision", "").lower()
                hay = f"{title} {name} {year} {region} {revision} {subfolder}"
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
                it.setIcon(make_dot(dot_color))
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
        parts = [f"<span style='color:{COLOR_NEUTRAL};'>●</span> <span style='color:#ffffff;'>{total_games} {self.tr('games_count')}</span>"]
        if self.rom_size:
            parts.append(f"<span style='color:#ffffff;'>{fmt_size(self.rom_size)}</span>")
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
        title = html.escape(m.get("title", name))
        year = html.escape(str(m.get("year", "?")))
        platform = html.escape(m.get("platform", data.get("subfolder", "")))
        region = html.escape(m.get("region", "World"))
        revision = html.escape(m.get("revision", "Original"))

        rows = [
            (self.tr("year"), year),
            (self.tr("platform"), platform),
            (self.tr("region"), region),
            (self.tr("revision"), revision)
        ]

        txt = f"<b>{title}</b>"
        LABEL_COLORS = {
            self.tr("year"): "#0a84ff",
            self.tr("platform"): "#30d158",
            self.tr("region"): "#ff9f0a",
            self.tr("revision"): "#bf5af2"
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
            none_path = cover_path + ".none"
        else:
            cover_path = os.path.join(IMG_DIR, name + ".png")
            none_path = cover_path + ".none"

        if os.path.exists(cover_path):
            pm = QPixmap(cover_path)
            scaled_pm = pm.scaled(self.cover.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cover.setPixmap(scaled_pm)
        elif os.path.exists(none_path):
            self.cover.clear()
            self.cover.setText(self.tr("no_images"))
        else:
            self.cover.clear()
            self.cover.setText(self.tr("loading_bg"))

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

        if unique_key and self.settings["rom_dir"]:
            data = self.all_item_cache.get(unique_key)
            if data and data.get("path"):
                if hasattr(self, "gamepad"): self.gamepad.enabled = False
                rom_path = data["path"]
                subfolder = data.get("subfolder", "")
                self.hide()
                self.emu_thread = EmulatorRunnerThread(rom_path, subfolder)
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
