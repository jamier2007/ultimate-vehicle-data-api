UK Vehicle Data API – Docker deployment

This repository packages the async FastAPI service in a slim, multi-stage Docker image.

Features
	•	Fast, asynchronous vehicle-data lookup by UK registration mark (VRM)
	•	Clean, modern web interface for easy access
	•	In-memory cache layer for repeated look-ups
	•	Fully-typed JSON API for programme-matic access
	•	Permissive CORS policy – the service accepts requests from any origin (see below)
	•	Container-ready deployment for local testing or production

CORS policy

The service starts with the CORSMiddleware enabled and configured as follows:

Setting	Value	Meaning
allow_origins	["*"]	Accept requests from every origin
allow_methods	"*"	Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
allow_headers	"*"	Allow any custom or standard headers
allow_credentials	True	Cookies, authorisation headers, and TLS client certificates are forwarded

No further configuration is required: as soon as the container is running, any website, SPA, or mobile app can call the API without cross-origin errors.

Need stricter rules?
Edit app.vehicle_service.py and replace the wildcard ("*" ) entries with explicit lists of allowed origins, methods, or headers.

Build the image

docker build -t vehicle-service:latest .

Run the API and web interface

docker run -p 5001:5001 --name vehicle-api vehicle-service

The service will be available at:
	•	Web interface: http://localhost:5001/
	•	Interactive API docs (Swagger UI): http://localhost:5001/docs

Because the CORS policy is wide open, you can also invoke the API from any other origin—for example, a React or Vue development server on http://localhost:3000.

API usage

Web interface

Open http://localhost:5001/ in your browser and enter a registration mark in the form.

API endpoints

Purpose	Method & path	Example
Vehicle look-up	GET /{vrm}	GET /AB12CDE

Responses are returned as plain text (key : value pairs) for simplicity; you can request JSON by parsing the text or adapting the source.

Development

Local development

# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn app.vehicle_service:app --reload --port 5001

Project structure

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