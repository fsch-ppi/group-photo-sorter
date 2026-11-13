# Photo Import Sorter

A photo and video collection and conversion system that integrates with Nextcloud. Share upload links, automatically convert files to standard formats (JPEG/MP4), and organize everything in your Nextcloud.

## Features

- 🔐 **Nextcloud Authentication** - Login with your Nextcloud account via OAuth2
- 📁 **Folder Management** - Create folders in your Nextcloud with custom settings
- 🔗 **Shareable Upload Links** - Generate secure, random links for anonymous uploads
- 🔄 **Auto-Conversion** - Automatically converts:
  - Images: HEIC, RAW (CR2, NEF, ARW, DNG), PNG, TIFF, WebP → JPEG
  - Videos: MOV, AVI, MKV, HEVC, WebM → MP4 (H.264 + AAC)
- 📅 **Smart Naming** - Files named by EXIF/media capture date + event name
- ⚡ **Redis Caching & Distributed Locking** - Caches Nextcloud user metadata, folder sizes, and folder file listings in Redis with atomic locks to eliminate redundant WebDAV queries and prevent filename collisions
- 📊 **Upload Statistics** - Track uploads by IP, file sizes, conversion times
- 🔒 **GDPR Compliant** - Automatically anonymizes uploader IP addresses older than 30 days
- 📱 **Modern UI** - Clean, responsive interface with drag-and-drop uploads and session recovery

## Architecture

- **Backend**: Django + Django REST Framework
- **Frontend**: SvelteKit + TailwindCSS
- **Task Queue & Caching**: Celery + Redis
- **Storage**: SQLite (configuration) + Nextcloud (files via WebDAV/OCS)
- **Deployment**: Docker Compose

## Prerequisites

- Docker and Docker Compose
- A Nextcloud instance
- Nextcloud OAuth2 app configured

## Nextcloud OAuth2 Setup

1. Go to your Nextcloud Admin Settings → Security → OAuth 2.0 clients
2. Add a new OAuth2 client:
   - **Name**: Photo Import Sorter
   - **Redirect URI**: `https://your-domain.com:18443/social/complete/nextcloud/`
3. Note down the **Client ID** and **Client Secret**

> 📖 **See [docs/ENV_SETUP_GUIDE.md](docs/ENV_SETUP_GUIDE.md) for detailed setup instructions for all environment variables.**

## Quick Start

### 1. Clone and configure

```bash
git clone <repository-url>
cd Photo_Import_Sorter

# Copy environment template
cp .env.example .env

# Generate a secret key
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Edit .env with your settings
nano .env
```

### 2. Build and run

```bash
# Build and start all services
docker compose up -d --build

# Run database migrations
docker compose exec backend python manage.py migrate
```

### 3. Access the application

- **Frontend**: `https://your-domain.com:18443` (HTTP on port `18080` redirects to HTTPS `18443`; override with `HTTP_PORT` / `HTTPS_PORT` in `.env`)
- **Backend API**: `https://your-domain.com:18443/api/`
- **Django Admin**: `https://your-domain.com:18443/admin/`

## API Endpoints

### Authentication
- `GET /api/auth/status/` - Check auth status
- `GET /api/auth/login/` - Redirect to Nextcloud OAuth
- `POST /api/auth/logout/` - Logout

### Folders (authenticated)
- `GET /api/folders/` - List folders
- `POST /api/folders/` - Create folder
- `GET /api/folders/{id}/` - Get folder details
- `PATCH /api/folders/{id}/` - Update folder
- `DELETE /api/folders/{id}/` - Delete folder
- `POST /api/folders/{id}/regenerate_token/` - New upload link
- `POST /api/folders/{id}/regenerate_nextcloud_share/` - New NC share
- `GET /api/folders/{id}/statistics/` - Upload stats

### Uploads (public)
- `GET /api/upload/{token}/info/` - Folder info for upload page
- `POST /api/upload/{token}/` - Upload file
- `GET /api/upload/task/{task_id}/` - Check task status
- `GET /api/upload/{token}/session/{session_id}/` - Recover session upload statuses

## License

MIT License
