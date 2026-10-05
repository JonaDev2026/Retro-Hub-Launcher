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

DAT_BASE_URL = "https://raw.githubusercontent.com/libretro/libretro-database/refs/heads/master/metadat/no-intro/"
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
    "gb": "Nintendo_-_Game_Boy",
    "gba": "Nintendo_-_Game_Boy_Advance",
    "n64": "Nintendo_-_Nintendo_64"
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

def ensure_and_parse_dat(libretro_sys, sys_path, log_path):
    clean_dat_name = libretro_sys.replace("_-_", " - ").replace("_", " ") + ".dat"
    dat_local_path = os.path.join(sys_path, f"{libretro_sys}.dat")
    
    if not os.path.exists(dat_local_path) or os.path.getsize(dat_local_path) < 100:
        remote_url = DAT_BASE_URL + urllib.parse.quote(clean_dat_name)
        log_message(log_path, f"Scaricamento DAT da: {remote_url}")
        try:
            urllib.request.urlretrieve(remote_url, dat_local_path)
        except Exception as e:
            log_message(log_path, f"Errore download DAT {clean_dat_name}: {e}")
            return {}

    games_db = {}
    if os.path.exists(dat_local_path):
        try:
            with open(dat_local_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            game_blocks = re.findall(r'game\s*\((.*?)\)', content, re.DOTALL)
            log_message(log_path, f"Trovati {len(game_blocks)} giochi nel DAT per {libretro_sys}")
            
            for block in game_blocks:
                name_match = re.search(r'name\s+"(.*?)"', block)
                desc_match = re.search(r'description\s+"(.*?)"', block)
                year_match = re.search(r'year\s+"(.*?)"', block)
                
                if name_match:
                    game_title = name_match.group(1)
                    official_title = desc_match.group(1) if desc_match else game_title
                    
                    rom_match = re.search(r'rom\s*\([^)]*name\s+"(.*?)"', block)
                    rom_filename = rom_match.group(1) if rom_match else game_title

                    year = year_match.group(1) if year_match else ""
                    
                    parens = re.findall(r'\(([^)]+)\)', official_title)
                    region = "World"
                    revision = "Original"
                    for p in parens:
                        pl = p.lower()
                        if any(r in pl for r in ["usa", "europe", "japan", "world", "germany", "france", "spain", "italy", "uk", "brazil"]):
                            region = p
                        if "rev" in pl or "v1." in pl or "v2." in pl or "version" in pl:
                            revision = p

                    game_info = {
                        "title": official_title,
                        "year": year,
                        "region": region,
                        "revision": revision
                    }
                    
                    games_db[rom_filename.lower()] = game_info
                    games_db[os.path.splitext(rom_filename)[0].lower()] = game_info
                    games_db[game_title.lower()] = game_info
                    
                    fuzzy_key = clean_game_name_for_matching(os.path.splitext(rom_filename)[0])
                    if fuzzy_key and fuzzy_key not in games_db:
                        games_db[fuzzy_key] = game_info
                        
        except Exception as e:
            log_message(log_path, f"Errore parsing DAT: {e}")
    return games_db

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(script_dir, "giochi_list.txt")

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=== AVVIO WORKER ===\n")
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
                        libretro_sys = EXT_TO_LIBRETRO.get(os.path.splitext(f)[1].lower(), "Sega_-_Master_System_-_Mark_III") if rel_path == "." else SYSTEM_TO_LIBRETRO.get(rel_path.split(os.sep)[0].lower().replace("-", "_").replace(" ", "_"), "Nintendo_-_Super_Nintendo_Entertainment_System")
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
        save_json(PROGRESS_FILE, {"task": "Analisi libreria...", "current": 0, "total": total})
        loaded_dats = {}

        for i, (libretro_sys, base_name, rom_file_name, game_dir, sys_path) in enumerate(all_games):
            save_json(PROGRESS_FILE, {"task": f"Elaborazione: {base_name}", "current": i + 1, "total": total})
            if libretro_sys not in loaded_dats:
                loaded_dats[libretro_sys] = ensure_and_parse_dat(libretro_sys, sys_path, log_path)
            
            dat_index = loaded_dats[libretro_sys]
            
            official_title, year, region, revision = None, "", "World", "Original"
            
            # PULIZIA: Rimuove la versione (es. v1.1) dal nome della cartella per trovare il match esatto nel DAT
            base_name_clean = re.sub(r'\s*\([^)]*v\d+\.\d+[^)]*\)', '', base_name, flags=re.IGNORECASE).strip()
            
            search_keys = [
                base_name_clean.lower(),
                base_name_clean.lower() + ".sms",
                base_name_clean.lower() + ".bin",
                base_name_clean.lower() + ".zip",
                rom_file_name.lower(),
                base_name.lower(),
                clean_game_name_for_matching(base_name)
            ]
            
            for k in search_keys:
                if k in dat_index:
                    d_info = dat_index[k]
                    official_title = d_info["title"]
                    if d_info["year"]: year = d_info["year"]
                    if d_info["region"]: region = d_info["region"]
                    if d_info["revision"]: revision = d_info["revision"]
                    log_message(log_path, f"Match trovato per '{base_name}' usando la chiave '{k}' -> Titolo ufficiale DAT: {official_title}")
                    break

            if not official_title:
                official_title = base_name_clean
                log_message(log_path, f"Nessun match DAT per '{base_name}', uso fallback pulito: {official_title}")

            parens = re.findall(r'\(([^)]+)\)', official_title)
            for p in parens:
                pl = p.lower()
                if any(r in pl for r in ["usa", "europe", "japan", "world", "germany", "france", "spain", "italy", "uk", "brazil"]):
                    region = p
                if "rev" in pl or "v1." in pl or "v2." in pl or "version" in pl:
                    revision = p

            if not year:
                ym = re.search(r'\b(19\d{2}|20\d{2})\b', official_title)
                if ym: 
                    year = ym.group(1)
                else:
                    year = "1986" if "alex kidd" in official_title.lower() else "199?"

            meta_path = os.path.join(game_dir, "metadata.json")
            save_json(meta_path, {
                "title": official_title,
                "year": year,
                "platform": get_clean_platform_name(libretro_sys),
                "region": region,
                "revision": revision
            })

            cover_path = os.path.join(game_dir, "cover.png")
            none_path = cover_path + ".none"
            
            if not os.path.exists(cover_path) and not os.path.exists(none_path):
                direct_url = f"https://raw.githubusercontent.com/libretro-thumbnails/{libretro_sys}/master/Named_Boxarts/{urllib.parse.quote(official_title + '.png')}"
                log_message(log_path, f"Tentativo download copertina con nome ufficiale esatto: {direct_url}")
                try:
                    req = urllib.request.Request(direct_url, headers={'User-Agent': 'RetroHub-Worker'})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        if response.status == 200:
                            with open(cover_path, 'wb') as out_file: 
                                out_file.write(response.read())
                            log_message(log_path, f"Copertina scaricata con successo per {official_title}")
                        else:
                            open(none_path, 'w').close()
                except Exception as ce: 
                    log_message(log_path, f"Fallito download copertina: {ce}")
                    try:
                        open(none_path, 'w').close()
                    except Exception:
                        pass

        save_json(PROGRESS_FILE, {"task": "Completato", "total": total, "current": total})
        log_message(log_path, "=== ELABORAZIONE COMPLETATA CON SUCCESSO ===")
    except Exception as e:
        log_message(log_path, f"ERRORE GENERALE CRITICO: {e}")

if __name__ == "__main__":
    main()
