# 🎬 Nova Media Player

A feature-rich Windows desktop media player with **AI-powered auto-subtitles**,
built with Python + PyQt6 + VLC + OpenAI Whisper.

---

## Features

### Formats supported
| Category | Examples |
|----------|---------|
| **Video** | MP4, MKV, AVI, MOV, WMV, FLV, WebM, M4V, MPEG, 3GP, TS, MTS, M2TS, VOB, OGV, RM, RMVB, DIVX, ASF, DV, and more |
| **Audio** | MP3, FLAC, WAV, AAC, OGG, WMA, M4A, OPUS, APE, AIFF, MKA, AC3, DTS, ALAC, MIDI, and more |
| **Images** | JPG, PNG, GIF, BMP, WebP, TIFF, ICO, HEIC, HEIF, AVIF, PSD, RAW (CR2, NEF, ARW, DNG, ORF…), and more |

### Auto-subtitles (like YouTube)
- Powered by **OpenAI Whisper** — runs 100 % offline, no API key needed
- Five model sizes to choose from (Subtitles menu):
  - **Tiny** — fastest, ~1 GB RAM
  - **Base** — recommended (default)
  - **Small** — more accurate
  - **Medium / Large** — best quality for difficult audio
- Subtitle segments are **cached** — reopening the same file shows subtitles instantly
- Toggle with `S` or the **CC** button

### Playback
- Hardware-accelerated video via **VLC**
- Seek anywhere with click-to-seek bar
- Skip ±5 seconds with arrow keys
- Volume control
- Double-click or press `F` for fullscreen

---

## Installation

### Step 1 — Install VLC Media Player
Download and install the **64-bit** version from:
https://www.videolan.org/vlc/download-windows.html

### Step 2 — Install FFmpeg
FFmpeg is required for Whisper to extract audio.

Option A (recommended):
```
winget install ffmpeg
```

Option B: Download from https://github.com/BtbN/FFmpeg-Builds/releases,
extract, and add the `bin` folder to your system PATH.

### Step 3 — Install Python packages
Double-click **`install.bat`**, or run manually:
```
pip install PyQt6 python-vlc Pillow openai-whisper
```

> **Note on torch:** `openai-whisper` depends on PyTorch. If `pip install openai-whisper`
> installs a CPU-only torch, that's fine — Whisper works on CPU (just slower on large models).

---

## Running

Double-click **`run.bat`**, or:
```
python nova_player.py
```

You can also open a file directly:
```
python nova_player.py "C:\Movies\my_movie.mkv"
run.bat "C:\Music\song.flac"
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` / `→` | Seek −5 s / +5 s |
| `↑` / `↓` | Volume up / down |
| `S` | Toggle subtitles |
| `F` | Fullscreen |
| `Esc` | Exit fullscreen |
| `Ctrl+O` | Open file |
| `Ctrl+Q` | Quit |

---

## Notes

- **Subtitle generation time** depends on file length and model size. A 2-hour movie
  takes roughly 5–15 minutes with the Base model on a modern CPU. Results are cached,
  so subsequent openings are instant.
- If you have an NVIDIA GPU, install the CUDA version of PyTorch for much faster
  transcription: https://pytorch.org/get-started/locally/
- The subtitle cache is stored in `%TEMP%\nova_player_subs\`. Use
  **Subtitles → Clear subtitle cache for this file** to force re-transcription.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Black video window | Make sure 64-bit VLC is installed |
| `python-vlc` import error | `pip install python-vlc` |
| No subtitles generated | Install `openai-whisper` and `ffmpeg` |
| HEIC / RAW images not loading | Install `Pillow` (`pip install Pillow`) |
| Very slow subtitle generation | Use Tiny model, or get a GPU |
