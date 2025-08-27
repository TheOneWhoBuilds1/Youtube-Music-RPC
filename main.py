import time
import re
import urllib.parse
import logging
import json
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from pypresence import Presence, DiscordNotFound, InvalidPipe
import pygetwindow as gw
from ytmusicapi import YTMusic

# Configuration
@dataclass
class Config:
    CLIENT_ID: str = '123456789'  # Replace with your Discord App ID
    UPDATE_INTERVAL: float = 2.0  # seconds (reduced frequency to be less aggressive)
    CACHE_DURATION: int = 300  # seconds (5 minutes)
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 5.0
    LOG_LEVEL: str = 'INFO'
    USE_CACHE_FILE: bool = True
    CACHE_FILE: str = 'yt_music_cache.json'

# Setup logging
def setup_logging(level: str = 'INFO'):
    """Setup logging with proper formatting."""
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

@dataclass
class TrackInfo:
    """Data class for track information."""
    song_name: str
    artist_name: str
    artwork_url: Optional[str] = None
    listen_url: Optional[str] = None
    duration: Optional[int] = None
    timestamp: float = 0

class CacheManager:
    """Manages caching of track metadata to reduce API calls."""
    
    def __init__(self, cache_file: str, cache_duration: int):
        self.cache_file = Path(cache_file)
        self.cache_duration = cache_duration
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.load_cache()
    
    def load_cache(self):
        """Load cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load cache: {e}")
            self.cache = {}
    
    def save_cache(self):
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.warning(f"Failed to save cache: {e}")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached item if not expired."""
        if key not in self.cache:
            return None
        
        item = self.cache[key]
        if time.time() - item.get('timestamp', 0) > self.cache_duration:
            del self.cache[key]
            return None
        
        return item
    
    def set(self, key: str, value: Dict[str, Any]):
        """Cache an item with timestamp."""
        value['timestamp'] = time.time()
        self.cache[key] = value
        
        # Clean old entries periodically
        if len(self.cache) % 50 == 0:
            self._clean_expired()
    
    def _clean_expired(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key for key, item in self.cache.items()
            if current_time - item.get('timestamp', 0) > self.cache_duration
        ]
        for key in expired_keys:
            del self.cache[key]

