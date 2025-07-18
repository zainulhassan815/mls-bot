# Bright MLS Scraper Bot

A headless browser bot that logs into Bright MLS, scrapes property listings (price, beds, agent email, etc.), and sends the data to a Podio webhook via a Flask API.

---

## Tech Stack

- **Python 3.11**
- **Flask**
- **Selenium** (undetected-chromedriver)
- **Docker**
- **Requests**, **dotenv**, **logging**

---

## 2. Running the Application

### 2.1 Running Locally

Ensure Python is installed, then run:

```bash
cd app
python bot.py
```

> This starts the Flask development server at `http://localhost:5000`.

---

### 2.2 Running with Docker

Ensure Docker is installed, then run:

```bash
docker compose build
docker compose up -d  # Starts the container in detached mode
```

Verify the container is running:

```bash
docker ps
```

> You should see a container named `flask_app` (or as defined in your `docker-compose.yml`).

---

### API Usage

**POST** `/index`

#### Payload
```json
{
  "login": "your_username",
  "password": "your_password",
  "podio_url": "your_webhook_url",
  "agents": "Agent 1 | Agent 2"
}
```

> Make sure all fields are provided. The response will confirm success or failure.
