# Environment Variables Setup Guide

This guide walks you through every `.env` variable needed to run Photo Import Sorter.

## Quick Setup

```bash
# Copy the example file
cp .env.example .env

# Generate a secret key and copy it
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Edit the file
nano .env
```

---

## Required Variables

These must be set before the application will work.

### DJANGO_SECRET_KEY

**What it is:** A cryptographic key used by Django for sessions, CSRF protection, and password hashing.

**How to generate:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

**Example:**
```env
DJANGO_SECRET_KEY=Kx7z_mNpQ2vB8wL3fY1uR9cT6dH4jA0sE5iO7nM2pX9qZ8wV
```

⚠️ **Never share this key or commit it to version control!**

---

### NEXTCLOUD_URL

**What it is:** The base URL of your Nextcloud instance.

**How to find it:** This is the URL you use to access Nextcloud in your browser.

**Examples:**
```env
# If Nextcloud is on the same server
NEXTCLOUD_URL=https://localhost

# If Nextcloud is on a subdomain
NEXTCLOUD_URL=https://cloud.yourdomain.com

# If Nextcloud is on a path
NEXTCLOUD_URL=https://yourdomain.com/nextcloud
```

---

### NEXTCLOUD_CLIENT_ID and NEXTCLOUD_CLIENT_SECRET

**What they are:** OAuth2 credentials that allow Photo Import Sorter to authenticate users via Nextcloud.

**How to create them:**

1. Log into Nextcloud as an **admin**
2. Go to **Settings** → **Administration** → **Security**
3. Scroll down to **OAuth 2.0 clients**
4. Click **Add client**
5. Fill in:
   - **Name:** `Photo Import Sorter` (or any name you prefer)
   - **Redirect URI:** `https://your-domain.com:8444/social/complete/nextcloud/`
   
   ⚠️ The redirect URI must match exactly, including the trailing slash!

6. Click **Add**
7. Copy the **Client ID** and **Client Secret**

**Example:**
```env
NEXTCLOUD_CLIENT_ID=abc123def456ghi789jkl012mno345pqr
NEXTCLOUD_CLIENT_SECRET=xyz789uvw456rst123qpo098nml765kji
```

---

### FRONTEND_URL

**What it is:** The public URL where users access Photo Import Sorter.

**Important:** This must match what users type in their browser, including the port.

**Examples:**
```env
# Standard setup (port 8444)
FRONTEND_URL=https://photos.yourdomain.com:8444

# If using a reverse proxy on standard ports
FRONTEND_URL=https://photos.yourdomain.com

# Local development
FRONTEND_URL=http://localhost:5173
```

---

### SSL_CERT_PATH and SSL_KEY_PATH

**What they are:** Paths to your SSL certificate files on the host machine.

**Option 1: Let's Encrypt (recommended for production)**

```bash
# Install certbot
sudo apt install certbot

# Stop any services using port 80 temporarily
sudo docker compose down

# Get certificate
sudo certbot certonly --standalone -d photos.yourdomain.com

# Certificates are created at:
# /etc/letsencrypt/live/photos.yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/photos.yourdomain.com/privkey.pem
```

```env
SSL_CERT_PATH=/etc/letsencrypt/live/photos.yourdomain.com/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/photos.yourdomain.com/privkey.pem
```

**Option 2: Self-signed certificate (for testing)**

```bash
# Create a certs directory
mkdir -p certs

# Generate self-signed certificate (valid 365 days)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/privkey.pem \
  -out certs/fullchain.pem \
  -subj "/CN=localhost"
```

```env
SSL_CERT_PATH=./certs/fullchain.pem
SSL_KEY_PATH=./certs/privkey.pem
```

⚠️ Browsers will show a security warning with self-signed certificates.

---

## Optional Variables

These have sensible defaults but can be customized.

### DJANGO_DEBUG

**What it is:** Enables detailed error pages and debugging features.

**Values:**
- `True` - Development mode (shows detailed errors)
- `False` - Production mode (shows generic errors)

```env
# Production (default)
DJANGO_DEBUG=False

# Development
DJANGO_DEBUG=True
```

⚠️ **Never enable debug mode in production!** It exposes sensitive information.

---

### DJANGO_ALLOWED_HOSTS

**What it is:** A list of hostnames that Django will accept requests from.

**Format:** Comma-separated list, no spaces.

**Examples:**
```env
# Single domain
DJANGO_ALLOWED_HOSTS=photos.yourdomain.com

# Multiple domains
DJANGO_ALLOWED_HOSTS=photos.yourdomain.com,localhost,127.0.0.1

# Allow all (development only!)
DJANGO_ALLOWED_HOSTS=*
```

---

### REDIS_URL

**What it is:** Connection string for Redis (used by Celery for task queuing).

**Default:** `redis://redis:6379/0` (works with docker-compose)

**When to change:** Only if you're using an external Redis server.

```env
# Default (docker-compose)
REDIS_URL=redis://redis:6379/0

# External Redis with password
REDIS_URL=redis://:yourpassword@redis.yourdomain.com:6379/0
```

---

### MAX_UPLOAD_SIZE_MB

**What it is:** Maximum file size for uploads in megabytes.

**Default:** `5120` (5 GB)

