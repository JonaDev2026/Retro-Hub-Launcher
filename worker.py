import os
import json
import urllib.request
import urllib.parse
import time
import re
import shutil

CONFIG_DIR = os.path.expanduser("~/.config/sms_launcher")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PROGRESS_FILE = os.path.join(CONFIG_DIR, "worker_progress.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "worker.lock")

os.makedirs(CONFIG_DIR, exist_ok=True)

VALID_EXTS = ('.sms', '.bin', '.sfc', '.smc', '.md', '.gen', '.nes', '.gb', '.gba', '.z64', '.n64', '.zip')

EXT_TO_LIBRETRO = {
    '.sms': "Sega_-_Master_System_-_Mark_III",
    '.bin': "Sega_-_Mega_Drive_-_Genesis",
    '.md': "Sega_-_Mega_Drive_-_Genesis",
    '.gen': "Sega_-_Mega_Drive_-_Genesis",
    '.sfc': "Nintendo_-_Super_Nintendo_Entertainment_System",
    '.smc': "Nintendo_-_Super_Nintendo_Entertainment_System",
    '.nes': "Nintendo_-_Nintendo_Entertainment_System",
    '.gb': "Nintendo_-_Game_Boy",
    '.gba': "Nintendo_-_Game_Boy_Advance",
    '.z64': "Nintendo_-_Nintendo_64",
    '.n64': "Nintendo_-_Nintendo_64"
}

SYSTEM_TO_LIBRETRO = {
    "sega": "Sega_-_Master_System_-_Mark_III",
    "master_system": "Sega_-_Master_System_-_Mark_III",
    "sms": "Sega_-_Master_System_-_Mark_III",
    "megadrive": "Sega_-_Mega_Drive_-_Genesis",
    "genesis": "Sega_-_Mega_Drive_-_Genesis",
    "snes": "Nintendo_-_Super_Nintendo_Entertainment_System",
    "super_nintendo": "Nintendo_-_Super_Nintendo_Entertainment_System",
    "nes": "Nintendo_-_Nintendo_Entertainment_System",
    "nintendo_entertainment_system": "Nintendo_-_Nintendo_Entertainment_System",
    "gb": "Nintendo_-_Game_Boy",
    "gameboy": "Nintendo_-_Game_Boy",
    "gba": "Nintendo_-_Game_Boy_Advance",
    "game_boy_advance": "Nintendo_-_Game_Boy_Advance",
    "n64": "Nintendo_-_Nintendo_64",
    "nintendo_64": "Nintendo_-_Nintendo_64"
}

def get_clean_platform_name(libretro_sys):
    if "Master_System" in libretro_sys: return "Sega Master System"
    elif "Mega_Drive" in libretro_sys: return "Sega Mega Drive"
    elif "Super_Nintendo" in libretro_sys: return "Super Nintendo"
    elif "Nintendo_Entertainment_System" in libretro_sys: return "Nintendo NES"
    elif "Game_Boy_Advance" in libretro_sys: return "Game Boy Advance"
    elif "Game_Boy" in libretro_sys: return "Game Boy"
    elif "Nintendo_64" in libretro_sys: return "Nintendo 64"
    return libretro_sys.replace("_-_", " ").replace("_", " ")

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception: pass

def clean_game_name_for_matching(name):
    base = re.sub(r'[\(\[].*?[\)\]]', '', name)
    return re.sub(r'[^a-z0-9]', '', base.lower())

def log_message(log_path, message):
    try:
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(message + "\n")
    except Exception:
        pass

def load_rdb_database(libretro_sys, log_path):
    rdb_dir = os.path.expanduser("~/.config/retroarch/database/rdb")
    games_db = {}
    
    rdb_filename = None
    if "Master_System" in libretro_sys: rdb_filename = "Sega - Master System - Mark III.rdb"
    elif "Mega_Drive" in libretro_sys: rdb_filename = "Sega - Mega Drive - Genesis.rdb"
    elif "Super_Nintendo" in libretro_sys: rdb_filename = "Nintendo - Super Nintendo Entertainment System.rdb"
    elif "Nintendo_Entertainment_System" in libretro_sys: rdb_filename = "Nintendo - Nintendo Entertainment System.rdb"
    elif "Game_Boy_Advance" in libretro_sys: rdb_filename = "Nintendo - Game Boy Advance.rdb"
    elif "Game_Boy" in libretro_sys: rdb_filename = "Nintendo - Game Boy.rdb"
    elif "Nintendo_64" in libretro_sys: rdb_filename = "Nintendo - Nintendo 64.rdb"

    if not rdb_filename:
        return games_db

    rdb_path = os.path.join(rdb_dir, rdb_filename)
    if not os.path.exists(rdb_path):
        return games_db

    try:
        import msgpack
        with open(rdb_path, "rb") as f:
            unpacker = msgpack.Unpacker(f, raw=True)
            entries = []
            for unpacked in unpacker:
                if isinstance(unpacked, dict):
                    clean_dict = {}
                    for k, v in unpacked.items():
                        k_str = k.decode('utf-8', errors='ignore') if isinstance(k, bytes) else str(k)
                        if isinstance(v, bytes):
                            try:
                                v_str = v.decode('utf-8', errors='ignore')
                            except Exception:
                                v_str = v
                        else:
                            v_str = v
                        clean_dict[k_str] = v_str
                    
                    if "entries" in clean_dict:
                        entries.extend(clean_dict["entries"])
                    else:
                        entries.append(clean_dict)
        
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name", "")
            if not name or "[tr" in name.lower() or "[b" in name.lower():
                continue
                
            year = str(entry.get("releaseyear", ""))
            
            parens = re.findall(r'\(([^)]+)\)', name)
            region = "World"
            revision = "Original"
            for p in parens:
                pl = p.lower()
                if any(r in pl for r in ["usa", "europe", "japan", "world", "germany", "france", "spain", "italy", "uk", "brazil"]):
                    region = p
                if "rev" in pl or "v1." in pl or "v2." in pl or "version" in pl:
                    revision = p

            game_info = {
                "title": name,
                "year": year,
                "region": region,
                "revision": revision
            }
            
            games_db[name.lower()] = game_info
            fuzzy_key = clean_game_name_for_matching(name)
            if fuzzy_key and fuzzy_key not in games_db:
                games_db[fuzzy_key] = game_info
                
    except Exception as e:
        log_message(log_path, f"Errore RDB: {e}")
        
    return games_db

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(script_dir, "giochi_list.txt")

    with open(LOCK_FILE, "w") as f:
        f.write("locked")

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=== WORKER STARTED (SMART THUMBNAIL CLEANER MODE) ===\n")
    except Exception:
        pass

    try:
        settings = load_json(SETTINGS_FILE)
        rom_dir = settings.get("rom_dir")
        if not rom_dir or not os.path.isdir(rom_dir):
            rom_dir = os.path.join(script_dir, "roms")
            os.makedirs(rom_dir, exist_ok=True)
            settings["rom_dir"] = rom_dir
            save_json(SETTINGS_FILE, settings)

        import_dir = os.path.join(script_dir, "import")
        if os.path.isdir(import_dir):
            for root, dirs, files in os.walk(import_dir):
                for f in files:
                    if f.lower().endswith(VALID_EXTS):
                        src_file = os.path.join(root, f)
                        rel_path = os.path.relpath(root, import_dir)
                        ext = os.path.splitext(f)[1].lower()
                        default_libretro = EXT_TO_LIBRETRO.get(ext, "Sega_-_Master_System_-_Mark_III")
                        
                        if rel_path == ".":
                            libretro_sys = default_libretro
                        else:
                            top_folder = rel_path.split(os.sep)[0].lower().replace("-", "_").replace(" ", "_")
                            libretro_sys = SYSTEM_TO_LIBRETRO.get(top_folder, default_libretro)

                        sys_path = os.path.join(rom_dir, libretro_sys)
                        os.makedirs(sys_path, exist_ok=True)
                        base_name = os.path.splitext(f)[0]
                        game_dir = os.path.join(sys_path, base_name)
                        os.makedirs(game_dir, exist_ok=True)
                        dst_rom = os.path.join(game_dir, f)
                        if os.path.exists(src_file) and not os.path.exists(dst_rom):
                            shutil.move(src_file, dst_rom)

        all_games = []
        if os.path.isdir(rom_dir):
            for libretro_sys in os.listdir(rom_dir):
                sys_path = os.path.join(rom_dir, libretro_sys)
                if os.path.isdir(sys_path):
                    for base_name in os.listdir(sys_path):
                        game_dir = os.path.join(sys_path, base_name)
                        if os.path.isdir(game_dir):
                            rom_file_name = base_name
                            for ef in os.listdir(game_dir):
                                if ef.lower().endswith(VALID_EXTS):
                                    rom_file_name = ef
                                    break
                            all_games.append((libretro_sys, base_name, rom_file_name, game_dir, sys_path))

        total = len(all_games) if all_games else 1
        save_json(PROGRESS_FILE, {"task": "Analyzing library...", "current": 0, "total": total})
        loaded_dbs = {}

        for i, (libretro_sys, base_name, rom_file_name, game_dir, sys_path) in enumerate(all_games):
            save_json(PROGRESS_FILE, {"task": f"Processing: {base_name}", "current": i + 1, "total": total})
            if libretro_sys not in loaded_dbs:
                loaded_dbs[libretro_sys] = load_rdb_database(libretro_sys, log_path)
            
            rdb_index = loaded_dbs[libretro_sys]
            
            official_title, year, region, revision = None, "", "World", "Original"
            base_name_clean = re.sub(r'\s*\([^)]*v\d+\.\d+[^)]*\)', '', base_name, flags=re.IGNORECASE).strip()
            rom_no_ext = os.path.splitext(rom_file_name)[0]
            
            search_keys = [
                rom_no_ext.lower(),
                base_name.lower(),
                base_name_clean.lower(),
                clean_game_name_for_matching(base_name),
                clean_game_name_for_matching(rom_no_ext)
            ]
            
            for k in search_keys:
                if k in rdb_index:
                    d_info = rdb_index[k]
                    official_title = d_info["title"]
                    if d_info["year"]: year = d_info["year"]
                    if d_info["region"]: region = d_info["region"]
                    if d_info["revision"]: revision = d_info["revision"]
                    log_message(log_path, f"Match RDB trovato per '{base_name}' con chiave '{k}' -> {official_title} ({year})")
                    break

            if not official_title:
                official_title = base_name_clean
                log_message(log_path, f"Nessun match RDB per '{base_name}', uso fallback: {official_title}")

            if not year:
                ym = re.search(r'\b(19\d{2}|20\d{2})\b', official_title)
                if ym: year = ym.group(1)
                else: year = "?"

            meta_path = os.path.join(game_dir, "metadata.json")
            save_json(meta_path, {
                "title": official_title,
                "year": year,
               "platform": get_clean_platform_name(libretro_sys),
                "region": region,
                "revision": revision
            })

            # --- GESTIONE DOWNLOAD THUMBNAIL INTELLIGENTE ---
            cover_path = os.path.join(game_dir, "cover.png")
            none_path = cover_path + ".none"
            
            if not os.path.exists(cover_path) and os.path.exists(none_path):
                try: os.remove(none_path)
                except Exception: pass

            if not os.path.exists(cover_path) and not os.path.exists(none_path):
                target_title = official_title
                if os.path.exists(meta_path):
                    try:
                        m_data = load_json(meta_path)
                        if m_data.get("title"):
                            target_title = m_data.get("title")
                    except Exception:
                        pass

                # Pulizia intelligente: spezzettiamo il titolo tenendo solo le parentesi iniziali 
                # finché non incontriamo tag come Beta, Rev, v1.1, Proto, Sample, [tr...], ecc.
                parts = re.split(r'(\s*\(.*?\))', target_title)
                clean_parts = []
                for p in parts:
                    if not p.strip():
                        continue
                    # Se il pezzo è una parentesi e contiene parole chiave di versione/revisione/beta/hack, interrompiamo
                    if p.startswith('('):
                        pl_lower = p.lower()
                        if any(bad in pl_lower for bad in ['beta', 'rev', 'proto', 'sample', 'demo', 'alt', 'version', 'v1.', 'v2.', 'v3.', 'hack', 'transl', 'program']):
                            break
                    clean_parts.append(p)
                
                clean_thumb_title = "".join(clean_parts).strip()
                if not clean_thumb_title:
                    clean_thumb_title = re.sub(r'[\(\[].*?[\)\]]', '', target_title).strip()

                safe_title = clean_thumb_title.replace(':', '_').replace('/', '_').replace('\\', '_')
                safe_title = ' '.join(safe_title.split())

                subfolders = ["Named_Boxarts", "Named_Logos", "Named_Snaps", "Named_Titles"]
                downloaded = False

                for folder in subfolders:
                    if downloaded:
                        break
                    
                    direct_url = f"https://raw.githubusercontent.com/libretro-thumbnails/{libretro_sys}/master/{folder}/{urllib.parse.quote(safe_title + '.png')}"
                    log_message(log_path, f"Tentativo download ({folder}): {direct_url}")
                    try:
                        req = urllib.request.Request(direct_url, headers={'User-Agent': 'RetroHub-Worker'})
                        with urllib.request.urlopen(req, timeout=10) as response:
                            if response.status == 200:
                                content = response.read()
                                if len(content) > 100 and content.startswith(b'\x89PNG\r\n\x1a\n'):
                                    with open(cover_path, 'wb') as out_file: 
                                        out_file.write(content)
                                    log_message(log_path, f"Immagine scaricata con successo da {folder} per: {safe_title}")
                                    downloaded = True
                                    break
                    except Exception:
                        continue

                if not downloaded:
                    try:
                        open(none_path, 'w').close()
                        log_message(log_path, f"Nessuna immagine trovata per {target_title} (cercato come: {safe_title}).")
                    except Exception:
                        pass

        save_json(PROGRESS_FILE, {"task": "Completed", "total": total, "current": total})
        log_message(log_path, "=== PROCESSING COMPLETED SUCCESSFULLY ===")
    except Exception as e:
        log_message(log_path, f"CRITICAL GENERAL ERROR: {e}")
    finally:
        if os.path.exists(LOCK_FILE):
            try: os.remove(LOCK_FILE)
            except Exception: pass

if __name__ == "__main__":
    main()
