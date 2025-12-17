# 🎵 AutoSplitTagger (Universal Edition)

**AutoSplitTagger** is a powerful Python automated tool designed to rip, split, and tag audio from various disc image formats (`.nrg`, `.iso`, `.bin/.cue`, and physical Audio CDs).

## 🌟 Key Features

*   **Native NRG Support:** Directly reads Nero Disc Image (`.nrg`) files to extract audio tracks *without* mounting or Administrator privileges.
*   **Universal Compatibility:**
    *   **Disc Images:** `.nrg`, `.iso` (SACD/Data), `.bin/.cue`.
    *   **Audio Files:** `.flac`, `.wav`, `.mp3`, `.m4a`. (Auto-splits based on silence).
    *   **Physical Media:** Rips Audio CDs directly.
*   **High Quality Output:** Extracts to FLAC (Free Lossless Audio Codec) by default.
*   **Smart Automation:** Automatically detects silence to split tracks if cue sheet/metadata is missing.
*   **Metadata Integration:**
    *   Generates **AcoustID** fingerprints.
    *   Queries **MusicBrainz** for track info.
    *   Supports Local MusicBrainz Server (via Docker) for unlimited rate-free lookups.
*   **Portable:** Includes necessary binaries (`ffmpeg`, `fpcalc`, `sacd_extract`) in the `bin/` folder.

## 🛠️ Installation & Usage

### Method 1: Portable Binary
Just run `AutoSplitTagger.exe` (if built). No dependencies required.

### Method 2: Running from Source
1.  **Clone the Repo:**
    ```bash
    git clone https://github.com/Khogao/AutoSplitTagger.git
    cd AutoSplitTagger
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    # (Note: Standard libraries + mutagen, requests, pyqt6)
    ```
3.  **Run:**
    ```bash
    python main.py
    ```

## 🐋 Advanced: Offline/Faster Tagging (Optional)
For heavy usage, you can run a local MusicBrainz server to speed up metadata lookups and avoid API rate limits.
1.  Enter the `mb-docker` directory (if provided) or set up a standard MusicBrainz Docker.
2.  Run `docker-compose up -d`.
3.  The app will automatically detect `http://127.0.0.1:5000`.

## 📂 Project Structure
*   `main.py`: GUI Application entry point.
*   `processor.py`: Core logic for Audio Processing, Mounting, and Network Lookups.
*   `bin/`: Contains bundled tools (`ffmpeg.exe`, `fpcalc.exe`, `sacd_extract.exe`).
*   `dev_tools/`: Scripts for testing and building.

## 📜 License
This project uses components like FFmpeg and sacd_extract which are subject to their own licenses (GPL/LGPL).
Custom code is open source.
