# CloudNest — Self-Hosted Cloud Storage

CloudNest is a portfolio project that demonstrates a self-hosted file storage web application built with **FastAPI, MySQL, SQLAlchemy, Docker, and Jinja2**.

Users can register, sign in, upload files, view their personal file list, download files, and delete files. File metadata is stored in MySQL; file contents are stored in a persistent Docker volume.

## Features

- User registration and sign-in with Argon2 password hashing
- Session-based authentication
- Upload, list, download, and delete files
- Per-user file ownership checks
- Configurable per-file upload limit (25 MB by default)
- Persistent database and file-storage Docker volumes
- Responsive web dashboard
- JSON file-list endpoint at `/api/files`
- Health check at `/health`
- Containerized local setup with Docker Compose

## Tech stack

- Python 3.12
- FastAPI and Uvicorn
- MySQL 8.4
- SQLAlchemy 2
- Jinja2, HTML, CSS
- Docker and Docker Compose
- Argon2 password hashing

## Run locally with Docker

### Prerequisites
Install Docker Desktop and make sure it is running.

### 1. Configure environment variables

PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace all three example values with unique, strong secrets. Do not commit `.env` to GitHub.

### 2. Start the application

```powershell
docker compose up --build -d
```

Open **http://localhost:8000** and create an account.

API documentation: **http://localhost:8000/docs**

### 3. Useful commands

```powershell
docker compose ps
docker compose logs -f app
docker compose logs -f db
docker compose stop
docker compose start
docker compose down
```

The database and uploaded files are stored in named Docker volumes and persist when containers are stopped or recreated. `docker compose down -v` deletes those volumes; do not use it unless you intend to erase your stored data.

## Project structure

```text
CloudNest/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── security.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── register.html
│   │   └── dashboard.html
│   └── static/
│       └── style.css
├── .env.example
├── .gitignore
├── Dockerfile
├── compose.yaml
└── requirements.txt
```

## Main routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Sign-in page |
| GET, POST | `/register` | Create an account |
| POST | `/login` | Sign in |
| POST | `/logout` | Sign out |
| GET | `/dashboard` | Personal file dashboard |
| POST | `/files/upload` | Upload a file |
| GET | `/files/{file_id}/download` | Download an owned file |
| POST | `/files/{file_id}/delete` | Delete an owned file |
| GET | `/api/files` | List current user's files as JSON |
| GET | `/health` | Health check |
| GET | `/docs` | Interactive API documentation |

## Security notes and next steps

This is a learning/portfolio project, not a production-ready public cloud service. Before exposing it to the internet, add CSRF protection for form submissions, rate limiting, stricter upload/content validation, HTTPS, secure cookie settings, database migrations, automated backups, and security testing. Use a strong random `SESSION_SECRET`; set `COOKIE_HTTPS_ONLY=true` only after HTTPS is configured. Keep secrets out of source control.

## Future improvements

- Shareable links with expiry and revocation
- File previews and search
- Storage quotas per user
- Audit logs and automated backups
- Virus scanning and file-type allowlists
- Cloud deployment behind HTTPS

## Author

Built as a backend and Docker learning project. Update this section with your name, GitHub profile, screenshots, and demo link before publishing.
