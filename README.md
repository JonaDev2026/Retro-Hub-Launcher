
# 🎮 Retro Hub Launcher

![Retro Hub Launcher Preview](preview.png)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/PySide6-Qt6-green.svg)](https://pyside.org/)
[![OS](https://img.shields.io/badge/OS-Debian%2013%20(Trixie)-red.svg)](https://www.debian.org/)
[![Display Server](https://img.shields.io/badge/Display-X11%20%2F%20Xorg-orange.svg)](https://www.x.org/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)

**Retro Hub Launcher** is a high-performance, thread-safe, and fully configurable desktop frontend designed for managing and launching retro gaming ROM collections on Linux.

Built in **Python** using **PySide6 (Qt6)** for the graphical user interface and **Pygame** for hardware event handling, it relies on a decoupled **Client-Worker** architecture. This guarantees maximum UI responsiveness during asynchronous game ingestion and metadata scraping.

Specifically engineered and optimized for **Debian 13 (Trixie)** running in an **X11 / Xorg** environment.

---

## 📸 Overview

```text
  +-----------------------------------------------------------------------+
  |  RETRO HUB LAUNCHER (PySide6 GUI)                                     |
  |  +---------------------+  +-----------------------------------------+ |
  |  | SYSTEMS             |  | GAMES LIST                              | |
  |  |  [x] SNES (12)      |  | > Super Mario World (SNES)              | |
  |  |  [ ] Mega Drive (8) |  |   The Legend of Zelda (SNES)            | |
  |  |  [ ] MAME (45)      |  |   Sonic the Hedgehog (MD)               | |
  |  +---------------------+  +-----------------------------------------+ |
  |  +------------------------------------------------------------------+ |
  |  | Status: Worker idle | Processing: 0/0 | Gamepad: Controller 1    | |
  |  +------------------------------------------------------------------+ |
  +-----------------------------------------------------------------------+
```

---

## 🔥 Key Features

* ⚡ **Non-Blocking Asynchronous Architecture**: The graphical frontend (`launcher_2.py`) maintains a steady 60 FPS while game cataloging is handled asynchronously by a background worker process (`worker.py`).
* 🎮 **Gamepad Navigation (Zero-Keyboard)**: Native controller navigation powered by thread-safe Pygame polling over `/dev/input/js*`.
* 🎨 **Automated Box Art & Metadata Scraping**: The worker monitors the import folder, organizes ROMs, and automatically scrapes cover art directly from official Libretro repositories.
* 🕹️ **Multi-Backend Emulator Integration**: Seamless execution support for **RetroArch** (via Libretro cores) and **MAME** (both native binaries and Flatpak).
* 📁 **Automated Ingestion (Watchdog)**: Automatically sorts incoming files from the `import/` directory into structured system subfolders and generates dedicated `metadata.json` files.

---

## 🏗️ System Architecture

The application is split into two core components synchronized via shared state files in `~/.config/sms_launcher/`:

```text
┌──────────────────────────────┐              ┌──────────────────────────────┐
│       launcher_2.py          │              │          worker.py           │
│   (PySide6 Frontend GUI)     │              │    (Background Ingestion)    │
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               │                                             │
               │────── Reads ROMs / Metadata / Covers ───────>│ (Directory Struct)
               │                                             │
               │<───── Syncs Progress / Lock Files ──────────│ (worker_progress.json)
```

1. **Frontend (`launcher_2.py`)**:
   * Manages the PySide6 interface with support for filtering, dynamic search, and favorites.
   * Handles gamepad inputs and button mappings.
   * Executes emulator processes in isolated child environments.
2. **Backend Worker (`worker.py`)**:
   * Continuously polls the `import/` directory.
   * Identifies ROMs using file hashes and local JSON databases (e.g., `mame_db.json`).
   * Downloads PNG box art thumbnails from the official Libretro Thumbnails repository.

---

## 📂 Project Structure

```text
sms_launcher/
├── launcher_2.py       # Main GUI, input event loop, and emulator launcher
├── worker.py          # Asynchronous worker for ROM scraping and organization
├── mame_db.json       # Local database mapping for Arcade ROMs
├── roms/              # Tree-structured directory grouped by system
│   ├── Sega - Master System/
│   │   └── Alex Kidd/
│   │       ├── alex_kidd.sms
│   │       ├── metadata.json
│   │       └── cover.png
├── bios/              # Mandatory BIOS files for emulation (e.g., neogeo.zip)
└── import/            # Drop folder for automatic ROM ingestion
```

---

## 🛠️ System Requirements & Dependencies (Debian 13 / X11)

This application strictly requires an **X11 / Xorg** session on Debian 13.

### 1. System Package Installation

Run the following command to install Python dependencies, joystick drivers, and X11 libraries:

```bash
sudo apt update && sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-pyside6 \
    python3-pygame \
    flatpak \
    x11-utils \
    libgl1-mesa-dri \
    libgl1-mesa-glx \
    joystick \
    udev
```

### 2. Gamepad Permissions Setup

To allow direct access to `/dev/input/js*` devices without root privileges, add your user to the `input` group:

```bash
sudo usermod -aG input $USER
```

> **Note:** Log out and log back in for group permission changes to take effect.

---

## 🚀 Emulator Setup (RetroArch & MAME)

The launcher comes pre-configured to integrate with official Flatpak emulator builds:

```bash
# Install RetroArch via Flatpak
flatpak install flathub org.libretro.RetroArch

# Install MAME via Flatpak
flatpak install flathub org.mamedev.MAME
```

### Recommended Libretro Cores

Make sure to install the following cores via RetroArch's Online Core Updater:

| Platform | Supported Extensions | Recommended Libretro Core |
| :--- | :--- | :--- |
| **Super Nintendo** | `.sfc`, `.smc` | `snes9x_libretro.so` |
| **Nintendo NES** | `.nes` | `fceumm_libretro.so` |
| **Sega Mega Drive / MS** | `.sms`, `.md`, `.gen` | `genesis_plus_gx_libretro.so` |
| **Game Boy / GBC** | `.gb` | `gambatte_libretro.so` |
| **Game Boy Advance** | `.gba` | `vba_next_libretro.so` |
| **Nintendo 64** | `.z64`, `.n64` | `mupen64plus_next_libretro.so` |
| **Arcade / MAME** | `.zip`, `.chd` | MAME Native / Flatpak |

---

## 💻 Quick Start Guide

1. **Clone the repository and navigate into the folder**:
   ```bash
   git clone [https://github.com/your-username/retro-hub-launcher.git](https://github.com/your-username/retro-hub-launcher.git)
   cd retro-hub-launcher
   ```

2. **Prepare directories**:
   Place required BIOS files (e.g., `neogeo.zip`) into the `bios/` directory and new ROMs into the `import/` directory.

3. **Launch the Frontend**:
   ```bash
   python3 launcher_2.py
   ```
   *(On startup, the launcher will automatically spawn `worker.py` to ingest and process files in `import/`)*.

---

## ❓ Troubleshooting

* **Gamepad input not responding:**
  Verify that your controller is recognized by running `jstest /dev/input/js0`. If you encounter permission errors, confirm your user is in the `input` group via `sudo usermod -aG input $USER`.
* **Rendering or window issues on Wayland:**
  The application explicitly targets X11/Xorg. If running Wayland, log out and select "GNOME on Xorg" or "Plasma (X11)" from your display manager.
* **Worker Process Locked / Stuck State:**
  If the background worker terminates unexpectedly, clear the lockfile with:
  ```bash
  rm ~/.config/sms_launcher/worker.lock
  ```

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
