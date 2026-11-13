"""
File conversion utilities for images and videos.
"""

import io
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from dateutil import parser as date_parser
from PIL import Image, ImageOps
import pillow_heif

from apps.core.cache_utils import redis_lock, safe_cache_get, safe_cache_set

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

# EXIF tag IDs for capture dates
_EXIF_DATE_TAG_IDS = (
    36867,  # DateTimeOriginal
    36868,  # DateTimeDigitized
    306,    # DateTime
)
_EXIF_IFD_TAG = 0x8769


def _parse_exif_date_str(value: Any) -> Optional[datetime]:
    """Parse an EXIF date string into a naive datetime object."""
    if not value:
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode('utf-8', errors='ignore')
        except Exception:
            return None

    date_str = str(value).strip().rstrip('\x00').strip()
    if not date_str or date_str.startswith('0000:00:00'):
        return None

    # Standard EXIF format: "YYYY:MM:DD HH:MM:SS"
    for fmt in (
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y:%m:%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y:%m:%d",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str[:19], fmt)
        except ValueError:
            continue

    # Fallback: replace YYYY:MM:DD colons with dashes and use dateutil
    normalized = re.sub(r'^(\d{4}):(\d{2}):(\d{2})', r'\1-\2-\3', date_str)
    try:
        dt = date_parser.parse(normalized)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def get_exif_date(image_or_path: Any) -> Optional[datetime]:
    """
    Extract the earliest capture date from image EXIF data.

    Accepts either a file path (`str` / `Path`) or an open `PIL.Image.Image`.
    Uses both public `img.getexif()` (which supports HEIC/HEIF, WebP, PNG,
    TIFF, DNG, and JPEG, including the Exif SubIFD 0x8769) and legacy
    `img._getexif()` fallback.
    """
    dates = []

    def _extract_from_img(img: Image.Image) -> None:
        # 1. Public Pillow getexif() API (works for HEIC, JPEG, TIFF, WebP, PNG)
        if hasattr(img, 'getexif'):
            try:
                exif = img.getexif()
                if exif:
                    for tag_id in _EXIF_DATE_TAG_IDS:
                        if tag_id in exif:
                            dt = _parse_exif_date_str(exif.get(tag_id))
                            if dt:
                                dates.append(dt)
                    # Check Exif SubIFD (0x8769) where DateTimeOriginal lives
                    try:
                        exif_ifd = exif.get_ifd(_EXIF_IFD_TAG)
                        if exif_ifd:
                            for tag_id in _EXIF_DATE_TAG_IDS:
                                if tag_id in exif_ifd:
                                    dt = _parse_exif_date_str(exif_ifd.get(tag_id))
                                    if dt:
                                        dates.append(dt)
                    except Exception:
                        pass
            except Exception:
                pass

        # 2. Legacy _getexif() fallback if nothing found yet
        if not dates and hasattr(img, '_getexif'):
            try:
                raw_exif = img._getexif()
                if raw_exif:
                    for tag_id in _EXIF_DATE_TAG_IDS:
                        if tag_id in raw_exif:
                            dt = _parse_exif_date_str(raw_exif.get(tag_id))
                            if dt:
                                dates.append(dt)
            except Exception:
                pass

    try:
        if isinstance(image_or_path, Image.Image):
            _extract_from_img(image_or_path)
        else:
            with Image.open(image_or_path) as img:
                _extract_from_img(img)
    except Exception:
        pass

    return min(dates) if dates else None


def _parse_video_date_str(value: Any) -> Optional[datetime]:
    """Parse a video creation_time tag string (ISO-8601 or QuickTime format)."""
    if not value:
        return None
    date_str = str(value).strip()
    if not date_str or date_str.startswith('0000-00-00'):
        return None

    try:
        dt = date_parser.isoparse(date_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        pass

    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def get_video_creation_date(video_path: str) -> Optional[datetime]:
    """
    Extract creation date from video metadata using ffprobe.
    """
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            candidate_tag_dicts = []

            fmt_tags = data.get('format', {}).get('tags')
            if isinstance(fmt_tags, dict):
                candidate_tag_dicts.append(fmt_tags)

            for stream in data.get('streams', []):
                s_tags = stream.get('tags')
                if isinstance(s_tags, dict):
                    candidate_tag_dicts.append(s_tags)

            date_fields = (
                'com.apple.quicktime.creationdate',
                'creation_time',
                'date',
            )

            for tags in candidate_tag_dicts:
                lower_map = {str(k).lower(): v for k, v in tags.items()}
                for field in date_fields:
                    if field in lower_map:
                        parsed = _parse_video_date_str(lower_map[field])
                        if parsed:
                            return parsed
    except Exception:
        pass

    return None


def convert_image_to_jpeg(
    input_path: str,
    quality: int = 90
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Convert any supported image format to JPEG.

    Args:
        input_path: Path to input image
        quality: JPEG quality (1-100)

    Returns:
        Tuple of (jpeg_bytes, metadata_dict)
    """
    ext = Path(input_path).suffix.lower()

    # Extract EXIF capture date from original file before conversion
    exif_date = get_exif_date(input_path)

    # Handle RAW formats
    if ext in {'.cr2', '.nef', '.arw', '.dng', '.raw'}:
        import rawpy
        with rawpy.imread(input_path) as raw:
            rgb = raw.postprocess(use_camera_wb=True)
            img = Image.fromarray(rgb)
    else:
        img = Image.open(input_path)
        # Apply EXIF orientation transpose BEFORE converting mode / pasting onto RGB canvas
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

    # Convert to RGB if necessary (e.g., from RGBA, LA, CMYK, 16-bit I, or palette mode)
    if img.mode in ('RGBA', 'LA', 'P'):
        if img.mode == 'P':
            img = img.convert('RGBA')
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert('RGB')
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    output = io.BytesIO()
    img.save(output, format='JPEG', quality=int(quality), optimize=True)
    jpeg_bytes = output.getvalue()

    return jpeg_bytes, {
        'exif_date': exif_date,
        'width': img.width,
        'height': img.height,
        'original_size': os.path.getsize(input_path),
        'converted_size': len(jpeg_bytes),
    }


def convert_video_to_mp4(
    input_path: str,
    crf: int = 23,
    stream_mode: bool = False
) -> Tuple[Any, Dict[str, Any]]:
    """
    Convert any supported video format to MP4 (H.264).

    Args:
        input_path: Path to input video
        crf: Constant Rate Factor for quality (18-28, lower = better)
        stream_mode: If True, returns file path instead of bytes (for large files)

    Returns:
        Tuple of (mp4_bytes_or_path, metadata_dict)
    """
    creation_date = get_video_creation_date(input_path)
    original_size = os.path.getsize(input_path)

    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        output_path = tmp.name

    try:
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', str(crf),
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr[-1000:]}")

        converted_size = os.path.getsize(output_path)

        probe_result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                output_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        width, height = 0, 0
        if probe_result.returncode == 0:
            data = json.loads(probe_result.stdout)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    break

        metadata = {
            'creation_date': creation_date,
            'width': width,
            'height': height,
            'original_size': original_size,
            'converted_size': converted_size,
        }

        if stream_mode:
            return output_path, metadata
        else:
            with open(output_path, 'rb') as f:
                mp4_bytes = f.read()
            os.unlink(output_path)
            return mp4_bytes, metadata

    except Exception:
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise


def _sanitize_filename_part(value: str) -> str:
    """Replace unsafe filename characters with underscores."""
    cleaned = re.sub(r'[^\w\-]+', '_', value.strip(), flags=re.UNICODE)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or 'file'


def generate_filename(
    folder,
    original_filename: str,
    file_date: Optional[datetime],
    is_video: bool
) -> str:
    """
    Generate a new filename based on folder naming format.
    """
    from apps.folders.models import NamingFormat

    dt = file_date if file_date else datetime.now()

    date_full = dt.strftime('%Y-%m-%d_%H%M%S')
    date_day = dt.strftime('%Y-%m-%d')
    date_hour = dt.strftime('%Y-%m-%d_%H')

    ext = '.mp4' if is_video else '.jpg'
    event = _sanitize_filename_part(folder.event_name)
    fmt = (folder.naming_format or '').lower()

    if fmt == NamingFormat.DATE_EVENT:
        base_name = f"{date_full}_{event}"
    elif fmt == NamingFormat.EVENT_DATE:
        base_name = f"{event}_{date_full}"
    elif fmt == NamingFormat.DATE_ONLY:
        base_name = date_full
    elif fmt == NamingFormat.DATE_DAY_ONLY:
        base_name = date_day
    elif fmt == NamingFormat.DATE_DAY_EVENT:
        base_name = f"{date_day}_{event}"
    elif fmt == NamingFormat.EVENT_DATE_DAY:
        base_name = f"{event}_{date_day}"
    elif fmt == NamingFormat.DATE_HOUR_EVENT:
        base_name = f"{date_hour}_{event}"
    elif fmt == NamingFormat.EVENT_DATE_HOUR:
        base_name = f"{event}_{date_hour}"
    else:  # ORIGINAL
        base_name = _sanitize_filename_part(Path(original_filename).stem)

    return f"{base_name}{ext}"


def get_unique_filename(
    folder,
    filename: str,
    client,
    reserved_names: Optional[Set[str]] = None,
) -> str:
    """
    Ensure filename is unique in the Nextcloud folder using a Redis-cached
    directory set protected by a distributed lock.

    This avoids making N sequential PROPFIND calls per file and prevents
    race-condition collisions when multiple files with identical timestamps
    are processed concurrently or in a batch.
    """
    base_path = folder.nextcloud_folder_path
    cache_key = f"folder_filenames:{folder.id}"
    lock_name = f"folder_filenames_lock:{folder.id}"

    with redis_lock(lock_name, timeout=15, wait_timeout=10.0):
        known_files_list = safe_cache_get(cache_key)
        known_files: Optional[Set[str]] = None

        if isinstance(known_files_list, (list, set)):
            known_files = set(known_files_list)
        else:
            # Populate cache with a single WebDAV Depth: 1 listing
            listing = client.list_folder(base_path)
            if listing.get('success'):
                known_files = {
                    item['name']
                    for item in listing.get('items', [])
                    if item.get('name')
                }

        if reserved_names:
            if known_files is not None:
                known_files |= reserved_names

        stem = Path(filename).stem
        ext = Path(filename).suffix

        if known_files is not None:
            candidate = filename
            counter = 1
            while candidate in known_files:
                candidate = f"{stem}_{counter}{ext}"
                counter += 1
                if counter > 9999:
                    raise RuntimeError("Too many filename conflicts")

            known_files.add(candidate)
            if reserved_names is not None:
                reserved_names.add(candidate)
            safe_cache_set(cache_key, list(known_files), timeout=300)
            return candidate

    # Fallback if Redis cache or list_folder wasn't available
    local_reserved = reserved_names if reserved_names is not None else set()
    full_path = f"{base_path}/{filename}"
    if filename not in local_reserved and not client.file_exists(full_path):
        local_reserved.add(filename)
        return filename

    counter = 1
    while counter <= 9999:
        new_filename = f"{stem}_{counter}{ext}"
        new_path = f"{base_path}/{new_filename}"
        if new_filename not in local_reserved and not client.file_exists(new_path):
            local_reserved.add(new_filename)
            return new_filename
        counter += 1

    raise RuntimeError("Too many filename conflicts")
