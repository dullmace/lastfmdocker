# **CURRENTLY IN DEVELOPMENT. CREDENTIALS UNSECURE**

# **Last.fm Artwork Manager**

![Last.fm Artwork Manager](https://img.shields.io/badge/Last.fm-Artwork%20Manager-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.9-blue?style=flat-square)
![Flask](https://img.shields.io/badge/Flask-2.0.3-green?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue?style=flat-square)

## **Overview**
The **Last.fm Artwork Manager** is a web application that helps users find and upload missing album artwork to Last.fm. It integrates with Spotify and Last.fm APIs to fetch album data and uses Selenium to automate artwork uploads. The app is built with Python, Flask, and Docker for easy deployment.

---

## **Features**
- **Start Jobs**: Fetch album data from Spotify or Last.fm and identify missing artwork.
- **Active Jobs**: Monitor the progress of ongoing jobs in real-time.
- **Settings**: Configure API credentials for Spotify and Last.fm.
- **Dynamic Artwork Upload**: Automatically upload missing artwork to Last.fm using Selenium.
- **Dockerized**: Easily deploy the application using Docker.

---

## **Table of Contents**
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Contributing](#contributing)
- [License](#license)

---

## **Installation**

### **1. Clone the Repository**
```bash
git clone https://github.com/<your-username>/lastfm-artwork-manager.git
cd lastfm-artwork-manager
```

### **2. Install Dependencies**
#### **Option 1: Local Setup**
1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

#### **Option 2: Docker Setup**
1. Build the Docker image:
   ```bash
   docker build -t lastfm-artwork-manager .
   ```
2. Run the Docker container:
   ```bash
   docker run -p 5000:5000 lastfm-artwork-manager
   ```

---

## **Usage**

### **1. Start the Application**
#### **Local Setup**
Run the Flask app:
```bash
python app.py
```
The app will be available at `http://localhost:5000`.

#### **Docker Setup**
Run the container:
```bash
docker run -p 5000:5000 lastfm-artwork-manager
```
The app will be available at `http://localhost:5000`.

### **2. Access the Web Interface**
Open your browser and navigate to `http://localhost:5000`. You can:
- Start a new job by providing a Spotify URL or Last.fm username.
- Monitor active jobs in the "Active Jobs" tab.
- Configure API credentials in the "Settings" tab.

---

## **Configuration**

### **1. API Credentials**
To use the application, you need API credentials for Spotify and Last.fm. These can be configured in the **Settings** tab of the web interface or by editing the `config.json` file.

#### **Spotify API**
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Create an app and get the **Client ID** and **Client Secret**.

#### **Last.fm API**
1. Go to the [Last.fm API Account Creation](https://www.last.fm/api/account/create).
2. Create an API key and get the **API Key** and **API Secret**.

### **2. Default Configuration**
The application uses a `config.json` file located in `~/.lastfm_artwork_manager/`. If the file doesn’t exist, it will be created automatically with default values.

Example `config.json`:
```json
{
    "credentials": {
        "SPOTIPY_CLIENT_ID": "",
        "SPOTIPY_CLIENT_SECRET": "",
        "LASTFM_API_KEY": "",
        "LASTFM_API_SECRET": "",
        "LASTFM_EMAIL": "",
        "LASTFM_PASSWORD": ""
    },
    "settings": {
        "BROWSER": "chrome",
        "WAIT_TIME": 5,
        "UPLOAD_DELAY": 8,
        "MAX_RETRIES": 3,
        "RETRY_DELAY": 5,
        "HEADLESS": true
    },
    "paths": {
        "JSON_FILE_PATH": "no_artwork_albums.json",
        "ARTWORK_FOLDER": "artworkup",
        "LOG_FILE": "lastfm_artwork_manager.log"
    }
}
```

---

## **API Endpoints**

### **1. `/api/config`**
- **GET**: Retrieve current API credentials and settings.
- **POST**: Update API credentials and settings.

### **2. `/api/start-job`**
- **POST**: Start a new job.
- **Request Body**:
  ```json
  {
      "source_type": "album",
      "source_value": "https://open.spotify.com/album/...",
      "check_only": true,
      "lastfm_email": "user@example.com",
      "lastfm_password": "password",
      "lastfm_sources": ["recenttracks", "lovedtracks"]
  }
  ```

### **3. `/api/jobs`**
- **GET**: Retrieve a list of active jobs.

### **4. `/api/job-status/<job_id>`**
- **GET**: Retrieve the status of a specific job.

### **5. `/api/clear-job/<job_id>`**
- **DELETE**: Clear a completed or failed job.

---

## **Development**

### **1. Directory Structure**
```
project/
├── app.py                     # Main Flask application
├── lastfm_artwork_uploader.py # Core logic for Last.fm and Spotify integration
├── templates/                 # HTML templates
│   ├── index.html
├── static/                    # Static files (CSS, JS)
│   ├── app.js
├── config.json                # Default configuration (optional)
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker configuration
└── README.md                  # Project documentation
```

### **2. Running in Debug Mode**
To enable debug mode, run:
```bash
flask run --debug
```

---

## **Contributing**

Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add your message here"
   ```
4. Push to your branch:
   ```bash
   git push origin feature/your-feature-name
   ```
5. Open a pull request.

---

## **License**

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## **Acknowledgments**
- [Flask](https://flask.palletsprojects.com/) for the web framework.
- [Spotify API](https://developer.spotify.com/) for album and playlist data.
- [Last.fm API](https://www.last.fm/api) for user and album data.
- [Selenium](https://www.selenium.dev/) for browser automation.
