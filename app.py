from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import json
import threading
import time
import logging
from pathlib import Path
import queue

# Import the core functionality from the original script
from lastfm_artwork_manager import (
    ConfigManager, LastFMAPIAuth, get_album_info, get_playlist_info, 
    get_artist_info, setup_webdriver, perform_login, perform_upload,
    download_image, sanitize_filename, search_spotify_album, search_itunes_album,
    get_album_art_url
)
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize configuration manager
config_manager = ConfigManager()

# Queue for job status updates
job_status_queue = queue.Queue()

# Dictionary to store job status
jobs = {}

def process_albums(job_id, source_type, source_value, lastfm_username=None, lastfm_sources=None, 
                  check_only=False, lastfm_email=None, lastfm_password=None):
    """Process albums in a background thread"""
    try:
        jobs[job_id]['status'] = 'running'
        jobs[job_id]['progress'] = 0
        jobs[job_id]['phase'] = 'searching'  # Add phase tracking
        jobs[job_id]['message'] = 'Initializing...'
        
        # Extract credentials from config
        credentials = config_manager.config["credentials"]
        SPOTIPY_CLIENT_ID = credentials["SPOTIPY_CLIENT_ID"]
        SPOTIPY_CLIENT_SECRET = credentials["SPOTIPY_CLIENT_SECRET"]
        LASTFM_API_KEY = credentials["LASTFM_API_KEY"]
        LASTFM_API_SECRET = credentials["LASTFM_API_SECRET"]
        
        # Initialize Spotify client
        sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
            client_id=SPOTIPY_CLIENT_ID, 
            client_secret=SPOTIPY_CLIENT_SECRET
        ))
        
        # Initialize Last.fm API client
        lastfm = LastFMAPIAuth(LASTFM_API_KEY, LASTFM_API_SECRET)
        
        # Fetch album records based on input type
        records = []
        
        jobs[job_id]['message'] = f'Fetching data from {source_type}...'
        records = [{'artist_name': 'Artist 1', 'album_title': 'Album 1'}, {'artist_name': 'Artist 2', 'album_title': 'Album 2'}]
        
        if source_type == "album":
            records = get_album_info(sp, source_value)
            
        elif source_type == "playlist":
            records = get_playlist_info(sp, source_value)
            
        elif source_type == "artist":
            records = get_artist_info(sp, source_value)
            
        elif source_type == "lastfm_username":
            all_albums = []
            
            for source in lastfm_sources:
                source_type = source['type']
                period = source.get('period')
                
                jobs[job_id]['message'] = f'Fetching {source_type} for user {lastfm_username}...'
                
                lastfm_data = lastfm.get_user_albums(lastfm_username, source_type, period)
                
                if lastfm_data:
                    albums = lastfm.get_albums_from_lastfm_data(lastfm_data, source_type)
                    all_albums.extend(albums)
            
            # Remove duplicates
            unique_albums = {f"{album['artist_name']} - {album['album_title']}": album for album in all_albums}
            records = list(unique_albums.values())
        
        jobs[job_id]['message'] = f'Found {len(records)} albums. Checking for missing artwork...'
        jobs[job_id]['total_albums'] = len(records)
        
        # Check for missing artwork
        no_artwork_urls = []
        
        for i, record in enumerate(records):
            # Check for missing fields
            if not record.get('artist_name') or not record.get('album_title') or not record.get('album_art_url'):
                logger.warning(f"Missing data in entry: {record}")
                continue  # Skip this entry
                
            # Optional: Handle missing track_title gracefully
            track_title = record.get('track_title', 'Unknown Track')  # Use a default value if track_title is missing
    
            # Process the entry
            artist_name = record['artist_name']
            album_title = record['album_title']
            album_art_url = record['album_art_url']

            # Example: Log the entry being processed
            logger.info(f"Processing album: {artist_name} - {album_title}")
            
            artwork_info = lastfm.check_album_artwork(artist_name, album_title)
            
            if not artwork_info.get('artwork_exists', False):
                # Try to find album art URL
                album_art_url = record.get('album_art_url')
                
                if not album_art_url:
                    # Try to get album art from Spotify and iTunes
                    album_art_url = get_album_art_url(sp, artist_name, album_title)
                    
                if album_art_url and artwork_info.get('lastfm_url'):
                    no_artwork_entry = {
                        'artist': artist_name,
                        'album': album_title,
                        'album_art_url': album_art_url,
                        'lastfm_url': artwork_info.get('lastfm_url')
                    }
                    no_artwork_urls.append(record)
            
            # Update progress
            progress = int((i + 1) / len(records) * 100)
            jobs[job_id]['progress'] = progress
            jobs[job_id]['message'] = f'Checking artwork: {i+1}/{len(records)}'
        
        # Save results to JSON file
        if no_artwork_urls:
            artwork_folder = config_manager.config["paths"]["ARTWORK_FOLDER"]
            json_file_path = f"{job_id}_no_artwork_albums.json"
            
            if not os.path.exists(artwork_folder):
                os.makedirs(artwork_folder)
                
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(no_artwork_urls, f, ensure_ascii=False, indent=4)
            
            jobs[job_id]['missing_artwork'] = no_artwork_urls
            jobs[job_id]['message'] = f'Found {len(no_artwork_urls)} albums missing artwork'
        else:
            jobs[job_id]['missing_artwork'] = []
            jobs[job_id]['message'] = 'All albums have artwork!'
            jobs[job_id]['status'] = 'completed'
            return
        
        # Exit if check-only mode
        if check_only:
            jobs[job_id]['message'] = f'Check completed. Found {len(no_artwork_urls)} albums missing artwork.'
            jobs[job_id]['status'] = 'completed'
            return
        
        # Upload artwork if credentials are provided
        if lastfm_email and lastfm_password:
            jobs[job_id]['message'] = 'Setting up browser for uploads...'
            
            # Define element selectors for Last.fm
            selectors = {
                'username_or_email': 'id_username_or_email',
                'password': 'id_password',
                'post_login': 'top-artists',
                'file_input': '//input[@type="file"]',
                'album_title': 'title',
                'upload_button': '.btn-primary',
                'upload_success': '.gallery-image-uploaded-by'
            }
            
            # Force headless mode for server
            config_manager.config["settings"]["HEADLESS"] = True
            
            # Initialize WebDriver
            driver = setup_webdriver()
            
            try:
                # Perform login
                jobs[job_id]['message'] = 'Logging in to Last.fm...'
                login_success = perform_login(driver, lastfm_email, lastfm_password, selectors)
                
                if not login_success:
                    jobs[job_id]['message'] = 'Login failed'
                    jobs[job_id]['status'] = 'failed'
                    driver.quit()
                    return
                
                # Process each album for upload
                successful_uploads = 0
                failed_uploads = 0
                jobs[job_id]['phase'] = 'uploading'
                jobs[job_id]['progress'] = 0                
                jobs[job_id]['message'] = 'Starting uploads...'
                
                for i, album_entry in enumerate(no_artwork_urls):
                    artist = album_entry.get('artist')
                    album = album_entry.get('album')
                    album_art_url = album_entry.get('album_art_url')
                    lastfm_url = album_entry.get('lastfm_url')
                    
                    if not all([artist, album, album_art_url, lastfm_url]):
                        logger.warning(f"Missing data in entry: {album_entry}")
                        continue
                    
                    # Prepare upload URL
                    upload_url = lastfm_url.rstrip('/') + '/+images/upload'
                    
                    # Prepare image path
                    filename = f"{sanitize_filename(artist)} - {sanitize_filename(album)}.jpg"
                    image_path = os.path.join(config_manager.config["paths"]["ARTWORK_FOLDER"], filename)
                    
                    jobs[job_id]['message'] = f'Downloading artwork for "{artist} - {album}"'
                    
                    # Download the album art image if it doesn't exist
                    if not os.path.exists(image_path):
                        success = download_image(album_art_url, image_path)
                        if not success:
                            logger.error(f"Failed to download image for '{album}'")
                            failed_uploads += 1
                            continue
                    
                    jobs[job_id]['message'] = f'Uploading artwork for "{album["artist_name"]} - {album["album_title"]}"'
            
                    
                    # Upload the image
                    upload_success = perform_upload(driver, album_entry, image_path, upload_url, selectors)
                    
                    if upload_success:
                        successful_uploads += 1
                        logger.info(f"Upload successful for '{artist} - {album}'")
                    else:
                        failed_uploads += 1
                        logger.error(f"Upload failed for '{artist} - {album}'")
                    
                    # Update progress
                    jobs[job_id]['progress'] = int((i + 1) / len(no_artwork_urls) * 100)
                    jobs[job_id]['progress'] = progress
                    
                    # Delay between uploads to prevent rate limiting
                    time.sleep(config_manager.config["settings"]["UPLOAD_DELAY"])
                
                jobs[job_id]['successful_uploads'] = successful_uploads
                jobs[job_id]['failed_uploads'] = failed_uploads
                jobs[job_id]['message'] = f'Upload completed. Successful: {successful_uploads}, Failed: {failed_uploads}'
                jobs[job_id]['status'] = 'completed'
                
            except Exception as e:
                logger.error(f"Error during upload process: {e}")
                jobs[job_id]['message'] = f'Error during upload process: {str(e)}'
                jobs[job_id]['status'] = 'failed'
            finally:
                # Close the WebDriver
                driver.quit()
                logger.info("WebDriver closed")
        else:
            jobs[job_id]['message'] = 'Check completed. Last.fm credentials not provided for upload.'
            jobs[job_id]['status'] = 'completed'
            
    except Exception as e:
        logger.error(f"Error in job {job_id}: {str(e)}")
        jobs[job_id]['message'] = f'Error: {str(e)}'
        jobs[job_id]['status'] = 'failed'

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify({
        'spotify_client_id': config_manager.config["credentials"]["SPOTIPY_CLIENT_ID"] != '',
        'spotify_client_secret': config_manager.config["credentials"]["SPOTIPY_CLIENT_SECRET"] != '',
        'lastfm_api_key': config_manager.config["credentials"]["LASTFM_API_KEY"] != '',
        'lastfm_api_secret': config_manager.config["credentials"]["LASTFM_API_SECRET"] != '',
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    data = request.json
    
    if 'spotify_client_id' in data:
        config_manager.config["credentials"]["SPOTIPY_CLIENT_ID"] = data['spotify_client_id']
    
    if 'spotify_client_secret' in data:
        config_manager.config["credentials"]["SPOTIPY_CLIENT_SECRET"] = data['spotify_client_secret']
    
    if 'lastfm_api_key' in data:
        config_manager.config["credentials"]["LASTFM_API_KEY"] = data['lastfm_api_key']
    
    if 'lastfm_api_secret' in data:
        config_manager.config["credentials"]["LASTFM_API_SECRET"] = data['lastfm_api_secret']
    
    config_manager.save_config()
    return jsonify({'status': 'success'})

def extract_spotify_name(url):
    """
    Extracts a human-readable name from a Spotify URL.
    Example: "https://open.spotify.com/album/12345" -> "Album 12345"
    """
    try:
        parts = url.split('/')
        if len(parts) > 0:
            return parts[-1].replace('-', ' ').title()
    except Exception as e:
        logger.warning(f"Error extracting name from URL: {url} - {e}")
    return "Unknown"


@app.route('/api/start-job', methods=['POST'])
def start_job():
    """Start a new job"""
    data = request.json

    source_type = data.get('source_type')
    source_value = data.get('source_value')
    check_only = data.get('check_only', False)
    lastfm_email = data.get('lastfm_email')
    lastfm_password = data.get('lastfm_password')
    lastfm_username = data.get('lastfm_username')
    lastfm_sources = data.get('lastfm_sources', [])

    # Generate a descriptive job name
    if source_type == "album":
        job_name = f"Spotify Album: {extract_spotify_name(source_value)}"
    elif source_type == "playlist":
        job_name = f"Spotify Playlist: {extract_spotify_name(source_value)}"
    elif source_type == "artist":
        job_name = f"Spotify Artist: {extract_spotify_name(source_value)}"
    elif source_type == "lastfm_username":
        job_name = f"Last.fm User: {lastfm_username}"
    else:
        job_name = "Unknown Job"

    # Generate a unique job ID
    job_id = f"job_{int(time.time())}"

    # Initialize job status
    jobs[job_id] = {
        'id': job_id,
        'name': job_name,  # Add the descriptive name here
        'status': 'initializing',
        'progress': 0,
        'message': 'Job created',
        'source_type': source_type,
        'source_value': source_value,
        'check_only': check_only,
        'start_time': time.time()
    }

    # Start processing in a background thread
    thread = threading.Thread(
        target=process_albums,
        args=(job_id, source_type, source_value),
        kwargs={
            'lastfm_username': lastfm_username,
            'lastfm_sources': lastfm_sources,
            'check_only': check_only,
            'lastfm_email': lastfm_email,
            'lastfm_password': lastfm_password
        }
    )
    thread.daemon = True
    thread.start()

    return jsonify({'job_id': job_id})

@app.route('/api/job-status/<job_id>', methods=['GET'])
def job_status(job_id):
    """Get the status of a job"""
    if job_id in jobs:
        # Return a copy of the job status without sensitive information
        job_status = jobs[job_id].copy()
        if 'lastfm_password' in job_status:
            del job_status['lastfm_password']
        return jsonify(job_status)
    else:
        return jsonify({'status': 'not_found'}), 404

@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    """List all jobs"""
    # Return a list of jobs without sensitive information
    job_list = []
    for job_id, job in jobs.items():
        job_copy = job.copy()
        if 'lastfm_password' in job_copy:
            del job_copy['lastfm_password']
        job_list.append(job_copy)
    
    return jsonify(job_list)

@app.route('/api/clear-job/<job_id>', methods=['DELETE'])
def clear_job(job_id):
    """Clear a completed or failed job"""
    if job_id in jobs:
        if jobs[job_id]['status'] in ['completed', 'failed']:
            del jobs[job_id]
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Cannot clear a running job'}), 400
    else:
        return jsonify({'status': 'not_found'}), 404

if __name__ == '__main__':
    # Create necessary directories
    artwork_folder = config_manager.config["paths"]["ARTWORK_FOLDER"]
    if not os.path.exists(artwork_folder):
        os.makedirs(artwork_folder)
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
