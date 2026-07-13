# Group Photo Sorter (Nextcloud App)

A native Nextcloud application compatible with Nextcloud 32.0.12. It allows Nextcloud users to generate secure, shareable public upload links where guests can upload photos and videos asynchronously. The app automatically converts uploads to standard, web-friendly formats (JPEG/MP4), extracts capture dates from EXIF/metadata, organizes files, and saves them directly into the user's Nextcloud storage.

---

## Key Features

- 📁 **Native Integration**: Works directly inside Nextcloud using the Nextcloud AppFramework. Saves files into Nextcloud's virtual filesystem and respects user storage environments.
- 🔗 **Guest Upload Links**: Create custom folders, and generate unique, secure 32-character token links for anonymous uploads.
- 🔄 **Robust Conversion Pipeline**:
  - **Images**: HEIC, RAW formats (CR2, NEF, ARW, DNG), PNG, WebP, TIFF -> Optimized JPEG.
  - **Videos**: MOV, AVI, MKV, HEVC, WebM -> Web-friendly H.264 MP4 with AAC audio (fast-start optimized for streaming).
- 📅 **EXIF Sorting**: Reads EXIF tags (images) and media creation times (videos) to dynamically name files according to the format selected (e.g. `YYYY-MM-DD_HHMMSS_event.ext`).
- ⚡ **Asynchronous Queue**: Uploaded files are safely queued in the database. Video conversion spawns isolated, background FFmpeg processes to keep the web thread responsive.
- 🔒 **Distributed Cache Locking**: Employs Nextcloud's distributed cache (APCu/Redis) to handle lock synchronization and prevent race conditions or server overload during parallel conversions.
- 📊 **Analytics**: View statistics on uploads, original vs. compressed file sizes, total disk space saved, and upload counts grouped by uploader IP.
- ⚖️ **GDPR Compliant**: Automatically anonymizes guest IP addresses older than 30 days via a daily timed background maintenance job.

---

## Server Prerequisites

- **Nextcloud**: version `31.x` or `32.x` (fully compatible with `32.0.12`).
- **System Commands**:
  - `ffmpeg` and `ffprobe` (for video encoding and info extraction).
  - `python3` (for image preprocessing and EXIF extraction).

---

## Directory Structure

```text
├── appinfo/             # Nextcloud App metadata (info.xml) and routing (routes.php)
├── bin/                 # Executable Python helper converter script
├── css/                 # Compiled CSS bundle (Tailwind)
├── js/                  # Compiled JS Svelte bundle
├── lib/                 # Core PHP source classes
│   ├── AppInfo/         # DI Container & Application bootstrap
│   ├── BackgroundJob/   # Timed cron jobs (Conversion, GDPR Cleanup)
│   ├── Command/          # occ CLI commands
│   ├── Controller/      # REST API Controllers (Admin, Guest Upload)
│   ├── Db/              # Database entities and mappers
│   ├── Migration/       # Database Schema updates
│   └── Service/         # Core business logic (Storage, Conversion, Folders)
├── templates/           # PHP Template views (index.php, upload.php)
└── frontend/            # Svelte frontend source project
```

---

## Installation & Setup

1. Copy or symlink this repository folder into your Nextcloud `apps/` or `custom_apps/` directory under the name `group_photo_sorter`.
2. Enable the app using the Nextcloud Admin Panel or via the command line:
   ```bash
   php occ app:enable group_photo_sorter
   ```
3. Run the database migrations:
   ```bash
   php occ migration:migrate group_photo_sorter
   ```

### Recommended Python Dependencies Setup
For RAW and HEIC image support, set up a virtual environment inside the app directory to install `pillow-heif` and `rawpy`:
```bash
cd /path/to/nextcloud/apps/group_photo_sorter
python3 -m venv venv
./venv/bin/pip install pillow pillow-heif rawpy
```
The app will automatically detect and use the Python virtual environment if it exists.

---

## Development & Building Frontend

The Svelte frontend can be run locally for development or compiled into standard assets for Nextcloud.

### 1. Local Dev Server
```bash
cd frontend
npm install
npm run dev
```

### 2. Build for Nextcloud Distribution
This builds the Svelte code into a single, scoped CSS/JS bundle and writes them directly to the root `css/` and `js/` folders:
```bash
cd frontend
npm run build:nextcloud
```

---

## Local Docker Testing

For detailed instructions on running a local Nextcloud dev container, symlinking your workspace, and installing packages inside the container, please see the [Local Testing & Development Guide](local_testing_guide.md).
