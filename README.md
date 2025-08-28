# 🎵 YouTube Music Discord RPC

Display your currently playing YouTube Music tracks directly in your Discord status with album artwork and track information.

![Discord Status Preview]([https://via.placeholder.com/400x100/7289da/ffffff?text=Now+Playing+on+YouTube+Music](https://theonewhobuilds1.linus-tech.tips/ttUUaqpmDU.png)

## ✨ Features

- 🎵 **Real-time status updates** - Shows current track and artist
- 🖼️ **Album artwork display** - Beautiful cover art in your Discord profile
- 🌐 **Browser compatibility** - Works with any modern web browser
- 🔄 **Automatic sync** - Updates instantly when you change tracks

---

## 📋 Prerequisites

- **Python 3.7.1+** - [Download Python](https://www.python.org/downloads/)
- **Discord Desktop App** - Required for Rich Presence
- **Web browser** with YouTube Music access

## 🚀 Quick Start

### 1. Install Dependencies
```bash
py -m pip install pypresence ytmusicapi
```

### 2. Download the Project
```bash
git clone <repository-url>
cd youtube-music-rpc
```
*Or download and extract the ZIP file to a folder*

### 3. Create Discord Application
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** and give it a name
3. Copy the **Application ID**
4. Paste it into the `CLIENT_ID` field in `main.py`
5. Save the file

### 4. Setup YouTube Music Authentication

#### Generate Authentication Headers:
(make sure you're cd'd into the python installation folder, otherwhise this command won't work)
```bash
py ytmusicapi browser
```

#### Capture Browser Headers:
1. Open your browser and navigate to [music.youtube.com](https://music.youtube.com)
2. Press `F12` (or `Ctrl+Shift+I`) to open Developer Tools
3. Go to the **Network** tab
4. Refresh the page (`F5`)
5. In the filter box, type: `browse`
6. Click on any `browse` request
7. Scroll to **Request Headers** section
8. Copy all headers and paste into your terminal
9. Press `Enter`, then `Ctrl+Z` (Windows) or `Ctrl+D` (Mac/Linux), then `Enter`

#### Move Authentication File:
```bash
# The command above creates 'browser.json' - rename and move it:
mv browser.json headers_auth.json
# Move to your project directory if needed
```

### 5. Run the Application
```bash
python main.py
```

🎉 **That's it!** Your Discord status will now show your YouTube Music activity.

---

## 🔧 Configuration

### Custom Client ID
Replace the `CLIENT_ID` in `main.py` with your Discord application ID:
```python
CLIENT_ID = "your_application_id_here"
```

### File Structure
```
youtube-music-rpc/
├── main.py                 # Main script
├── headers_auth.json       # Authentication headers
└── README.md              # This file
```

---

## 🐛 Troubleshooting

### Common Issues

**"No module named 'pypresence'"**
```bash
py -m pip install --upgrade pypresence ytmusicapi
```

**"Authentication failed"**
- Regenerate `headers_auth.json` following step 4
- Ensure you're logged into YouTube Music in your browser

**"Discord not detected"**
- Make sure Discord Desktop app is running (not browser version)
- Restart Discord if the status doesn't appear

**Rich Presence not showing**
- Check that "Display currently running game as status message" is enabled in Discord Settings > Activity Privacy

### Still having issues?
1. Make sure all files are in the same directory
2. Verify your Discord Application ID is correct
3. Check that YouTube Music is playing in your browser
4. Restart the script after making changes

---

## 📝 Known Limitations

- ⚠️ "Listen on YouTube Music" button is currently non-functional
- 🔄 Requires periodic re-authentication (headers expire)
- 🌐 Only works while YouTube Music is open in browser

---

## 🛠️ Technical Details

- **Built with:** Python, pypresence, ytmusicapi
- **Tested on:** Windows 10/11, macOS, Ubuntu
- **Compatible browsers:** Chrome, Firefox, Safari, Opera GX, Edge

---

## 📄 License

This project is provided as-is for educational purposes. Please respect YouTube Music's terms of service.

---

## 🤝 Contributing

Found a bug or want to contribute? Feel free to open an issue or submit a pull request!

---

*Made with ❤️ for the Discord and YouTube Music community*
