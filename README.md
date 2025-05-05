# UK Vehicle Data API – Docker deployment

This repo packages the async FastAPI service in a slim, multi‑stage
Docker image.

## Features

- Fast, async vehicle data lookup by UK registration mark (VRM)
- Clean, modern web interface for easy access
- Cache layer for repeated lookups
- JSON API for programmatic access
- Containerized deployment ready

## Build the image

```bash
docker build -t vehicle-service:latest .
```

## Run the API and Web Interface

```bash
docker run -p 5001:5001 --name vehicle-api vehicle-service
```

The service will be available at:
- Web Interface: http://localhost:5001/
- API Docs: http://localhost:5001/docs

## API Usage

### Web Interface

Visit http://localhost:5001/ in your browser to use the user-friendly lookup form.

### API Endpoints

1. **Vehicle Lookup**
   ```
   GET /{vrm}
   ```
   Example: `GET /AB12CDE`

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn app.vehicle_service:app --reload --port 5001
```

### Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── vehicle_service.py
│   └── static/
│       ├── index.html       # Web interface
│       └── favicon.ico      # Site favicon
├── requirements.txt
├── Dockerfile
└── README.md