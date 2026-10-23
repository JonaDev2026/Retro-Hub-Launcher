import os
import json
import urllib.request
import urllib.parse
import re
import zipfile
import logging
import traceback
from datetime import datetime
from pathlib import Path

CONFIG_DIR = os.path.expanduser("~/.config/launcher")
PROGRESS_FILE = os.path.join(CONFIG_DIR, "worker_progress.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "worker.lock")
LOG_FILE = os.path.join(CONFIG_DIR, "worker.log")
SUMMARY_FILE = os.path.join(CONFIG_DIR, "worker_summary.json")
DATABASE_CACHE_DIR = os.path.join(CONFIG_DIR, "database_cache")
LIBRETRO_TREE_URL = "https://api.github.com/repos/libretro/libretro-database/git/trees/master?recursive=1"
LIBRETRO_RAW_BASE = "https://raw.githubusercontent.com/libretro/libretro-database/master/"

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DATABASE_CACHE_DIR, exist_ok=True)

# Log dettagliato: usa mode="w" per pulire il log a ogni nuovo avvio/sessione
logger = logging.getLogger("launcher_worker")
logger.setLevel(logging.DEBUG)
logger.handlers.clear()
_log_format = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
_file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(_log_format)
logger.addHandler(_file_handler)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_log_format)
logger.addHandler(_console_handler)
logger.info("=" * 72)
logger.info("Worker avviato. Log pulito e inizializzato: %s", LOG_FILE)

VALID_EXTS = ('.sms', '.bin', '.sfc', '.smc', '.md', '.gen', '.nes', '.z64', '.n64', '.iso', '.rvz', '.chd', '.zip', '.cue', '.img', '.exe', '.bat', '.com')

_DOS_SKIP = {'dosbox.exe', 'dos4gw.exe', 'setup.exe', 'install.exe', 'setsound.exe', 'uninstall.exe', 'config.exe', 'setstick.exe', 'order.exe', 'helpme.exe', 'catalog.exe', 'hlfile01.exe'}
_DOS_CRC = None

def _get_dos_dat_crys(script_dir):
    global _DOS_CRC
    if _DOS_CRC is None:
        _DOS_CRC = set()
        dat_path = os.path.join(script_dir, "data", "DOS.dat")
        if os.path.exists(dat_path):
            try:
                with open(dat_path, encoding="utf-8", errors="replace") as f:
                    for m in re.finditer(r'rom \( name "[^"]+" size (\d+) crc ([0-9a-fA-F]+)', f.read()):
                        _DOS_CRC.add((int(m.group(1)), m.group(2).lower()))
            except Exception:
                pass
    return _DOS_CRC

def find_dos_exe(zip_path, script_dir):
    try:
        infos = zipfile.ZipFile(zip_path).infolist()
    except Exception:
        return None
    def base(i):
        return i.filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for exts in (('.exe', '.com'), ('.bat',)):
        c = [i for i in infos if not i.is_dir() and i.filename.lower().endswith(exts) and base(i) not in _DOS_SKIP]
        if c:
            dos_dat = _get_dos_dat_crys(script_dir)
            known = [i for i in c if (i.file_size, format(i.CRC, '08x')) in dos_dat]
            pool = known or c
            return max(pool, key=lambda i: i.file_size).filename.replace("/", "\\")
    return None

