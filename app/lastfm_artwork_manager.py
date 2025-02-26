# lastfm_artwork_manager.py
# This file contains the core functionality extracted from the original script

import os
import re
import json
import logging
import time
import hashlib
from functools import wraps, lru_cache
from urllib.parse import urlencode
from pathlib import Path

import requests
import spotipy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# ---------------------------- Configuration ---------------------------- #

class ConfigManager:
    """Manages application configuration and credentials."""
    
    def __init__(self):
        # Load environment variables from .env file if present
        load_dotenv()
        
        # Default configuration file
        self.config_dir = Path.home() / ".lastfm_artwork_manager"
        self.config_file = self.config_dir / "config.json"
        self.session_file = self.config_dir / "session.json"
        
        # Default configuration
        self.config = {
            "credentials": {
                "SPOTIPY_CLIENT_ID": os.getenv('SPOTIPY_CLIENT_ID', ''),
                "SPOTIPY_CLIENT_SECRET": os.getenv('SPOTIPY_CLIENT_SECRET', ''),
                "LASTFM_API_KEY": os.getenv('LASTFM_API_KEY', ''),
                "LASTFM_API_SECRET": os.getenv('LASTFM_API_SECRET', ''),
                "LASTFM_EMAIL": os.getenv('LASTFM_EMAIL', ''),
                "LASTFM_PASSWORD": os.getenv('LASTFM_PASSWORD', '')
            },
            "settings": {
                "BROWSER": os.getenv('BROWSER', 'firefox'),
                "WAIT_TIME": 5,
                "UPLOAD_DELAY": 8,
                "MAX_RETRIES": 3,
                "RETRY_DELAY": 5,
                "HEADLESS": True  # Default to headless for server
            },
            "paths": {
                "JSON_FILE_PATH": 'no_artwork_albums.json',
                "ARTWORK_FOLDER": 'artworkup',
                "LOG_FILE": 'lastfm_artwork_manager.log'
            }
        }
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(exist_ok=True)
        
        # Load existing configuration if available
        self.load_config()
    
    def load_config(self):
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)
                    # Update config with saved values, preserving defaults for any missing keys
                    for section in self.config:
                        if section in saved_config:
                            self.config[section].update(saved_config[section])
            except Exception as e:
                logger.warning(f"Could not load configuration file: {e}")
    
    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.warning(f"Could not save configuration: {e}")
    
    def save_session(self, data):
        """Save session data for resuming later."""
        try:
            with open(self.session_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.warning(f"Could not save session data: {e}")
    
    def load_session(self):
        """Load session data if available."""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load session data: {e}")
        return None
    
    def clear_session(self):
        """Clear session data."""
        if self.session_file.exists():
            try:
                self.session_file.unlink()
            except Exception as e:
                logger.warning(f"Could not clear session data: {e}")

# ---------------------------- Decorators ---------------------------- #

def rate_limited(max_per_second):
    """Decorator to limit function calls to a maximum rate."""
    min_interval = 1.0 / float(max_per_second)
    
    def decorator(func):
        last_time_called = [0.0]
        
        @wraps(func)
        def rate_limited_function(*args, **kwargs):
            elapsed = time.perf_counter() - last_time_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_time_called[0] = time.perf_counter()
            return ret
        
        return rate_limited_function
    
    return decorator

# ---------------------------- Classes ---------------------------- #

class LastFMAPIAuth:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://ws.audioscrobbler.com/2.0/"
        logger.info("Initialized LastFMAPIAuth.")
    
    @rate_limited(4)  # Limit to 4 calls per second
    def check_album_artwork(self, artist, album):
        """Check if an album has artwork on Last.fm."""
        params = {
            'method': 'album.getInfo',
            'api_key': self.api_key,
            'artist': artist,
            'album': album,
            'format': 'json'
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'album' in data and 'image' in data['album']:
                images = data['album']['image']
                has_artwork = any(img['#text'] for img in images)
                
                return {
                    'artwork_exists': has_artwork,
                    'lastfm_url': data['album'].get('url')
                }
            
            return {'artwork_exists': False}
            
        except requests.RequestException as e:
            logger.error(f"Error making API request: {e}")
            return {'artwork_exists': False, 'error': str(e)}
    
    def generate_signature(self, params):
        """Generate API signature for authenticated requests."""
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        sig_string = ''.join([f"{k}{v}" for k, v in sorted_params])
        sig_string += self.api_secret
        return hashlib.md5(sig_string.encode('utf-8')).hexdigest()
    
    @rate_limited(2)
    def get_user_albums(self, username, source, period=None):
        """Fetch albums from a Last.fm user's data source."""
        params = {
            'method': '',
            'user': username,
            'api_key': self.api_key,
            'limit': 200,
            'format': 'json'
        }
        
        if source == 'recenttracks':
            params['method'] = 'user.getrecenttracks'
        elif source == 'lovedtracks':
            params['method'] = 'user.getlovedtracks'
        elif source == 'topalbums':
            params['method'] = 'user.gettopalbums'
            if period:
                params['period'] = period
        else:
            raise ValueError("Invalid source specified.")
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching {source} for user {username}: {e}")
            return None
    
    def get_albums_from_lastfm_data(self, lastfm_data, source):
        """Extract album information from Last.fm API response."""
        albums = []
        
        if source == 'recenttracks':
            tracks = lastfm_data.get('recenttracks', {}).get('track', [])
        elif source == 'lovedtracks':
            tracks = lastfm_data.get('lovedtracks', {}).get('track', [])
        else:  # topalbums
            tracks = lastfm_data.get('topalbums', {}).get('album', [])
        
        for track in tracks:
            album_name = track.get('album', {}).get('#text', track.get('name', ''))
            artist_name = track.get('artist', {}).get('#text', track.get('artist', {}).get('name', ''))
            if album_name and artist_name:
                albums.append({
                    'artist_name': artist_name,
                    'album_title': album_name
                })
        
        return albums

# ---------------------------- Helper Functions ---------------------------- #

def extract_id_from_url(url, type_):
    """Extract Spotify ID from URL."""
    pattern = rf"https?://open\.spotify\.com/{type_}/([a-zA-Z0-9]+)(\?.*)?"
    match = re.match(pattern, url)
    if not match:
        raise ValueError(f"Invalid Spotify {type_.capitalize()} URL format.")
    return match.group(1)

def get_album_info(sp, album_url):
    """Get album information from Spotify."""
    album_id = extract_id_from_url(album_url, "album")
    album_info = sp.album(album_id)
    tracks = album_info['tracks']['items']
    
    # Extract the largest image URL available
    album_art_url = album_info['images'][0]['url'] if album_info['images'] else None
    
    return [{
        'track_title': track['name'],
        'artist_name': track['artists'][0]['name'],
        'album_title': album_info['name'],
        'album_art_url': album_art_url
    } for track in tracks]

def get_playlist_info(sp, playlist_url):
    """Get playlist information from Spotify."""
    playlist_id = extract_id_from_url(playlist_url, "playlist")
    albums = set()
    track_details = []
    
    # Fetch the first page of tracks
    results = sp.playlist_tracks(playlist_id, limit=100)
    
    # Process tracks
    while results:
        for item in results['items']:
            track = item['track']
            if not track:
                continue  # Skip if track info is missing
            album_id = track['album']['id']
            if album_id not in albums:
                albums.add(album_id)
                album_art_url = track['album']['images'][0]['url'] if track['album']['images'] else None
                track_details.append({
                    'track_title': track['name'],
                    'artist_name': track['artists'][0]['name'],
                    'album_title': track['album']['name'],
                    'album_art_url': album_art_url
                })
                
        # Check if there is a next page
        if results['next']:
            results = sp.next(results)
        else:
            results = None
    
    logger.info(f"Found {len(albums)} unique albums in playlist")
    return track_details

def get_artist_info(sp, artist_url):
    """Get artist's albums from Spotify."""
    artist_id = extract_id_from_url(artist_url, "artist")
    albums = {}
    
    # Get artist name first
    artist_data = sp.artist(artist_id)
    artist_name = artist_data['name']
    
    # Process albums
    results = sp.artist_albums(artist_id, album_type='album,single', country='US', limit=50)
    
    while results:
        for album in results['items']:
            album_id = album['id']
            if album_id not in albums:
                album_art_url = album['images'][0]['url'] if album['images'] else None
                albums[album_id] = {
                    'track_title': '',  # No track title at this level
                    'artist_name': album['artists'][0]['name'],
                    'album_title': album['name'],
                    'album_art_url': album_art_url,
                    'album_id': album_id
                }
                
        # Check if there is a next page
        if results['next']:
            results = sp.next(results)
        else:
            results = None
    
    logger.info(f"Found {len(albums)} albums for {artist_name}")
    # Convert dictionary to list
    return list(albums.values())

def sanitize_filename(name):
    """Sanitize the filename by removing or replacing invalid characters."""
    return re.sub(r'[\\/:"*?<>|]+', '_', name)

@lru_cache(maxsize=128)
def search_spotify_album(sp, artist_name, album_title):
    """Search for album artwork on Spotify."""
    query = f"artist:{artist_name} album:{album_title}"
    
    try:
        result = sp.search(q=query, type='album', limit=1)
        albums = result.get('albums', {}).get('items', [])
        if albums:
            album = albums[0]
            return album['images'][0]['url'] if album['images'] else None
        return None
    except Exception as e:
        logger.error(f"Spotify API error for '{album_title}' by '{artist_name}': {e}")
        return None

@lru_cache(maxsize=128)
def search_itunes_album(album_title, artist_name):
    """Search for album artwork on iTunes."""
    query = {
        'term': f"{album_title} {artist_name}",
        'entity': 'album',
        'limit': 1,
    }
    url = 'https://itunes.apple.com/search?' + urlencode(query)
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['resultCount'] > 0:
            result = data['results'][0]
            artwork_url = result.get('artworkUrl100')
            if artwork_url:
                # Modify the artwork URL to get the largest available image
                return re.sub(r'\/[0-9]+x[0-9]+bb.jpg$', '/100000x100000bb.jpg', artwork_url)
    except requests.RequestException as e:
        logger.warning(f"Error searching iTunes for '{album_title}' by {artist_name}: {e}")
    
    return None

def get_album_art_url(sp, artist_name, album_title):
    """Get album art URL from Spotify or iTunes."""
    # First try Spotify
    album_art_url = search_spotify_album(sp, artist_name, album_title)
    if album_art_url:
        return album_art_url
    
    # Try iTunes if Spotify fails
    return search_itunes_album(album_title, artist_name)

def download_image(url, save_path):
    """Download an image from a URL with retry logic."""
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            
            logger.info(f"Downloaded image to {save_path}")
            return True
        
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt+1} - Failed to download image: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    logger.error(f"Failed to download image from {url} after {max_retries} attempts")
    return False

def setup_webdriver():
    """Set up the Selenium WebDriver."""
    # Always use Firefox for headless server operation
    options = FirefoxOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    try:
        driver = webdriver.Firefox(options=options)
        logger.info("Initialized Firefox WebDriver in headless mode")
        return driver
    except WebDriverException as e:
        logger.error(f"Error initializing Firefox WebDriver: {e}")
        
        # Try Chrome as fallback
        try:
            options = ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            logger.info("Initialized Chrome WebDriver in headless mode")
            return driver
        except WebDriverException as chrome_e:
            logger.error(f"Error initializing Chrome WebDriver: {chrome_e}")
            raise

def perform_login(driver, email, password, selectors):
    """Log in to Last.fm with retry logic."""
    max_retries = 3
    retry_delay = 5
    wait_time = 10
    
    for attempt in range(max_retries):
        try:
            driver.get("https://www.last.fm/login")
            logger.info("Navigated to Last.fm login page")
            
            wait = WebDriverWait(driver, wait_time)
            
            # Enter email
            username_field = wait.until(
                EC.visibility_of_element_located((By.ID, selectors['username_or_email']))
            )
            username_field.clear()
            username_field.send_keys(email)
            
            # Enter password
            password_field = wait.until(
                EC.visibility_of_element_located((By.ID, selectors['password']))
            )
            password_field.clear()
            password_field.send_keys(password)
            
            # Click login button
            login_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.form-submit button'))
            )
            login_button.click()
            
            # Verify login success
            wait.until(
                EC.presence_of_element_located((By.ID, selectors['post_login']))
            )
            
            logger.info("Login successful")
            return True
            
        except (TimeoutException, NoSuchElementException, Exception) as e:
            logger.warning(f"Attempt {attempt+1} - Login error: {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying login in {retry_delay} seconds...")
                time.sleep(retry_delay)
    
    logger.error("Login failed after maximum retries")
    return False