class YouTubeMusicRPC:
    """Main class for YouTube Music Discord Rich Presence."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logging(config.LOG_LEVEL)
        self.rpc: Optional[Presence] = None
        self.ytmusic = None
        self.cache_manager = CacheManager(config.CACHE_FILE, config.CACHE_DURATION) if config.USE_CACHE_FILE else None
        
        self.last_track_key: Optional[str] = None
        self.last_update_time = 0
        self.start_timestamp = time.time()
        self.connection_retries = 0
        
    def initialize_ytmusic(self):
        """Initialize YouTube Music API with error handling."""
        try:
            self.ytmusic = YTMusic()
            self.logger.info("YouTube Music API initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize YouTube Music API: {e}")
            raise
    
    def connect_discord(self) -> bool:
        """Connect to Discord with retry logic."""
        for attempt in range(self.config.MAX_RETRIES):
            try:
                if self.rpc:
                    self.rpc.close()
                
                self.rpc = Presence(self.config.CLIENT_ID)
                self.rpc.connect()
                self.logger.info("✅ Connected to Discord")
                self.connection_retries = 0
                return True
                
            except (DiscordNotFound, InvalidPipe) as e:
                self.logger.warning(f"Discord connection failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.MAX_RETRIES - 1:
                    time.sleep(self.config.RETRY_DELAY)
            except Exception as e:
                self.logger.error(f"Unexpected error connecting to Discord: {e}")
                break
        
        self.connection_retries += 1
        return False
    
    def get_youtube_music_window_title(self) -> Optional[str]:
        """Find YouTube Music window with improved browser support."""
        try:
            youtube_music_titles = [
                title for title in gw.getAllTitles()
                if any(indicator in title for indicator in [
                    "YouTube Music",
                    "music.youtube.com",
                    "YT Music"
                ])
            ]
            
            if youtube_music_titles:
                # Prefer active/focused windows
                for title in youtube_music_titles:
                    if any(browser in title for browser in ["Opera GX", "Chrome", "Firefox", "Edge"]):
                        return title
                return youtube_music_titles[0]
            
        except Exception as e:
            self.logger.debug(f"Error getting window titles: {e}")
        
        return None
    
    def parse_title(self, title: str) -> Tuple[Optional[str], Optional[str]]:
        """Enhanced title parsing with better pattern matching."""
        if not title:
            return None, None
        
        # Remove common prefixes (play/pause symbols, etc.)
        cleaned = re.sub(r'^[\s\-\|•>▶️⏸❚►⏵]*\s*', '', title.strip())
        
        # Remove browser and site suffixes
        patterns_to_remove = [
            r'\s*(?:[-–—])\s*YouTube Music.*$',
            r'\s*(?:[-–—])\s*Opera GX.*$',
            r'\s*(?:[-–—])\s*Chrome.*$',
            r'\s*(?:[-–—])\s*Firefox.*$',
            r'\s*(?:[-–—])\s*Edge.*$',
            r'\s*\|\s*YouTube Music.*$'
        ]
        
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        cleaned = cleaned.strip()
        
        # Try different separators in order of preference
        separators = [r'\s—\s', r'\s–\s', r'\s-\s', r'\s·\s', r'\s\|\s']
        
        for sep_pattern in separators:
            parts = re.split(sep_pattern, cleaned)
            if len(parts) >= 2:
                song = parts[0].strip()
                artist = parts[1].strip()
                
                # Validate the parts
                if song and artist and artist.lower() not in ['youtube music', 'opera gx']:
                    return song, artist
        
        # Fallback: treat entire string as song name
        return cleaned or None, None
    
    def fetch_track_metadata(self, song_hint: str, artist_hint: str) -> TrackInfo:
        """Fetch track metadata with caching."""
        cache_key = f"{song_hint}|{artist_hint or ''}"
        
        # Check cache first
        if self.cache_manager:
            cached = self.cache_manager.get(cache_key)
            if cached:
                return TrackInfo(
                    song_name=cached['song_name'],
                    artist_name=cached['artist_name'],
                    artwork_url=cached.get('artwork_url'),
                    listen_url=cached.get('listen_url'),
                    duration=cached.get('duration')
                )
        
        # Search using API
        try:
            query = f"{song_hint} {artist_hint}" if artist_hint else song_hint
            results = self.ytmusic.search(query, filter="songs", limit=3)
            
            # Fallback to general search if no songs found
            if not results:
                results = self.ytmusic.search(query, limit=3)
            
            track_info = self._process_search_results(results, song_hint, artist_hint, query)
            
            # Cache the result
            if self.cache_manager and track_info:
                cache_data = {
                    'song_name': track_info.song_name,
                    'artist_name': track_info.artist_name,
                    'artwork_url': track_info.artwork_url,
                    'listen_url': track_info.listen_url,
                    'duration': track_info.duration
                }
                self.cache_manager.set(cache_key, cache_data)
            
            return track_info
            
        except Exception as e:
            self.logger.warning(f"API search failed: {e}")
            # Return basic info even if API fails
            return TrackInfo(
                song_name=song_hint,
                artist_name=artist_hint or "Unknown Artist",
                listen_url=f"https://music.youtube.com/search?q={urllib.parse.quote(f'{song_hint} {artist_hint or ''}')}"
            )
    
    def _process_search_results(self, results: list, song_hint: str, artist_hint: str, query: str) -> TrackInfo:
        """Process search results and extract best match."""
        if not results:
            return TrackInfo(
                song_name=song_hint,
                artist_name=artist_hint or "Unknown Artist",
                listen_url=f"https://music.youtube.com/search?q={urllib.parse.quote(query)}"
            )
        
        # Score results to find best match
        best_result = None
        best_score = -1
        
        for result in results[:3]:  # Check top 3 results
            score = self._calculate_match_score(result, song_hint, artist_hint)
            if score > best_score:
                best_score = score
                best_result = result
        
        if not best_result:
            best_result = results[0]
        
        # Extract information
        song_name = best_result.get("title", song_hint)
        
        # Handle artist names
        artist_name = artist_hint or "Unknown Artist"
        if best_result.get("artists"):
            artists = [a.get("name", "") for a in best_result["artists"] if a.get("name")]
            if artists:
                artist_name = ", ".join(artists)
        
        # Get artwork (prefer larger images)
        artwork_url = None
        if best_result.get("thumbnails"):
            artwork_url = best_result["thumbnails"][-1].get("url")
        
        # Build listen URL
        listen_url = f"https://music.youtube.com/search?q={urllib.parse.quote(query)}"
        video_id = best_result.get("videoId")
        if video_id:
            listen_url = f"https://music.youtube.com/watch?v={video_id}"
        
        # Get duration if available
        duration = None
        if best_result.get("duration_seconds"):
            duration = int(best_result["duration_seconds"])
        
        return TrackInfo(
            song_name=song_name,
            artist_name=artist_name,
            artwork_url=artwork_url,
            listen_url=listen_url,
            duration=duration
        )
    
    def _calculate_match_score(self, result: dict, song_hint: str, artist_hint: str) -> float:
        """Calculate how well a search result matches the hints."""
        score = 0.0
        
        # Title similarity
        result_title = result.get("title", "").lower()
        if result_title:
            if song_hint.lower() in result_title:
                score += 2.0
            elif any(word in result_title for word in song_hint.lower().split()):
                score += 1.0
        
        # Artist similarity
        if artist_hint and result.get("artists"):
            result_artists = " ".join(a.get("name", "").lower() for a in result["artists"])
            if artist_hint.lower() in result_artists:
                score += 2.0
            elif any(word in result_artists for word in artist_hint.lower().split()):
                score += 1.0
        
        # Prefer songs over other content types
        if result.get("category") == "Songs":
            score += 1.0
        
        return score
    
    def update_presence(self, track_info: TrackInfo):
        """Update Discord Rich Presence with error handling."""
        if not self.rpc:
            return False
        
        try:
            # Prepare RPC data
            rpc_data = {
                "details": f"🎵 {track_info.song_name}",
                "state": f"👤 {track_info.artist_name}",
                "start": int(self.start_timestamp),
                "buttons": [{"label": "🎧 Listen on YouTube Music", "url": track_info.listen_url}]
            }
            
            # Add artwork if available
            if track_info.artwork_url:
                rpc_data["large_image"] = f"url:{track_info.artwork_url}"
                rpc_data["large_text"] = f"{track_info.song_name} — {track_info.artist_name}"
            else:
                rpc_data["large_image"] = "youtubemusic"
                rpc_data["large_text"] = "YouTube Music"
            
            self.rpc.update(**rpc_data)
            self.logger.info(f"🎶 Now Playing: {track_info.song_name} by {track_info.artist_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update presence: {e}")
            return False
    
    def clear_presence(self):
        """Clear Discord presence with error handling."""
        if self.rpc:
            try:
                self.rpc.clear()
                self.logger.info("⏹️ Cleared Discord presence")
            except Exception as e:
                self.logger.debug(f"Error clearing presence: {e}")
    
    def run(self):
        """Main event loop."""
        self.logger.info("🎵 Starting YouTube Music Discord RPC")
        
        # Initialize services
        try:
            self.initialize_ytmusic()
        except Exception:
            self.logger.error("Failed to initialize. Exiting.")
            return
        
        if not self.connect_discord():
            self.logger.error("Could not connect to Discord. Exiting.")
            return
        
        try:
            while True:
                # Check if we need to reconnect to Discord
                if self.connection_retries > 0 and not self.connect_discord():
                    self.logger.warning("Failed to reconnect to Discord, retrying later...")
                    time.sleep(self.config.RETRY_DELAY)
                    continue
                
                # Get current window title
                window_title = self.get_youtube_music_window_title()
                
                if window_title:
                    song_hint, artist_hint = self.parse_title(window_title)
                    
                    if song_hint:
                        track_key = f"{song_hint}|{artist_hint or ''}"
                        
                        # Check if track changed
                        if track_key != self.last_track_key:
                            self.logger.debug(f"Track changed: {track_key}")
                            
                            # Fetch metadata and update presence
                            track_info = self.fetch_track_metadata(song_hint, artist_hint)
                            
                            if self.update_presence(track_info):
                                self.last_track_key = track_key
                                self.start_timestamp = time.time()
                                self.last_update_time = time.time()
                else:
                    # No YouTube Music window found
                    if self.last_track_key is not None:
                        self.clear_presence()
                        self.last_track_key = None
                
                time.sleep(self.config.UPDATE_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Shutting down...")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        if self.rpc:
            self.clear_presence()
            try:
                self.rpc.close()
            except:
                pass
        
        if self.cache_manager:
            self.cache_manager.save_cache()
        
        self.logger.info("✅ Cleanup completed")

def main():
    """Main entry point."""
    config = Config()
    rpc = YouTubeMusicRPC(config)
    rpc.run()

if __name__ == "__main__":
    main()
