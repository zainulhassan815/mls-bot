FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install Chrome dependencies & Chrome
RUN apt-get update && apt-get install -y \
    curl unzip gnupg ca-certificates fonts-liberation \
    libnss3 libatk-bridge2.0-0 libgtk-3-0 libxss1 libasound2 libx11-xcb1 \
    && curl -sSL https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o chrome.deb \
    && apt-get install -y ./chrome.deb \
    && rm chrome.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/google-chrome

# App directory
WORKDIR /

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app code
COPY . .

# Expose Flask default port
EXPOSE 5000

CMD ["python", "bot-dev.py"]
