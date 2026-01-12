# Photo Import Sorter

A photo and video collection and conversion system that integrates with Nextcloud. Share upload links, automatically convert files to standard formats (JPEG/MP4), and organize everything in your Nextcloud.

## Features

- 🔐 **Nextcloud Authentication** - Login with your Nextcloud account via OAuth2
- 📁 **Folder Management** - Create folders in your Nextcloud with custom settings
- 🔗 **Shareable Upload Links** - Generate secure, random links for anonymous uploads
- 🔄 **Auto-Conversion** - Automatically converts:
  - Images: HEIC, RAW (CR2, NEF, ARW, DNG), PNG, TIFF, WebP → JPEG
  - Videos: MOV, AVI, MKV, HEVC, WebM → MP4
- 📅 **Smart Naming** - Files named by EXIF date + event name
- 📊 **Upload Statistics** - Track uploads by IP, file sizes, conversion times
- 🔒 **Secure Sharing** - 32-character random tokens for upload links
- 📱 **Modern UI** - Clean, responsive interface with drag-and-drop uploads

## Architecture

- **Backend**: Django + Django REST Framework
- **Frontend**: SvelteKit + TailwindCSS
- **Task Queue**: Celery + Redis
- **Storage**: SQLite (configuration) + Nextcloud (files)
- **Deployment**: Docker Compose

## Prerequisites

- Docker and Docker Compose
- A Nextcloud instance (v32.0.3+)
- Nextcloud OAuth2 app configured

## Nextcloud OAuth2 Setup

1. Go to your Nextcloud Admin Settings → Security → OAuth 2.0 clients
2. Add a new OAuth2 client:
   - **Name**: Photo Import Sorter
   - **Redirect URI**: `https://your-domain.com:8444/social/complete/nextcloud/`
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

### 2. Configure .env

```env
# Generate a secure secret key (use command above)
DJANGO_SECRET_KEY=your-secure-random-key-here

# Set to False in production
DJANGO_DEBUG=False

# Your domain
DJANGO_ALLOWED_HOSTS=localhost,your-domain.com

# Nextcloud configuration
NEXTCLOUD_URL=https://your-nextcloud.com
NEXTCLOUD_CLIENT_ID=your-oauth-client-id
NEXTCLOUD_CLIENT_SECRET=your-oauth-client-secret

# Frontend URL (include port 8444)
FRONTEND_URL=https://your-domain.com:8444

# SSL certificates (Let's Encrypt)
SSL_CERT_PATH=/etc/letsencrypt/live/your-domain.com/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/your-domain.com/privkey.pem
```

### 3. Build and run

```bash
# Build and start all services
docker compose up -d

# Run database migrations
docker compose exec backend python manage.py migrate

# Create a superuser (optional, for Django admin)
docker compose exec backend python manage.py createsuperuser
```

### 4. Access the application

- **Frontend**: https://your-domain.com:8444
- **Backend API**: https://your-domain.com:8444/api/
- **Django Admin**: https://your-domain.com:8444/admin/

## Development Setup

> **Note**: For local development, you can use HTTP. Update `.env` with `FRONTEND_URL=http://localhost:5173` and use the dev docker-compose file which doesn't require SSL certificates.

### Backend (Django)

```bash
# Create virtual environment
cd backend
python -m venv .venv
source .venv/bin/activate

# Install dependencies with uv
uv pip install -e ".[dev]"

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```

### Frontend (Svelte)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Development with Docker

```bash
# Start backend services (Redis, Django, Celery) - no SSL required
docker compose -f docker-compose.dev.yml up -d

# Frontend runs separately for hot reload
cd frontend && npm run dev
```

For local development, set in `.env`:
```env
FRONTEND_URL=http://localhost:5173
```

## Usage

### For Administrators

1. **Login** - Click "Login with Nextcloud" and authenticate
2. **Create Folder** - Click "New Folder" on the dashboard
   - Enter a display name and event name
   - Specify the Nextcloud folder path (will be created)
   - Choose naming format and quality settings
   - Add an optional README message
3. **Share Upload Link** - Copy the generated upload URL and share it
4. **Monitor** - View upload statistics and manage share links

### For Uploaders

1. **Open Upload Link** - Use the shared URL
2. **Upload Files** - Drag and drop or click to select files
3. **Wait for Processing** - Files are converted automatically
4. **Download** - Click the link to view/download from Nextcloud

