# Retro Hub Launcher

Retro Hub Launcher is a modern, lightweight, and stylish desktop frontend written in Python using PySide6 (Qt) and Pygame. It is designed to manage and launch retro gaming ROMs effortlessly across multiple platforms, featuring automated background metadata fetching, artwork generation, gamepad support, and robust emulator integration (RetroArch and MAME).

---

## Key Features

* Multi-Platform Support: Automatically categorizes and lists ROMs for systems such as Sega Master System, Mega Drive/Genesis, Super Nintendo (SNES), Nintendo NES, Game Boy, Game Boy Advance, Nintendo 64, and Arcade/MAME.
* Automated Background Worker: A dedicated background process (worker.py) handles ROM importing, metadata scraping, and cover art generation seamlessly.
* Dynamic Search & Filtering: Real-time filtering by game title, release year, platform, and region using an intuitive search bar and dynamic sidebar.
* Favorites System: Easily tag and filter your favorite games with a single keystroke or click.
* Dual Emulator Backend Integration: 
  * RetroArch: Automatically selects the appropriate Libretro core based on the platform.
  * MAME: Fully configured for arcade titles, featuring automated custom -rompath support for system BIOS files and standard windowed execution (1280x720).
* Gamepad Navigation: Full out-of-the-box gamepad support allowing you to navigate menus, select games, toggle favorites, and launch titles using standard joypad controls (/dev/input/js*).
* Customizable Settings: Easily configure ROM directories, switch between Flatpak and native emulator packages, and change the user interface language (English and Italian supported).

---

## Project Structure

sms_launcher/
├── launcher.py        # Main GUI application
├── worker.py          # Background metadata and asset scraper
├── roms/              # Default directory for your game ROMs
├── bios/              # Directory for system BIOS files required by MAME
└── import/            # Drop folder for automatic ROM importing

---

## Requirements

* Python 3.10+
* PySide6
* Pygame
* Emulators: RetroArch and/or MAME (supports both Flatpak and native installations).

---

## Usage

1. Place your ROM files inside the roms/ directory (or configure a custom path via the Settings menu).
2. Place any required system BIOS files (e.g., for Neo Geo or Arcade systems) inside the bios/ directory.
3. Run the launcher:
   python3 launcher.py
