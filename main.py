import time
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pypresence import Presence, DiscordNotFound, InvalidPipe
from ytmusicapi import YTMusic

# Configuration
@dataclass
class Config:
    """Configuration for the Discord Rich Presence script."""
    CLIENT_ID: str = '123456789'
    UPDATE_INTERVAL: float = 5.0
    LOG_LEVEL: str = 'INFO'
    HEADERS_FILE: str = 'headers_auth.json'
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 5.0

# Setup logging
def setup_logging(level: str = 'INFO'):
    """Setup logging with proper formatting."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

@dataclass
class TrackInfo:
    """Data class for track information."""
    title: str
    artist: str
    album: Optional[str] = None
    url: Optional[str] = None
    artwork: Optional[str] = None
    
class YouTubeMusicRPC:
    """Main class for YouTube Music Discord Rich Presence."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logging(config.LOG_LEVEL)
        self.rpc: Optional[Presence] = None
        self.ytmusic: Optional[YTMusic] = None
        
        self.last_track_id: Optional[str] = None
        self.start_timestamp: Optional[int] = None
        self.connection_retries = 0

    def initialize_ytmusic(self):
        """Initialize YouTube Music API with error handling."""
        try:
            headers_path = Path(self.config.HEADERS_FILE)
            if not headers_path.exists():
                self.logger.error(f"Authentication file '{self.config.HEADERS_FILE}' not found. "
                                  "Please run 'ytmusicapi headers_auth' to generate it.")
                return False
                
            self.ytmusic = YTMusic(str(headers_path))
            self.logger.info("YouTube Music API initialized.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize YouTube Music API: {e}")
            self.logger.error("Check your network connection or the headers_auth.json file.")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during YTMusic initialization: {e}")
            return False
    
    def get_playing_track(self) -> Optional[TrackInfo]:
        """Gets the currently playing track from your YouTube Music history."""
        try:
            history = self.ytmusic.get_history()
            
            if not history:
                self.logger.debug("No listening history found.")
                return None
            
            latest_track = history[0]
            
            track_id = latest_track.get('videoId')
            if not track_id:
                return None
            
            if track_id != self.last_track_id:
                self.last_track_id = track_id
                self.start_timestamp = time.time()
                self.logger.info(f"New track detected: {latest_track.get('title')}")
            
            title = latest_track.get('title')
            artists = latest_track.get('artists')
            artist_name = ", ".join([artist['name'] for artist in artists]) if artists else "Unknown Artist"
            
            artwork_url = latest_track.get('thumbnails', [{}])[-1].get('url') if latest_track.get('thumbnails') else None
            
            track_url = f"https://music.youtube.com/watch?v={track_id}"

            return TrackInfo(
                title=title,
                artist=artist_name,
                url=track_url,
                artwork=artwork_url
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get track from API: {e}")
            return None

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
        
    def update_presence(self, track_info: TrackInfo):
        """Update Discord Rich Presence with error handling."""
        if not self.rpc:
            return False
        
        try:
            rpc_data = {
                "details": f"🎵 {track_info.title}",
                "state": f"👤 {track_info.artist}",
                "start": int(self.start_timestamp),
                "buttons": [{"label": "🎧 Listen on YouTube Music", "url": track_info.url}]
            }
            
            if track_info.artwork:
                rpc_data["large_image"] = track_info.artwork.split("=")[0]
                rpc_data["large_text"] = f"{track_info.title} — {track_info.artist}"
                rpc_data["small_image"] = "youtubemusic"
                rpc_data["small_text"] = "YouTube Music"
            else:
                rpc_data["large_image"] = "youtubemusic"
            
            self.rpc.update(**rpc_data)
            self.logger.info(f"🎶 Now Playing: {track_info.title} by {track_info.artist}")
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
        self.logger.info("🎵 Starting YouTube Music Discord RPC (API Mode)")
        
        if not self.initialize_ytmusic():
            self.logger.error("Failed to initialize YTMusic API. Exiting.")
            return
        
        if not self.connect_discord():
            self.logger.error("Could not connect to Discord. Exiting.")
            return
        
        try:
            while True:
                if self.connection_retries > 0 and not self.connect_discord():
                    self.logger.warning("Failed to reconnect to Discord, retrying later...")
                    time.sleep(self.config.RETRY_DELAY)
                    continue

                track_info = self.get_playing_track()
                
                if track_info and track_info.title and track_info.artist:
                    if self.update_presence(track_info):
                        pass
                else:
                    if self.last_track_id is not None:
                        self.clear_presence()
                        self.last_track_id = None
                
                time.sleep(self.config.UPDATE_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Shutting down...")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        if self.rpc:
            self.clear_presence()
            try:
                self.rpc.close()
            except Exception:
                pass
        
        self.logger.info("✅ Cleanup completed")
    
def main():
    """Main entry point."""
    config = Config()
    rpc = YouTubeMusicRPC(config)
    rpc.run()

if __name__ == "__main__":
    main()
