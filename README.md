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

## Launching the Launcher

1. Make sure you have launcher.py and worker.py in the same folder.
2. Create a folder named roms in the same directory and organize your ROMs into subfolders (e.g., roms/Super Nintendo/, roms/Mega Drive/, etc.).
3. Start the program by running:
   python3 launcher.py

---

## Gamepad Support
The launcher includes a dedicated thread for controller management via Linux /dev/input/js* devices. Make sure your user has permissions to read them.
