# 🎶 YouTube Music RPC

A Discord Rich Presence client for **YouTube Music** that shows the current track, artist, and album art in your Discord profile.  
Works with Opera GX and most other browsers.

---

## 📦 Requirements

- **Python 3.13.7+** → [Download here](https://www.python.org/downloads/)  
- The following Python packages:

```powershell
py -m pip install pypresence ytmusicapi pygetwindow
```
## How to Run
## 1. Download or clone this repository.
## 2. Open ## PowerShell or ## Command Prompt inside the project folder.
## 3. Start the script:

```powershell
py main.py
```
Once running, your Discord profile will automatically update with your current ## YouTube Music track.

## Known Issues
- Sometimes the RPC may report a different song than the one actually playing.
- Cover art may not always fetch properly depending on availability.

## Notes
- Uses ytmusicapi for fetching metadata.
- Presence includes a clickable “Listen on YouTube Music” button.
- Works best on Windows with Opera GX; other browsers may also work.