def get_emulator_command(platform_lower, rom_path, script_dir):
    """Restituisce il comando di avvio specifico per ogni emulatore standalone."""
    if "sega" in platform_lower or "mega drive" in platform_lower or "master system" in platform_lower:
        return ["flatpak", "run", "com.retrodev.blastem", rom_path]
    elif "gamecube" in platform_lower or "wii" in platform_lower:
        return ["flatpak", "run", "org.DolphinEmu.dolphin-emu", "-e", rom_path]
    elif "super nintendo" in platform_lower or "snes" in platform_lower:
        return ["flatpak", "run", "com.snes9x.Snes9x", rom_path]
    elif "nintendo 64" in platform_lower or "n64" in platform_lower:
        return ["flatpak", "run", "--file-forwarding", "io.github.gopher64.gopher64", "@@", rom_path, "@@"]
    elif "nintendo entertainment system" in platform_lower or "nes" in platform_lower or "nintendo" in platform_lower:
        return ["flatpak", "run", "ca._0ldsk00l.Nestopia", rom_path]
    elif "mame" in platform_lower or "arcade" in platform_lower:
        bios_path = os.path.expanduser("~/Games/bios")
        rom_dir = os.path.dirname(rom_path)
        rompath_arg = f"{rom_dir};{bios_path}"
        return ["flatpak", "run", "org.mamedev.MAME", rom_path, "-rompath", rompath_arg]
    elif "playstation 2" in platform_lower or "ps2" in platform_lower:
        appimage_path = os.path.expanduser("~/Games/roms/Sony - PlayStation 2/pcsx2-v2.8.2-linux-appimage-x64-Qt.AppImage")
        return [appimage_path, rom_path]
    elif "playstation 1" in platform_lower or "ps1" in platform_lower or "psx" in platform_lower or "playstation" in platform_lower:
        return ["flatpak", "run", "org.duckstation.DuckStation", rom_path]
    elif "xbox" in platform_lower:
        return ["flatpak", "run", "app.xemu.xemu", "-dvd_path", rom_path]
    elif "dos" in platform_lower:
        args = ["-c", f'mount d "{rom_path}"', "-c", "d:"]
        if rom_path.lower().endswith(".zip"):
            exe = find_dos_exe(rom_path, script_dir)
            if exe:
                if "\\" in exe:
                    d, exef = exe.rsplit("\\", 1)
                    args += ["-c", f"cd {d}"]
                    args += ["-c", exef, "-c", "exit"]
                else:
                    args += ["-c", exe, "-c", "exit"]
        return ["flatpak", "run", f"--filesystem={script_dir}", "com.dosbox_x.DOSBox-X"] + args
    return [rom_path]