def perform_upload(driver, album_entry, image_path, upload_url, selectors):
    """Upload album artwork to Last.fm with retry logic."""
    max_retries = 3
    retry_delay = 5
    wait_time = 10
    
    for attempt in range(max_retries):
        try:
            driver.get(upload_url)
            
            wait = WebDriverWait(driver, wait_time)
            
            # Upload image file
            file_input = wait.until(
                EC.presence_of_element_located((By.XPATH, selectors['file_input']))
            )
            file_input.send_keys(os.path.abspath(image_path))
            
            # Enter album title
            title_input = wait.until(
                EC.presence_of_element_located((By.NAME, selectors['album_title']))
            )
            title_input.clear()
            title_input.send_keys(album_entry['album'])
            
            # Click upload button
            upload_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selectors['upload_button']))
            )
            upload_button.click()
            
            # Verify upload success
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selectors['upload_success']))
            )
            
            logger.info(f"Successfully uploaded image for '{album_entry['album']}' by '{album_entry['artist']}'")
            return True
            
        except (TimeoutException, NoSuchElementException, 
                ElementClickInterceptedException, StaleElementReferenceException, Exception) as e:
            logger.warning(f"Attempt {attempt+1} - Upload error: {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying upload in {retry_delay} seconds...")
                time.sleep(retry_delay)
    
    logger.error(f"Upload failed for '{album_entry['album']}' after maximum retries")
    return False
