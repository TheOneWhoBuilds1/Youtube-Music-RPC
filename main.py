import time
import re
import logging
import json
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pypresence import Presence, DiscordNotFound, InvalidPipe
from ytmusicapi import YTMusic, OAuthCredentials

# Configuration
@dataclass
class Config:
    """Configuration for the Discord Rich Presence script."""
    CLIENT_ID: str = 'YOUR_DISCORD_APPLICATION_ID'
    UPDATE_INTERVAL: float = 2.0
    LOG_LEVEL: str = 'INFO'
    OAUTH_FILE: str = 'oauth.json'
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 5.0
    
    # YouTube Music OAuth credentials
    # You need to get these from Google Cloud Console
    YOUTUBE_CLIENT_ID: str = 'YOUR_GOOGLE_CLIENT_ID'
    YOUTUBE_CLIENT_SECRET: str = 'YOUR_GOOGLE_CLIENT_SECRET'

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

class OAuthManager:
    """Handles OAuth authentication for YouTube Music."""
    
    def __init__(self, oauth_file: str, client_id: str, client_secret: str, logger):
        self.oauth_file = Path(oauth_file)
        self.client_id = client_id
        self.client_secret = client_secret
        self.logger = logger
        
    def load_oauth_credentials(self) -> Optional[Dict[str, Any]]:
        """Load OAuth credentials from file."""
        try:
            if self.oauth_file.exists():
                with open(self.oauth_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load OAuth credentials: {e}")
        return None
    
    def save_oauth_credentials(self, credentials: Dict[str, Any]):
        """Save OAuth credentials to file."""
        try:
            with open(self.oauth_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            self.logger.info(f"OAuth credentials saved to {self.oauth_file}")
        except Exception as e:
            self.logger.error(f"Failed to save OAuth credentials: {e}")
    
    def setup_oauth(self) -> bool:
        """Setup OAuth authentication interactively."""
        if not self.client_id or not self.client_secret:
            self.logger.error("YouTube Music OAuth credentials not configured!")
            self.logger.error("Please set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in the Config class")
            self.logger.error("Get these from Google Cloud Console: https://console.cloud.google.com/")
            return False
            
        self.logger.info("Setting up OAuth authentication...")
        self.logger.info("Please follow the instructions to authenticate with YouTube Music:")
        
        try:
            # Create OAuth credentials object
            oauth_creds = OAuthCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Initialize YTMusic with OAuth credentials to trigger the auth flow
            ytmusic_temp = YTMusic(oauth_credentials=oauth_creds)
            
            # If we get here, authentication was successful
            # The oauth tokens should be automatically saved
            self.logger.info("✅ OAuth setup completed successfully!")
            return True
                
        except Exception as e:
            self.logger.error(f"OAuth setup failed: {e}")
            self.logger.info("Please try the following steps:")
            self.logger.info("1. Make sure you have the latest version of ytmusicapi: pip install --upgrade ytmusicapi")
            self.logger.info("2. Ensure your client_id and client_secret are correct")
            self.logger.info("3. Make sure the YouTube Data API v3 is enabled in your Google Cloud project")
            self.logger.info("4. Restart the application")
            return False

class YouTubeMusicRPC:
    """Main class for YouTube Music Discord Rich Presence."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logging(config.LOG_LEVEL)
        self.rpc: Optional[Presence] = None
        self.ytmusic: Optional[YTMusic] = None
        self.oauth_manager = OAuthManager(
            config.OAUTH_FILE, 
            config.YOUTUBE_CLIENT_ID, 
            config.YOUTUBE_CLIENT_SECRET, 
            self.logger
        )
        
        self.last_track_id: Optional[str] = None
        self.start_timestamp: Optional[int] = None
        self.connection_retries = 0

    def initialize_ytmusic(self):
        """Initialize YouTube Music API with OAuth authentication."""
        try:
            # Check if OAuth credentials are configured
            if not self.config.YOUTUBE_CLIENT_ID or not self.config.YOUTUBE_CLIENT_SECRET:
                self.logger.error("YouTube Music OAuth credentials not configured!")
                self.logger.error("Please set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in the Config class")
                self.logger.error("Get these from Google Cloud Console: https://console.cloud.google.com/")
                return False
            
            # Try to initialize YTMusic with OAuth
            try:
                oauth_creds = OAuthCredentials(
                    client_id=self.config.YOUTUBE_CLIENT_ID,
                    client_secret=self.config.YOUTUBE_CLIENT_SECRET
                )
                
                # Try to load existing oauth.json if it exists
                if self.oauth_manager.oauth_file.exists():
                    self.ytmusic = YTMusic(
                        auth=str(self.oauth_manager.oauth_file),
                        oauth_credentials=oauth_creds
                    )
                else:
                    # First time setup - this will trigger the OAuth flow
                    self.logger.info("First time setup - starting OAuth authentication...")
                    self.ytmusic = YTMusic(oauth_credentials=oauth_creds)
                
                # Test the connection by trying to get history
                test_history = self.ytmusic.get_history()
                self.logger.info("✅ YouTube Music API initialized with OAuth")
                return True
                
            except Exception as auth_error:
                self.logger.warning(f"Authentication failed: {auth_error}")
                self.logger.info("This might be your first time using OAuth or tokens may have expired")
                self.logger.info("Starting fresh OAuth setup...")
                
                # Remove old credentials and try fresh setup
                if self.oauth_manager.oauth_file.exists():
                    self.oauth_manager.oauth_file.unlink()
                
                if self.oauth_manager.setup_oauth():
                    # Try again with fresh OAuth
                    oauth_creds = OAuthCredentials(
                        client_id=self.config.YOUTUBE_CLIENT_ID,
                        client_secret=self.config.YOUTUBE_CLIENT_SECRET
                    )
                    
                    self.ytmusic = YTMusic(oauth_credentials=oauth_creds)
                    self.logger.info("✅ YouTube Music API initialized with fresh OAuth")
                    return True
                else:
                    return False
            
        except Exception as e:
            self.logger.error(f"Failed to initialize YouTube Music API: {e}")
            self.logger.error("Please check your internet connection and OAuth credentials")
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
            
            # If we get authentication errors, try to re-initialize
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                self.logger.warning("Authentication error detected, attempting to re-authenticate...")
                if self.initialize_ytmusic():
                    return self.get_playing_track()
            
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
        self.logger.info("🎵 Starting YouTube Music Discord RPC (OAuth Mode)")
        
        if not self.initialize_ytmusic():
            self.logger.error("Failed to initialize YTMusic API with OAuth. Exiting.")
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
