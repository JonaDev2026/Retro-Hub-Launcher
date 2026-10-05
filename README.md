# Retro Hub Launcher

A lightweight and modern retro ROM launcher written in Python with PySide6, designed to integrate with RetroArch via Flatpak and handle launching various systems with full gamepad support.

---

## System Requirements

- Operating System: Debian 13 (Trixie)
- Graphics Session: X11
- Python: 3.11 or higher

---

## Dependencies and Installation

Follow these steps to set up the environment and install all necessary dependencies on Debian 13 X11.

### 1. Install System Packages and Python
Open the terminal and run this command to install Python, pip, Qt6 libraries, gamepad support (pygame), and Flatpak:

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

You do not need to manually create complex directory structures inside the `roms/` folder. The application uses an automated background worker (`worker.py`) that handles everything through official Libretro databases (DAT files).

1. Go to the application directory and open (or create) the **`import/`** folder.
2. Inside it, create a subfolder named after the platform (for example **`snes`**, **`megadrive`**, **`nes`**, etc.).
3. Place your files in **`.zip`** format (or supported uncompressed ROMs like `.sfc`, `.md`, `.nes`) directly inside that subfolder (e.g., `import/snes/game.zip`).
4. When you launch the application or refresh the ROM library, the built-in worker will automatically read the files, download the correct metadata, create the final structure inside **`roms/`**, and download official box art covers (`cover.png`).

---

## Interface and Usage

- **Left Panel (Search & List):** Type in the search bar to filter games in real-time. Use the list to browse your library.
- **Center Panel (Details & Actions):** Displays metadata (Year, Platform, Region) and cover art. Click **Play** to start the game, or **Favorite** to toggle it in your favorites.
- **Right Panel (Platforms):** Filter the view between "All games", "Favorites", and specific platforms.
- **Menu Bar:** Use *File > Refresh ROMs* to reload your library, or *Settings* to change the ROM folder or language.

### Gamepad Controls
The launcher supports controllers connected via Linux (`/dev/input/js*`):
- **D-Pad / Left Stick:** Navigate through games or the platform menu.
- **Button A (Bottom):** Launch the selected game.
- **Button B (Right):** Add or remove the game from favorites.

---

## Launching the Launcher

1. Make sure you have `launcher.py` and `worker.py` in the same folder.
2. Start the program by running from the terminal:
   python3 launcher.py