def _http_read(url, timeout=12):
    """Legge una risorsa HTTP senza dipendenze esterne."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "MAME-Launcher-Metadata-Worker/1.0",
        "Accept": "application/vnd.github+json, text/plain, */*",
    })
    logger.debug("HTTP GET %s (timeout=%ss)", url, timeout)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            logger.debug("HTTP %s %s: %d byte", response.status, url, len(data))
            return data
    except Exception as exc:
        logger.warning("HTTP ERRORE %s: %s: %s", url, type(exc).__name__, exc)
        raise


def _normal_name(value):
    """Normalizzazione conservativa: non altera il nome salvato sul disco."""
    value = os.path.basename(str(value or "")).strip()
    value = re.sub(r"\.[^.]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.casefold()


def _decode_msgpack_value(data, offset=0):
    """Decodifica i tipi MessagePack usati dagli RDB Libretro senza dipendenze esterne."""
    if offset >= len(data):
        raise ValueError("Fine inattesa del record MessagePack")
    code = data[offset]
    offset += 1

    def uint(n):
        nonlocal offset
        if offset + n > len(data):
            raise ValueError("Valore MessagePack troncato")
        value = int.from_bytes(data[offset:offset+n], "big", signed=False)
        offset += n
        return value

    def raw(n, as_text=False):
        nonlocal offset
        if n < 0 or offset + n > len(data):
            raise ValueError("Stringa/binario MessagePack troncato")
        value = data[offset:offset+n]
        offset += n
        return value.decode("utf-8", errors="replace") if as_text else value

    if code <= 0x7f:
        return code, offset
    if code >= 0xe0:
        return code - 256, offset
    if 0xa0 <= code <= 0xbf:
        return raw(code & 0x1f, True), offset
    if 0x90 <= code <= 0x9f:
        return _decode_msgpack_array(data, offset, code & 0x0f)
    if 0x80 <= code <= 0x8f:
        return _decode_msgpack_map(data, offset, code & 0x0f)

    if code == 0xc0: return None, offset
    if code == 0xc2: return False, offset
    if code == 0xc3: return True, offset
    if code == 0xca:
        import struct
        if offset + 4 > len(data): raise ValueError("Float32 troncato")
        value = struct.unpack(">f", data[offset:offset+4])[0]; return value, offset+4
    if code == 0xcb:
        import struct
        if offset + 8 > len(data): raise ValueError("Float64 troncato")
        value = struct.unpack(">d", data[offset:offset+8])[0]; return value, offset+8
    if code in (0xcc, 0xcd, 0xce, 0xcf):
        n = {0xcc:1, 0xcd:2, 0xce:4, 0xcf:8}[code]; return uint(n), offset
    if code in (0xd0, 0xd1, 0xd2, 0xd3):
        n = {0xd0:1, 0xd1:2, 0xd2:4, 0xd3:8}[code]
        if offset+n > len(data): raise ValueError("Intero signed troncato")
        return int.from_bytes(data[offset:offset+n], "big", signed=True), offset+n
    if code in (0xd9, 0xda, 0xdb):
        n = {0xd9:1, 0xda:2, 0xdb:4}[code]; size = uint(n); return raw(size, True), offset
    if code in (0xc4, 0xc5, 0xc6):
        n = {0xc4:1, 0xc5:2, 0xc6:4}[code]; size = uint(n); return raw(size, False), offset
    if code in (0xdc, 0xdd):
        n = {0xdc:2, 0xdd:4}[code]
        count = uint(n)
        return _decode_msgpack_array(data, offset, count)
    if code in (0xde, 0xdf):
        n = {0xde:2, 0xdf:4}[code]
        count = uint(n)
        return _decode_msgpack_map(data, offset, count)
    if code in (0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xc7, 0xc8, 0xc9):
        if code in (0xd4, 0xd5, 0xd6, 0xd7, 0xd8):
            size = {0xd4:1, 0xd5:2, 0xd6:4, 0xd7:8, 0xd8:16}[code]
        else:
            n = {0xc7:1, 0xc8:2, 0xc9:4}[code]; size = uint(n)
        if offset >= len(data): raise ValueError("Extension MessagePack troncata")
        offset += 1
        return raw(size, False), offset
    raise ValueError(f"Tipo MessagePack non supportato: 0x{code:02x}")


def _decode_msgpack_array(data, offset, count):
    result = []
    for _ in range(count):
        value, offset = _decode_msgpack_value(data, offset)
        result.append(value)
    return result, offset


def _decode_msgpack_map(data, offset, count):
    result = {}
    for _ in range(count):
        key, offset = _decode_msgpack_value(data, offset)
        value, offset = _decode_msgpack_value(data, offset)
        if isinstance(key, bytes):
            key = key.decode("utf-8", errors="replace")
        result[str(key)] = value
    return result, offset


def _rdb_records(data):
    """Legge i record di un file RetroArch RDB rispettando l'header C da 16 byte."""
    if len(data) < 16 or data[:7] != b"RARCHDB" or data[7] != 0:
        raise ValueError("File non valido: header RARCHDB non valido")
    metadata_offset = int.from_bytes(data[8:16], "big", signed=False)
    end = metadata_offset if 16 <= metadata_offset <= len(data) else len(data)
    record_data = data[:end]
    offset = 16
    count = 0
    while offset < end:
        record_start = offset
        try:
            record, new_offset = _decode_msgpack_value(record_data, offset)
        except (ValueError, IndexError, OverflowError) as exc:
            logger.warning(
                "Fine/record RDB non decodificabile a offset %d di %d: %s; "
                "mantengo i %d record già letti",
                record_start, end, exc, count
            )
            break
        if new_offset <= record_start:
            logger.warning("Offset RDB non avanzato (%d); interrompo la lettura", record_start)
            break
        offset = new_offset
        if record is None:
            break
        if isinstance(record, dict):
            yield record
            count += 1
    logger.info("RDB decodificato: %d record validi", count)