## File Naming

Files are named using this format:
```
{date}_{event_name}.{ext}
```

Example: `2026-01-12_143052_wedding.jpg`

- **Date**: Earliest EXIF date (or upload date if unavailable)
- **Event Name**: Set by the folder creator
- **Conflicts**: Automatically adds numeric suffix (_1, _2, etc.)

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

## Configuration Options

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `DJANGO_SECRET_KEY` | Django secret key | Required |
| `DJANGO_DEBUG` | Debug mode | `False` |
| `DJANGO_ALLOWED_HOSTS` | Allowed hosts | `localhost` |
| `NEXTCLOUD_URL` | Nextcloud base URL | Required |
| `NEXTCLOUD_CLIENT_ID` | OAuth client ID | Required |
| `NEXTCLOUD_CLIENT_SECRET` | OAuth client secret | Required |
| `FRONTEND_URL` | Frontend URL | `https://your-domain.com:8444` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `MAX_UPLOAD_SIZE_MB` | Max file size in MB | `5120` |
| `TEMP_FILE_MAX_AGE_HOURS` | Clean up temp files older than X hours | `24` |
| `JPEG_QUALITY` | JPEG conversion quality | `90` |
| `VIDEO_CRF` | FFmpeg CRF for video | `23` |
| `SSL_CERT_PATH` | Path to SSL certificate | `./certs/fullchain.pem` |
| `SSL_KEY_PATH` | Path to SSL private key | `./certs/privkey.pem` |
| `CELERY_CPU_LIMIT` | CPU limit for Celery worker | `2` |
| `CELERY_MEMORY_LIMIT` | Memory limit for Celery worker | `2G` |

**Note:** SQLite database is configured automatically by Django - no DATABASE_URL needed.

## HTTPS / SSL Setup

The application is configured to run with HTTPS for production. You need SSL certificates from Let's Encrypt or another provider.

### Option 1: Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt install certbot

# Get certificates (standalone mode - stop any services on port 80 first)
sudo certbot certonly --standalone -d your-domain.com

# Certificates will be in /etc/letsencrypt/live/your-domain.com/
```

### Option 2: Using existing certificates

If you already have SSL certificates, point to them in your `.env` file.

### Configure .env for HTTPS

```env
# Update redirect URI to HTTPS
FRONTEND_URL=https://your-domain.com

# SSL certificate paths (Let's Encrypt example)
SSL_CERT_PATH=/etc/letsencrypt/live/your-domain.com/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/your-domain.com/privkey.pem
```

### Update Nextcloud OAuth2

After enabling HTTPS, update your Nextcloud OAuth2 client redirect URI:
- Old: `http://your-domain.com/social/complete/nextcloud/`
- New: `https://your-domain.com:8444/social/complete/nextcloud/`

### Certificate Renewal

Set up automatic renewal with a cron job:

```bash
# Add to crontab
0 3 * * * certbot renew --quiet && docker compose restart frontend
```

## Resource Limits

By default, the Celery worker has no resource limits. For production deployments where you want to limit CPU and memory usage:

### Enable resource limits

```bash
# Start with resource limits enabled
docker compose -f docker-compose.yml -f docker-compose.limits.yml up -d
```

### Configure limits in .env

```env
# CPU cores allocated to Celery worker
CELERY_CPU_LIMIT=2

# Memory limit for Celery worker
CELERY_MEMORY_LIMIT=2G
```

### Default limits

When using `docker-compose.limits.yml`:
- CPU: 2 cores (limit), 0.5 cores (reservation)
- Memory: 2GB (limit), 512MB (reservation)

## File Storage

- **Temp files**: Uploaded files are temporarily stored during conversion, then automatically deleted
- **Converted files**: Stored only in Nextcloud, not on this system
- **Cleanup**: A scheduled task runs hourly to clean up any orphaned temp files

## Supported Formats

### Input Images
PNG, JPG, JPEG, HEIC, HEIF, TIFF, TIF, CR2, NEF, ARW, DNG, RAW, WebP, BMP, GIF

### Input Videos
MOV, AVI, MKV, MP4, M4V, WMV, FLV, WebM, HEVC, 3GP

### Output
- Images → JPEG
- Videos → MP4 (H.264 + AAC)

## License

MIT License
