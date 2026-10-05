# Retro Hub Launcher

A lightweight and modern retro ROM launcher written in Python with PySide6, designed to integrate with RetroArch via Flatpak and handle launching various systems (Super Nintendo, Mega Drive, NES, Game Boy, etc.) with full gamepad support.

---

## System Requirements

- Operating System: Debian 13 (Trixie)
- Graphics Session: X11
- Python: 3.11 or higher

---

## Dependencies and Installation

Follow these steps to set up the environment and install all necessary dependencies on Debian 13 X11.

### 1. Install System Packages and Python
Open the terminal and run this command to install Python, pip, Qt6 libraries, and gamepad support (pygame):

sudo apt update && sudo apt install -y python3 python3-pip python3-pyqt6 python3-pyside6 python3-pygame flatpak

### 2. Configure RetroArch via Flatpak
The launcher is configured to run emulators using RetroArch via Flatpak.

1. Add the Flathub repository:
   flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

2. Install RetroArch:
   flatpak install flathub org.libretro.RetroArch

3. Launch RetroArch at least once and download the desired cores (e.g., Snes9x, Genesis Plus GX, FCEumm, etc.) from the internal menu (Online Updater -> Core Downloader). They will be saved in ~/.var/app/org.libretro.RetroArch/config/retroarch/cores/

---

## How to Import Games (Automatic Import)

**Do not create manual folder structures inside `roms/`.** The application features an automated background worker (`worker.py`) that handles everything for you using official Libretro databases (DAT files).

1. Simply take your ROM files (e.g., `.sfc`, `.nes`, `.md`, `.gba`) and drop them directly into the **`import/`** folder located in the launcher's directory[cite: 4].
2. (Optional) You can also organize them into subfolders inside `import/` (like `import/snes/`, `import/megadrive/`)[cite: 4].
3. When you launch the application, the background worker will automatically:
   - Match and download official metadata from Libretro DAT files[cite: 4].
   - Create the correct system and game directory structure inside **`roms/`**[cite: 4].
   - Download official box art covers (`cover.png`) for your games[cite: 4].

---

## User Interface & Controls

- **Left Panel (Search & List):** Type in the search bar to filter games in real-time. Use the game list to browse your library.
- **Center Panel (Details & Actions):** Displays metadata (Year, Platform, Region) and cover art. Click **Play** (or press the confirmation button) to launch the game, and **Favorite** to toggle it in your favorites.
- **Right Panel (Platforms):** Switch between "All games", "Favorites", and specific platforms.
- **Menu Bar:** Use *File > Refresh ROMs* to reload your library, or *Settings* to change the ROM folder and language (English / Italian).

### Gamepad Controls
The launcher fully supports gamepads connected via Linux (`/dev/input/js*`):
- **D-Pad / Left Stick:** Navigate through the game list or platform menu.
- **Button A (Bottom):** Launch the selected game.
- **Button B (Right):** Toggle the game as a favorite.

---

## Launching the Launcher

1. Make sure you have `launcher.py` and `worker.py` in the same folder.
2. Start the program by running:
   python3 launcher.py
