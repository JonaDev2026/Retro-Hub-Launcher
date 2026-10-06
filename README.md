
# 🎮 Retro Hub Launcher

![Retro Hub Launcher Preview](preview.png)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/PySide6-Qt6-green.svg)](https://pyside.org/)
[![OS](https://img.shields.io/badge/OS-Debian%2013%20(Trixie)-red.svg)](https://www.debian.org/)
[![Display Server](https://img.shields.io/badge/Display-X11%20%2F%20Xorg-orange.svg)](https://www.x.org/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)

**Retro Hub Launcher** è un frontend desktop ad alte prestazioni, thread-safe e completamente configurabile, progettato per la gestione e l'avvio di collezioni ROM retrogaming su sistemi Linux.

Sviluppato in **Python** utilizzando **PySide6 (Qt6)** per l'interfaccia utente grafica e **Pygame** per la gestione degli eventi hardware, si basa su un'architettura disaccoppiata **Client-Worker**. Garantisce la massima reattività dell'interfaccia durante l'ingestion asincrona dei giochi e lo scraping dei metadati.

Progettato ed emulato specificamente per **Debian 13 (Trixie)** in ambiente **X11 / Xorg**.

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

## 🔥 Caratteristiche Principali

* ⚡ **Architettura Asincrona Non-Bloccante**: L'interfaccia utente (`launcher_2.py`) rimane sempre reattiva a 60 FPS grazie all'esecuzione del worker di catalogazione (`worker.py`) in un processo dedicato in background.
* 🎮 **Navigazione via Gamepad (Zero-Keyboard)**: Supporto nativo ai controller via polling `/dev/input/js*` gestito tramite Pygame thread-safe.
* 🎨 **Auto-Scraping Copertine & Metadati**: Il worker monitora la cartella di importazione, organizza le ROM ed effettua lo scraping automatico delle copertine direttamente dai repository di Libretro.
* 🕹️ **Supporto Emulatori Multi-Backend**: Gestione trasparente di **RetroArch** (tramite core Libretro) e **MAME** (sia pacchetti nativi che Flatpak).
* 📁 **Ingestion Automatica (Watchdog)**: Smistamento dinamico dei file dalla cartella `import/` alle relative directory di sistema con generazione automatica di file `metadata.json` dedicati.

---

## 🏗️ Architettura del Sistema

L'applicazione si divide in due componenti principali sincronizzati tramite file di stato condivisi in `~/.config/sms_launcher/`:

```text
┌──────────────────────────────┐              ┌──────────────────────────────┐
│       launcher_2.py          │              │          worker.py           │
│   (PySide6 Frontend GUI)     │              │    (Background Ingestion)    │
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               │                                             │
               │────── Legge ROM / Metadati / Cover ────────>│ (Directory Struct)
               │                                             │
               │<───── Sincronizza Progressi / Lock ─────────│ (worker_progress.json)
```

1. **Frontend (`launcher_2.py`)**:
   * Gestisce l'interfaccia grafica (PySide6) con supporto filtri, ricerca dinamica e preferiti.
   * Gestisce gli input del gamepad e la mappatura dei tasti.
   * Esegue gli emulatori isolando i processi di gioco.
2. **Backend Worker (`worker.py`)**:
   * Monitora la cartella `import/`.
   * Identifica le ROM tramite hash e database JSON ufficiali (es. `mame_db.json`).
   * Scarica le miniature in formato PNG dal repository di Libretro Thumbnails.

---

## 📂 Struttura del Progetto

```text
sms_launcher/
├── launcher_2.py       # Main GUI, eventi input e gestione emulatori
├── worker.py          # Worker asincrono per scraping e organizzazione ROM
├── mame_db.json       # Database locale per mapping ROM Arcade
├── roms/              # Struttura ad albero organizzata per sistema
│   ├── Sega - Master System/
│   │   └── Alex Kidd/
│   │       ├── alex_kidd.sms
│   │       ├── metadata.json
│   │       └── cover.png
├── bios/              # BIOS richiesti per emulazione (es. neogeo.zip)
└── import/            # Cartella temporanea per l'ingestion di nuove ROM
```

---

## 🛠️ Requisiti di Sistema & Dipendenze (Debian 13 / X11)

L'applicazione richiede un ambiente **X11 / Xorg** su Debian 13.

### 1. Installazione Pacchetti di Sistema

Esegui il seguente comando nel terminale per installare le dipendenze Python, i driver joystick e le librerie X11:

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

### 2. Configurazione Permessi Gamepad

Per consentire l'accesso diretto ai dispositivi `/dev/input/js*` senza privilegi di root, aggiungi il tuo utente al gruppo `input`:

```bash
sudo usermod -aG input $USER
```

> **Nota:** È necessario disconnettersi ed effettuare nuovamente il login per applicare i permessi.

---

## 🚀 Setup Emulatori (RetroArch & MAME)

Il launcher è preconfigurato per integrarsi con le versioni Flatpak ufficiali degli emulatori:

```bash
# Installazione RetroArch via Flatpak
flatpak install flathub org.libretro.RetroArch

# Installazione MAME via Flatpak
flatpak install flathub org.mamedev.MAME
```

### Core Libretro Consigliati

Assicurati di installare i seguenti core dall'Online Updater di RetroArch:

| Piattaforma | Estensioni Supportate | Core Libretro Consigliato |
| :--- | :--- | :--- |
| **Super Nintendo** | `.sfc`, `.smc` | `snes9x_libretro.so` |
| **Nintendo NES** | `.nes` | `fceumm_libretro.so` |
| **Sega Mega Drive / MS** | `.sms`, `.md`, `.gen` | `genesis_plus_gx_libretro.so` |
| **Game Boy / GBC** | `.gb` | `gambatte_libretro.so` |
| **Game Boy Advance** | `.gba` | `vba_next_libretro.so` |
| **Nintendo 64** | `.z64`, `.n64` | `mupen64plus_next_libretro.so` |
| **Arcade / MAME** | `.zip`, `.chd` | MAME Native / Flatpak |

---

## 💻 Guida all'Uso

1. **Clona il repository e posizionati nella cartella**:
   ```bash
   git clone [https://github.com/vostro-utente/retro-hub-launcher.git](https://github.com/vostro-utente/retro-hub-launcher.git)
   cd retro-hub-launcher
   ```

2. **Prepara le cartelle**:
   Inserisci i file BIOS (es. `neogeo.zip`) nella cartella `bios/` e le ROM che desideri importare nella cartella `import/`.

3. **Avvia il Frontend**:
   ```bash
   python3 launcher_2.py
   ```
   *(All'avvio, il launcher eseguirà automaticamente `worker.py` per processare i file presenti in `import/`)*.

---

## ❓ Troubleshooting

* **Il Gamepad non risponde ai comandi:**
  Verifica che il dispositivo sia riconosciuto dal sistema eseguendo `jstest /dev/input/js0`. Se ricevi un errore di permessi, assicurati di aver eseguito il comando `sudo usermod -aG input $USER`.
* **Problemi di rendering con Wayland:**
  L'applicazione richiede esplicitamente una sessione X11/Xorg. Se stai utilizzando Wayland, effettua il logout e seleziona "GNOME su Xorg" o "Plasma (X11)" dalla schermata di login.
* **Stato del Worker Bloccato:**
  Se il worker si interrompe in modo anomalo, elimina il file di lock di sicurezza con il comando:
  ```bash
  rm ~/.config/sms_launcher/worker.lock
  ```

---

## 📄 Licenza

Distribuito sotto licenza **MIT**. Consulta il file `LICENSE` per maggiori dettagli.
