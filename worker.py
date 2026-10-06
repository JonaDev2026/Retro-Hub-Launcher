import os
import json
import urllib.request
import urllib.parse
import re
import shutil

CONFIG_DIR = os.path.expanduser("~/.config/sms_launcher")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PROGRESS_FILE = os.path.join(CONFIG_DIR, "worker_progress.json")
LOCK_FILE = os.path.join(CONFIG_DIR, "worker.lock")

os.makedirs(CONFIG_DIR, exist_ok=True)

VALID_EXTS = ('.sms', '.bin', '.sfc', '.smc', '.md', '.gen', '.nes', '.gb', '.gba', '.z64', '.n64', '.zip', '.cue', '.iso', '.chd')

def get_clean_platform_name(libretro_sys):
    return libretro_sys.replace("_-_", " ").replace("_", " ")

def get_retroarch_core_for_platform(platform_name):
    p_lower = platform_name.lower()
    
    if "mame" in p_lower or "arcade" in p_lower:
        return "mame_libretro.so"
    elif "fbneo" in p_lower or "finalburn" in p_lower:
        return "fbneo_libretro.so"
        
    elif "nes" in p_lower or "nintendo entertainment system" in p_lower:
        return "fceumm_libretro.so"
    elif "snes" in p_lower or "super nintendo" in p_lower:
        return "snes9x_libretro.so"
    elif "mega drive" in p_lower or "genesis" in p_lower:
        return "genesis_plus_gx_libretro.so"
    elif "game boy" in p_lower:
        return "mgba_libretro.so"
    elif "playstation" in p_lower:
        return "pcsx_rearmed_libretro.so"
        
    return "mame_libretro.so"

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

def load_database_for_system(libretro_sys, data_dir, log_path):
    games_db = {}
    target_clean = libretro_sys.lower().replace("_", " ").replace("-", " ")
    
    if "mame" in target_clean or "arcade" in target_clean:
        mame_json_path = os.path.join(data_dir, "mame_db.json")
        if os.path.exists(mame_json_path):
            try:
                with open(mame_json_path, "r", encoding="utf-8") as f:
                    games_db = json.load(f)
                log_message(log_path, f"Caricato MAME DB da JSON. Voci: {len(games_db)}")
            except Exception as e:
                log_message(log_path, f"Errore caricamento mame_db.json: {e}")
    else:
        consoles_dir = os.path.join(data_dir, "consoles")
        if os.path.isdir(consoles_dir):
            matched_file = None
            for f in os.listdir(consoles_dir):
                if f.lower().endswith(".json"):
                    f_clean = f.lower().replace(".json", "").replace("-", " ").replace("_", " ")
                    if target_clean == f_clean or target_clean in f_clean or f_clean in target_clean:
                        matched_file = os.path.join(consoles_dir, f)
                        break
            
            if matched_file and os.path.exists(matched_file):
                try:
                    with open(matched_file, "r", encoding="utf-8") as f:
                        games_db = json.load(f)
                    log_message(log_path, f"Caricato DB JSON console da: {os.path.basename(matched_file)}. Voci: {len(games_db)}")
                except Exception as e:
                    log_message(log_path, f"Errore caricamento file JSON console: {e}")
                
    return games_db

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    log_path = os.path.join(script_dir, "giochi_list.txt")

    with open(LOCK_FILE, "w") as f:
        f.write("locked")

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=== WORKER STARTED (CORE MAPPING MODE) ===\n")
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
                        
                        if rel_path == ".":
                            libretro_sys = "Sega - Master System - Mark III"
                        else:
                            libretro_sys = rel_path.split(os.sep)[0]

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
                loaded_dbs[libretro_sys] = load_database_for_system(libretro_sys, data_dir, log_path)
            
            db_index = loaded_dbs[libretro_sys]
            
            official_title, year, region, revision = None, "", "World", "Original"
            base_name_clean = re.sub(r'\s*\([^)]*v\d+\.\d+[^)]*\)', '', base_name, flags=re.IGNORECASE).strip()
            rom_no_ext = os.path.splitext(rom_file_name)[0].lower()
            
            search_keys = [
                rom_no_ext,
                base_name.lower(),
                base_name_clean.lower(),
                clean_game_name_for_matching(base_name),
                clean_game_name_for_matching(rom_no_ext)
            ]
            
            for k in search_keys:
                if k in db_index:
                    d_info = db_index[k]
                    official_title = d_info["title"]
                    if d_info["year"]: year = d_info["year"]
                    if d_info["region"]: region = d_info["region"]
                    if d_info["revision"]: revision = d_info["revision"]
                    break

            if not official_title:
                official_title = base_name_clean

            if not year:
                ym = re.search(r'\b(19\d{2}|20\d{2})\b', official_title)
                if ym: year = ym.group(1)
                else: year = "?"

            assigned_core = get_retroarch_core_for_platform(libretro_sys)

            meta_path = os.path.join(game_dir, "metadata.json")
            save_json(meta_path, {
                "title": official_title,
                "year": year,
                "platform": get_clean_platform_name(libretro_sys),
                "region": region,
                "revision": revision,
                "core": assigned_core
            })

            cover_path = os.path.join(game_dir, "cover.png")
            none_path = cover_path + ".none"
            
            if not os.path.exists(cover_path) and not os.path.exists(none_path):
                target_title = official_title or rom_no_ext
                safe_title = target_title.replace(':', '_').replace('/', '_').replace('\\', '_')
                safe_title = ' '.join(safe_title.split())

                possible_names = [safe_title, rom_no_ext]
                subfolders = ["Named_Boxarts", "Named_Titles", "Named_Logos", "Named_Snaps"]
                downloaded = False

                for name_to_try in possible_names:
                    if downloaded: break
                    for folder in subfolders:
                        if downloaded: break
                        direct_url = f"https://raw.githubusercontent.com/libretro-thumbnails/{urllib.parse.quote(libretro_sys)}/master/{folder}/{urllib.parse.quote(name_to_try + '.png')}"
                        try:
                            req = urllib.request.Request(direct_url, headers={'User-Agent': 'RetroHub-Worker'})
                            with urllib.request.urlopen(req, timeout=10) as response:
                                if response.status == 200:
                                    content = response.read()
                                    if len(content) > 100 and content.startswith(b'\x89PNG\r\n\x1a\n'):
                                        with open(cover_path, 'wb') as out_file: 
                                            out_file.write(content)
                                        downloaded = True
                                        break
                        except Exception:
                            continue

                if not downloaded:
                    try: open(none_path, 'w').close()
                    except Exception: pass

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