def _normal_title_key(value):
    """Chiave per confrontare titolo database e cartella ROM senza alterare i nomi originali."""
    value = _normal_name(value)
    value = re.sub(r"\s*\((?:en|fr|de|es|it|nl|ja|zh|ko|pt|ru|sv|da|no|fi|pl|cs|hu|el|tr|ar|he|th|vi|id|ms|uk|hr|sk|ro|bg|ca|eu|gl|fa|hi|bn|ta|te|ur)(?:\s*,\s*(?:en|fr|de|es|it|nl|ja|zh|ko|pt|ru|sv|da|no|fi|pl|cs|hu|el|tr|ar|he|th|vi|id|ms|uk|hr|sk|ro|bg|ca|eu|gl|fa|hi|bn|ta|te|ur))*\)\s*", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*\((?:rev(?:ision)?\s*\d+|v\d+(?:\.\d+)*)\)\s*", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def _loose_title_key(value):
    """Chiave permissiva: ignora tag tra parentesi e differenze di punteggiatura."""
    value = _normal_name(value)
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\s*\([^()]*\)", " ", value)
        value = re.sub(r"\s*\[[^\[\]]*\]", " ", value)
        value = re.sub(r"\s*\{[^{}]*\}", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return re.sub(r"\s+", " ", value).strip()


def _candidate_rdb_paths(platform_name):
    filename = platform_name.strip() + ".rdb"
    roots = [
        os.path.expanduser("~/.config/retroarch/database/rdb"),
        os.path.expanduser("~/.config/retroarch/databases/rdb"),
        os.path.expanduser("~/.var/app/org.libretro.RetroArch/config/retroarch/database/rdb"),
        os.path.expanduser("~/.var/app/org.libretro.RetroArch/config/retroarch/databases/rdb"),
        os.path.expanduser("~/snap/retroarch/common/.config/retroarch/database/rdb"),
        "/usr/share/libretro-database/rdb",
        "/usr/share/retroarch/database/rdb",
    ]
    for root in roots:
        path = os.path.join(root, filename)
        if os.path.isfile(path) and os.path.getsize(path) > 15:
            yield path


def _load_rdb(platform_name):
    cache_name = re.sub(r"[^A-Za-z0-9._ -]", "_", platform_name.strip()) + ".rdb"
    cache_path = os.path.join(DATABASE_CACHE_DIR, cache_name)
    for local_path in _candidate_rdb_paths(platform_name):
        try:
            data = Path(local_path).read_bytes()
            if data.startswith(b"RARCHDB"):
                logger.info("Uso RDB locale per '%s': %s (%d byte)", platform_name, local_path, len(data))
                return data
            logger.warning("File ignorato: non è un RDB valido: %s", local_path)
        except Exception:
            logger.exception("Impossibile leggere RDB locale: %s", local_path)

    if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 15:
        try:
            data = Path(cache_path).read_bytes()
            if data.startswith(b"RARCHDB"):
                logger.info("Uso RDB in cache per '%s': %s (%d byte)", platform_name, cache_path, len(data))
                return data
            logger.warning("Cache RDB non valida, la riscarico: %s", cache_path)
        except Exception:
            logger.exception("Lettura cache RDB fallita: %s", cache_path)

    relative = "rdb/" + platform_name.strip() + ".rdb"
    url = LIBRETRO_RAW_BASE + urllib.parse.quote(relative, safe="/")
    try:
        logger.info("Scarico RDB ufficiale Libretro per '%s': %s", platform_name, url)
        data = _http_read(url, timeout=25)
        if not data.startswith(b"RARCHDB"):
            raise ValueError("La risposta scaricata non contiene l'header RARCHDB")
        with open(cache_path, "wb") as f:
            f.write(data)
        logger.info("RDB salvato in cache: %s (%d byte)", cache_path, len(data))
        return data
    except Exception as exc:
        logger.error("RDB non disponibile per '%s': %s", platform_name, exc)
        return b""


def _parse_rdb_entries(rdb_data):
    entries = {}
    for record in _rdb_records(rdb_data):
        year = record.get("releaseyear", record.get("year"))
        if year in (None, "", 0, "0"):
            continue
        year_text = str(year).strip()
        if not re.fullmatch(r"(?:19|20)\d{2}", year_text):
            continue
        keys = []
        for field in ("name", "description", "rom_name", "romname"):
            value = record.get(field)
            if isinstance(value, str) and value.strip():
                keys.append(value)
        rom_field = record.get("rom")
        if isinstance(rom_field, dict):
            value = rom_field.get("name")
            if isinstance(value, str) and value.strip():
                keys.append(value)
        elif isinstance(rom_field, list):
            for rom_item in rom_field:
                if isinstance(rom_item, dict):
                    value = rom_item.get("name")
                    if isinstance(value, str) and value.strip():
                        keys.append(value)
        for key in keys:
            entries.setdefault(_normal_name(key), year_text)
            entries.setdefault(_normal_title_key(key), year_text)
            loose_key = _loose_title_key(key)
            if loose_key:
                entries.setdefault("__loose__" + loose_key, year_text)
    return entries


def get_game_year(platform_name, game_folder_name, rom_path, rdb_cache):
    platform_key = platform_name.casefold()
    if platform_key not in rdb_cache:
        data = _load_rdb(platform_name)
        try:
            rdb_cache[platform_key] = _parse_rdb_entries(data) if data else {}
            logger.info("RDB '%s': %d titoli indicizzati per anno", platform_name, len(rdb_cache[platform_key]))
        except Exception:
            logger.exception("Errore nella lettura dell'RDB per '%s'", platform_name)
            rdb_cache[platform_key] = {}
    entries = rdb_cache[platform_key]
    candidates = [game_folder_name, os.path.basename(rom_path)]
    for candidate in candidates:
        for key in (_normal_name(candidate), _normal_title_key(candidate)):
            year = entries.get(key)
            if year:
                logger.info("Anno trovato via RDB per '%s': %s (chiave=%r)", game_folder_name, year, key)
                return year
    for candidate in candidates:
        loose_key = "__loose__" + _loose_title_key(candidate)
        year = entries.get(loose_key)
        if year:
            logger.info("Anno trovato via RDB (match titolo senza tag) per '%s': %s (chiave=%r)",
                        game_folder_name, year, loose_key.removeprefix("__loose__"))
            return year
    for candidate in candidates:
        match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", str(candidate))
        if match:
            logger.info("Anno esplicito nel nome per '%s': %s", game_folder_name, match.group(1))
            return match.group(1)
    logger.warning("Anno non trovato nell'RDB per '%s' (piattaforma '%s')", game_folder_name, platform_name)
    return None

def load_metadata(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def write_metadata(path, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, path)


_COVER_REGIONS = ["USA", "Europe", "World", "USA, Europe", "Japan", "Asia", "Europe, Australia", "Japan, USA", "USA, Asia", "Korea", "Australia", "Brazil", "Japan, Asia", "Japan, Korea", "USA, Australia"]
_COVER_LANG = r"\s*\((?:[A-Z][a-z](?:-[A-Za-z]+)?)(?:,[A-Z][a-z](?:-[A-Za-z]+)?)*\)"

def _cover_variants(name):
    """Genera varianti intelligenti del nome per trovare le copertine, gestendo prefissi e sottotitoli."""
    out = []
    def add(n):
        n = re.sub(r"\s+", " ", re.sub(r'[&*/:`<>?\\|"]', "_", n)).strip()
        if n and n not in out:
            out.append(n)
            
    m = re.search(_COVER_LANG, name)
    lang = m.group(0).strip() if m else ""
    no_lang = re.sub(_COVER_LANG, "", name).strip()
    plain = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", name).strip()
    has_region = re.search(r"(?:USA|Europe|World|Japan|Asia|Korea|Australia|Brazil)", name)
    
    titles = [plain]
    
    # 1. Rimuove prefissi comuni (es. Tom Clancy's)
    lower_plain = plain.lower()
    if lower_plain.startswith("tom clancy's "):
        sub_t = plain[13:].strip()
        titles.append(sub_t)
        
    # 2. Gestisce i sottotitoli (es. taglia dopo trattini o due punti per provare il titolo principale)
    base_titles = list(titles)
    for t in base_titles:
        for sep in [" - ", ": ", " – "]:
            if sep in t:
                main_part = t.split(sep)[0].strip()
                if main_part not in titles:
                    titles.append(main_part)
                    
    add(no_lang)
    for t in titles:
        if has_region:
            for r in _COVER_REGIONS:
                add(f"{t} ({r})")
                if lang:
                    add(f"{t} ({r}) {lang}")
        add(t)
    return out


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rom_dir = os.path.expanduser("~/Games/roms")
    logger.info("Script directory: %s", script_dir)
    logger.info("Cartella ROM configurata nel worker: %s", rom_dir)
    logger.info("Cartella ROM esiste: %s", os.path.isdir(rom_dir))
    logger.info("Cache database: %s", DATABASE_CACHE_DIR)
    logger.info("Log dettagliato: %s", LOG_FILE)

    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write("locked")

    try:
        all_games = []
        if os.path.isdir(rom_dir):
            for libretro_sys in sorted(os.listdir(rom_dir), key=str.casefold):
                sys_path = os.path.join(rom_dir, libretro_sys)
                if not os.path.isdir(sys_path):
                    logger.debug("Elemento ignorato (non directory piattaforma): %s", sys_path)
                    continue

                target_scan_path = sys_path
                if ("playstation 2" in libretro_sys.lower() or "playstation 1" in libretro_sys.lower() or "playstation" in libretro_sys.lower() or "dos" in libretro_sys.lower()) and os.path.isdir(os.path.join(sys_path, "roms")):
                    target_scan_path = os.path.join(sys_path, "roms")

                logger.info("Scansione piattaforma '%s' in %s", libretro_sys, target_scan_path)
                for base_name in sorted(os.listdir(target_scan_path), key=str.casefold):
                    game_dir = os.path.join(target_scan_path, base_name)
                    if not os.path.isdir(game_dir):
                        logger.debug("Elemento non cartella gioco ignorato: %s", game_dir)
                        continue
                    try:
                        files_in_game = os.listdir(game_dir)
                    except OSError:
                        logger.exception("Impossibile leggere cartella gioco: %s", game_dir)
                        continue
                    valid_files = [f for f in files_in_game if f.lower().endswith(VALID_EXTS)]
                    if not valid_files:
                        logger.debug("Nessun file ROM con estensione supportata in %s; contenuto=%r", game_dir, files_in_game)
                        continue

                    cue_files = [f for f in valid_files if f.lower().endswith(".cue")]
                    chosen_file = cue_files[0] if cue_files else valid_files[0]
                    rom_path = os.path.join(game_dir, chosen_file)
                    all_games.append((libretro_sys, base_name, rom_path, game_dir))
                    logger.debug("Gioco rilevato: piattaforma=%r cartella=%r ROM=%r", libretro_sys, base_name, rom_path)
        else:
            logger.error("La cartella ROM non esiste o non è accessibile: %s", rom_dir)

        logger.info("Scansione terminata: %d giochi rilevati", len(all_games))
        total = len(all_games) if all_games else 1
        with open(PROGRESS_FILE, "w", encoding="utf-8") as pf:
            json.dump({"task": "Scansione libreria...", "current": 0, "total": total}, pf, ensure_ascii=False)

        rdb_cache = {}
        
        # Struttura per il censimento finale
        summary_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "totale_giochi": total if all_games else 0,
            "con_copertina": 0,
            "senza_copertina": 0,
            "con_anno": 0,
            "senza_anno": 0,
            "piattaforme": {}
        }

        for i, (libretro_sys, base_name, rom_path, game_dir) in enumerate(all_games):
            with open(PROGRESS_FILE, "w", encoding="utf-8") as pf:
                json.dump({"task": f"RDB metadata: {base_name}", "current": i + 1, "total": total}, pf, ensure_ascii=False)

            meta_path = os.path.join(game_dir, "metadata.json")
            cover_path = os.path.join(game_dir, "cover.png")
            existed_before = os.path.isfile(meta_path)
            meta_data = load_metadata(meta_path)
            logger.info("Elaboro gioco %d/%d: piattaforma=%r cartella=%r", i + 1, total, libretro_sys, base_name)
            logger.debug("Percorsi: game_dir=%s | ROM=%s | metadata=%s | cover=%s", game_dir, rom_path, meta_path, cover_path)
            logger.debug("Metadata preesistenti (%s): %r", existed_before, meta_data)

            meta_data.setdefault("title", base_name)
            meta_data.setdefault("platform", libretro_sys)
            meta_data.setdefault("rom_path", rom_path)
            if not isinstance(meta_data.get("exec_command"), list) or not meta_data.get("exec_command"):
                meta_data["exec_command"] = get_emulator_command(libretro_sys.lower(), rom_path, script_dir)

            year = get_game_year(libretro_sys, base_name, rom_path, rdb_cache)
            if year:
                meta_data["year"] = year
                logger.info("Metadata aggiornati: year=%s per '%s'", year, base_name)
            else:
                logger.warning("Anno non aggiornato per '%s' (%s)", base_name, libretro_sys)

            try:
                write_metadata(meta_path, meta_data)
                logger.debug("Metadata JSON scritto correttamente: %s", meta_path)
            except Exception:
                logger.exception("Errore durante la scrittura di metadata.json: %s", meta_path)

            if os.path.exists(cover_path):
                logger.debug("Copertina già presente, non modificata: %s", cover_path)
            else:
                repo_sys_name = libretro_sys.replace(" ", "_")
                official_title = str(meta_data.get("title") or base_name)
                rom_no_ext = os.path.splitext(os.path.basename(rom_path))[0]
                names = list(dict.fromkeys([official_title, rom_no_ext, base_name]))
                names = [re.sub(r"\s+", " ", n.replace(":", "_").replace("/", "_").replace("\\", "_")).strip() for n in names]
                names += [v for v in _cover_variants(base_name) if v not in names]
                
                # Categorie ufficiali di Libretro Thumbnails
                categories = ("Named_Boxarts", "Named_Titles", "Named_Snaps", "Named_Logos")
                downloaded = False
                
                for name in names:
                    if downloaded:
                        break
                    # Ora TUTTE le varianti di nome testano TUTTE le categorie
                    for category in categories:
                        direct_url = (
                            f"https://raw.githubusercontent.com/libretro-thumbnails/"
                            f"{urllib.parse.quote(repo_sys_name, safe='')}/master/{category}/"
                            f"{urllib.parse.quote(name + '.png', safe='')}"
                        )
                        try:
                            req = urllib.request.Request(direct_url, headers={"User-Agent": "XVB-Launcher-Worker/1.0"})
                            with urllib.request.urlopen(req, timeout=8) as response:
                                content = response.read()
                                if response.status == 200 and len(content) > 100 and content.startswith(b"\x89PNG\r\n\x1a\n"):
                                    with open(cover_path, "wb") as out_file:
                                        out_file.write(content)
                                    logger.info("Copertina scaricata: %s | fonte=%s", cover_path, direct_url)
                                    downloaded = True
                                    break
                                logger.debug("Risposta copertina non valida: %s", direct_url)
                        except Exception as exc:
                            logger.debug("Tentativo copertina fallito (%s/%s): %s", category, name, exc)
                if not downloaded:
                    logger.warning("Nessuna copertina trovata | gioco=%s | piattaforma=%s", base_name, libretro_sys)

            # Raccogliamo i dati per il report di censimento finale
            has_cover = os.path.exists(cover_path)
            has_year = bool(meta_data.get("year"))

            if has_cover:
                summary_data["con_copertina"] += 1
            else:
                summary_data["senza_copertina"] += 1

            if has_year:
                summary_data["con_anno"] += 1
            else:
                summary_data["senza_anno"] += 1

            # Raggruppamento per piattaforma nel summary
            sys_stat = summary_data["piattaforme"].setdefault(libretro_sys, {
                "totale": 0,
                "con_copertina": 0,
                "senza_copertina": 0,
                "giochi_senza_copertina": []
            })
            sys_stat["totale"] += 1
            if has_cover:
                sys_stat["con_copertina"] += 1
            else:
                sys_stat["senza_copertina"] += 1
                sys_stat["giochi_senza_copertina"].append(base_name)

        # Scrittura del file di riepilogo finale (censimento)
        try:
            with open(SUMMARY_FILE, "w", encoding="utf-8") as sf:
                json.dump(summary_data, sf, indent=2, ensure_ascii=False)
            logger.info("Censimento libreria salvato in: %s", SUMMARY_FILE)
        except Exception:
            logger.exception("Impossibile scrivere il file di riepilogo summary")

        with open(PROGRESS_FILE, "w", encoding="utf-8") as pf:
            json.dump({"task": "Completato", "total": total, "current": total}, pf, ensure_ascii=False)
        logger.info("Worker completato senza errori fatali. Giochi elaborati: %d", len(all_games))

    except Exception as exc:
        logger.critical("ERRORE FATALE NEL WORKER: %s", exc)
        logger.critical(traceback.format_exc())
        try:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as pf:
                json.dump({"task": f"Errore worker: {exc}", "total": 1, "current": 0}, pf, ensure_ascii=False)
        except Exception:
            logger.exception("Impossibile aggiornare il file di progresso dopo l'errore")
        raise
    finally:
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception:
                logger.exception("Impossibile rimuovere il lock %s", LOCK_FILE)
        logger.info("Worker terminato. Lock rimosso se presente.")
        for handler in logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
