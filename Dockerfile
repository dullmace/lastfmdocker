# Dockerfile
FROM python:3.9-slim

# Install Firefox and dependencies
RUN apt-get update && apt-get install -y \
    firefox-esr \
    wget \
    bzip2 \
    libxtst6 \
    libgtk-3-0 \
    libx11-xcb1 \
    libdbus-glib-1-2 \
    libxt6 \
    libpci-dev \
    && rm -rf /var/lib/apt/lists/*

# Install geckodriver
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.32.0/geckodriver-v0.32.0-linux64.tar.gz \
    && tar -xzf geckodriver-v0.32.0-linux64.tar.gz -C /usr/local/bin \
    && rm geckodriver-v0.32.0-linux64.tar.gz \
    && chmod +x /usr/local/bin/geckodriver

# Install Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install specific version of chromedriver
RUN wget -q https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm chromedriver_linux64.zip
    
# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create artwork directory
RUN mkdir -p artworkup

RUN mkdir -p /root/.lastfm_artwork_manager

COPY config.json /root/.lastfm_artwork_manager/

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
