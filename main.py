import time
import re
import urllib.parse
from pypresence import Presence
import pygetwindow as gw
from ytmusicapi import YTMusic

CLIENT_ID = '123456789'  # Replace with your Discord App ID
UPDATE_INTERVAL = 1  # seconds

# Public search is fine for basic metadata; use headers_auth.json if you want account context
ytmusic = YTMusic()

def get_youtube_music_window_title():
    """Find any browser window with YouTube Music in the title (Opera GX included)."""
    for title in gw.getAllTitles():
        if "YouTube Music" in title:
            return title
    return None

def parse_title(title: str):
    """
    Extract (song_hint, artist_hint) from a YT Music tab title.

    Handles:
      ▶ Song — Artist — YouTube Music — Opera GX
      ▶ Song - Artist - YouTube Music
      Song · Artist - YouTube Music - Opera GX
    """
    if not title:
        return None, None

    t = title.strip()

    # strip play/pause symbols and stray separators at the start
    t = re.sub(r'^[\s\-\|•>]*[▶️⏸❚❚►⏵]?\s*', '', t)

    # remove trailing site/browser suffixes (case-insensitive)
    t = re.sub(r'\s*(?:[-–]|—)\s*YouTube Music.*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*(?:[-–]|—)\s*Opera GX.*$', '', t, flags=re.IGNORECASE)

    t = t.strip()

    # Try split on " - ", " – ", " — ", or " · "
    parts = re.split(r'\s(?:-|–|—|·)\s', t)

    if len(parts) >= 2:
        song_hint = parts[0].strip()
        artist_hint = parts[1].strip()
        # avoid bogus "YouTube Music" artist if something slipped through
        if artist_hint.lower() == "youtube music":
            artist_hint = None
        return song_hint, artist_hint

    # Fallback: only song name available
    return t or None, None

def fetch_cover_and_url(song_hint: str, artist_hint: str):
    """
    Use ytmusicapi to fetch artwork URL, canonical song/artist, and a playable URL.
    Returns (artwork_url, listen_url, song_name, artist_name).
    Always returns a valid listen_url (direct track if found, else search link).
    """
    query = f"{song_hint} {artist_hint}" if artist_hint else song_hint
    results = ytmusic.search(query, filter="songs")

    # If no song match, try general search as fallback
    if not results:
        results = ytmusic.search(query)

    # Defaults
    artwork = None
    song_url = None
    song_name = song_hint
    artist_name = artist_hint or ""

    if results:
        first = results[0]

        # Prefer canonical names from API
        if first.get("title"):
            song_name = first["title"]

        # ytmusicapi returns a list of artist dicts under "artists"
        if first.get("artists"):
            artist_name = ", ".join(a.get("name", "") for a in first["artists"] if a.get("name")) or artist_name

        # Thumbnails (pick largest)
        if first.get("thumbnails"):
            artwork = first["thumbnails"][-1].get("url")

        # Build a direct YT Music watch link if we have a videoId
        vid = first.get("videoId")
        if vid:
            song_url = f"https://music.youtube.com/watch?v={vid}"

    # If we still don't have a direct link, fall back to a search URL so there's ALWAYS a button
    if not song_url:
        song_url = f"https://music.youtube.com/search?q={urllib.parse.quote(query)}"

    return artwork, song_url, song_name, artist_name

def main():
    rpc = Presence(CLIENT_ID)
    rpc.connect()
    print("✅ Connected to Discord")

    last_key = None
    cached_artwork = None
    cached_url = None
    start_ts = time.time()

    try:
        while True:
            title = get_youtube_music_window_title()
            if title:
                song_hint, artist_hint = parse_title(title)

                # Only proceed if we have some hint of the track
                if song_hint:
                    # Use (song_hint, artist_hint) as the change key (window title can be noisy)
                    key = f"{song_hint}|{artist_hint or ''}"

                    if key != last_key:
                        # New track detected → fetch/update + refresh cache + timestamp
                        artwork, song_url, song_name, artist_name = fetch_cover_and_url(song_hint, artist_hint)

                        if artwork:
                            cached_artwork = artwork
                        if song_url:
                            cached_url = song_url
                        start_ts = time.time()

                        rpc.update(
                            details=f"🎵 {song_name}",
                            state=f"👤 {artist_name}" if artist_name else "🎶 YouTube Music",
                            large_image=f"url:{cached_artwork}" if cached_artwork else "youtubemusic",
                            large_text=f"{song_name} — {artist_name}" if artist_name else song_name,
                            # ALWAYS include a playable button (direct link or search)
                            buttons=[{"label": "▶ Listen on YT Music", "url": str(cached_url)}],
                            start=start_ts
                        )
                        print(f"🎶 Now Playing: {song_name} by {artist_name or 'Unknown Artist'}")
                        last_key = key
                else:
                    # Couldn’t parse, don't spam RPC
                    pass

            else:
                # No YT Music window → clear presence and cache
                if last_key is not None:
                    rpc.clear()
                    print("⏹️ Playback stopped or tab closed. RPC cleared.")
                last_key = None
                cached_artwork = None
                cached_url = None

            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        rpc.clear()
        print("\n🛑 Stopped. RPC cleared.")

if __name__ == "__main__":
    main()