**Examples:**
```env
# 5 GB (default)
MAX_UPLOAD_SIZE_MB=5120

# 10 GB
MAX_UPLOAD_SIZE_MB=10240

# 1 GB
MAX_UPLOAD_SIZE_MB=1024
```

---

### TEMP_FILE_MAX_AGE_HOURS

**What it is:** How long temporary files are kept before automatic cleanup.

**Default:** `24` hours

**How it works:** A scheduled task runs hourly to delete temp files older than this setting.

```env
# Keep for 24 hours (default)
TEMP_FILE_MAX_AGE_HOURS=24

# Delete immediately after processing
TEMP_FILE_MAX_AGE_HOURS=0

# Keep for 1 week (useful for debugging)
TEMP_FILE_MAX_AGE_HOURS=168
```

---

### JPEG_QUALITY

**What it is:** Quality setting for JPEG conversion (0-100).

**Default:** `92`

**Trade-off:** Higher = better quality but larger file size

```env
# High quality (default)
JPEG_QUALITY=92

# Maximum quality
JPEG_QUALITY=100

# Smaller files
JPEG_QUALITY=85
```

---

### VIDEO_CRF

**What it is:** Constant Rate Factor for video encoding. Controls quality vs file size.

**Default:** `18`

**Range:** 0-51 (lower = better quality, larger files)
- 0 = Lossless
- 18 = Visually lossless (recommended)
- 23 = Default FFmpeg setting
- 28+ = Noticeable quality loss

```env
# High quality (default)
VIDEO_CRF=18

# Smaller files, good quality
VIDEO_CRF=23

# Maximum quality
VIDEO_CRF=0
```

---

## Resource Limits (Optional)

These are only applied when using `docker-compose.limits.yml`.

### ENABLE_RESOURCE_LIMITS

**What it is:** Master switch for resource limiting.

```env
# Disabled (default)
ENABLE_RESOURCE_LIMITS=false

# Enabled
ENABLE_RESOURCE_LIMITS=true
```

### CELERY_MEMORY_LIMIT

**What it is:** Maximum RAM the Celery worker can use.

**Format:** Number followed by unit (M for MB, G for GB)

```env
# 4 GB (default)
CELERY_MEMORY_LIMIT=4G

# 8 GB (for large video files)
CELERY_MEMORY_LIMIT=8G

# 2 GB (resource-constrained server)
CELERY_MEMORY_LIMIT=2G
```

### CELERY_CPU_LIMIT

**What it is:** Maximum CPU cores the Celery worker can use.

**Format:** Decimal number (e.g., 2.0 = 2 cores, 0.5 = half a core)

```env
# 2 cores (default)
CELERY_CPU_LIMIT=2.0

# 4 cores (faster processing)
CELERY_CPU_LIMIT=4.0

# 1 core (minimal resources)
CELERY_CPU_LIMIT=1.0
```

---

## Complete Example .env

Here's a complete production-ready example:

```env
# ===========================================
# Photo Import Sorter - Production .env
# ===========================================

# Django Core
DJANGO_SECRET_KEY=Kx7z_mNpQ2vB8wL3fY1uR9cT6dH4jA0sE5iO7nM2pX9qZ8wV1234567890
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=photos.example.com,localhost

# Redis (no change needed for docker-compose)
REDIS_URL=redis://redis:6379/0

# Nextcloud OAuth2
NEXTCLOUD_URL=https://cloud.example.com
NEXTCLOUD_CLIENT_ID=abc123def456ghi789
NEXTCLOUD_CLIENT_SECRET=xyz789uvw456rst123

# Frontend (must match your actual domain + port)
FRONTEND_URL=https://photos.example.com:8444

# SSL Certificates (Let's Encrypt)
SSL_CERT_PATH=/etc/letsencrypt/live/photos.example.com/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/photos.example.com/privkey.pem

# File Handling
MAX_UPLOAD_SIZE_MB=5120
TEMP_FILE_MAX_AGE_HOURS=24

# Conversion Quality
JPEG_QUALITY=92
VIDEO_CRF=18

# Resource Limits (optional)
ENABLE_RESOURCE_LIMITS=false
CELERY_MEMORY_LIMIT=4G
CELERY_CPU_LIMIT=2.0
```

---

## Troubleshooting

### "Invalid redirect URI" error during login
- Ensure `FRONTEND_URL` matches the Nextcloud OAuth2 redirect URI exactly
- Include the port number if using a non-standard port (e.g., `:8444`)
- The redirect URI in Nextcloud must be: `{FRONTEND_URL}/social/complete/nextcloud/`

### SSL certificate errors
- Verify certificate paths are correct and readable by Docker
- For Let's Encrypt, ensure the full path including `/etc/letsencrypt/live/`
- Check certificate hasn't expired: `openssl x509 -enddate -noout -in /path/to/cert.pem`

### Connection refused to Nextcloud
- Verify `NEXTCLOUD_URL` is reachable from the Docker container
- If Nextcloud is on the same server, use the external hostname, not `localhost`
- Check Nextcloud's `trusted_domains` setting includes the Photo Import Sorter server

### Redis connection errors
- The default `REDIS_URL` works with docker-compose
- Only change if using an external Redis server
- Verify Redis is running: `docker compose logs redis`
