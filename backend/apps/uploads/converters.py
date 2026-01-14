"""
File conversion utilities for images and videos.
"""

import os
import io
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from PIL import Image
import pillow_heif
from django.conf import settings


# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()


def get_exif_date(image_path: str) -> Optional[datetime]:
    """
    Extract the earliest date from image EXIF data.

    Checks multiple EXIF date fields and returns the earliest one.
    """
    try:
        from PIL.ExifTags import TAGS

        with Image.open(image_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None

            date_fields = [
                36867,  # DateTimeOriginal
                36868,  # DateTimeDigitized
                306,    # DateTime
            ]

            dates = []
            for field_id in date_fields:
                if field_id in exif_data:
                    date_str = exif_data[field_id]
                    try:
                        # EXIF date format: "YYYY:MM:DD HH:MM:SS"
                        dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        dates.append(dt)
                    except (ValueError, TypeError):
                        pass

            if dates:
                return min(dates)  # Return earliest date

    except Exception:
        pass

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
                video_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            tags = data.get('format', {}).get('tags', {})

            # Try different metadata fields
            date_fields = ['creation_time', 'date',
                           'com.apple.quicktime.creationdate']

            for field in date_fields:
                if field in tags:
                    date_str = tags[field]
                    # Try various formats
                    for fmt in [
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                        "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d",
                    ]:
                        try:
                            return datetime.strptime(date_str[:26], fmt[:26])
                        except ValueError:
                            continue
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

    # Handle RAW formats
    if ext in {'.cr2', '.nef', '.arw', '.dng', '.raw'}:
        import rawpy
        with rawpy.imread(input_path) as raw:
            rgb = raw.postprocess()
            img = Image.fromarray(rgb)
    else:
        img = Image.open(input_path)

    # Get EXIF date before any processing
    exif_date = get_exif_date(input_path)

    # Convert to RGB if necessary (e.g., from RGBA or palette mode)
    if img.mode in ('RGBA', 'LA', 'P'):
        # Create white background for transparency
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()
                         [-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Preserve orientation from EXIF
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Save to bytes
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
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
    crf: int = 23
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Convert any supported video format to MP4 (H.264).

    Args:
        input_path: Path to input video
        crf: Constant Rate Factor for quality (18-28, lower = better)

    Returns:
        Tuple of (mp4_bytes, metadata_dict)
    """
    creation_date = get_video_creation_date(input_path)
    original_size = os.path.getsize(input_path)

    # Create temp output file
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        output_path = tmp.name

    try:
        # Run ffmpeg conversion
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', str(crf),
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',  # Overwrite output
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for large videos
        )

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")

        # Read converted video
        with open(output_path, 'rb') as f:
            mp4_bytes = f.read()

        converted_size = len(mp4_bytes)

        # Get video dimensions
        probe_result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                output_path
            ],
            capture_output=True,
            text=True
        )

        width, height = 0, 0
        if probe_result.returncode == 0:
            import json
            data = json.loads(probe_result.stdout)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    break

        return mp4_bytes, {
            'creation_date': creation_date,
            'width': width,
            'height': height,
            'original_size': original_size,
            'converted_size': converted_size,
        }

    finally:
        # Cleanup temp file
        if os.path.exists(output_path):
            os.unlink(output_path)


def generate_filename(
    folder,
    original_filename: str,
    file_date: Optional[datetime],
    is_video: bool
) -> str:
    """
    Generate a new filename based on folder naming format.

    Args:
        folder: PhotoFolder instance
        original_filename: Original uploaded filename
        file_date: Date from EXIF/metadata or None
        is_video: True if video, False if image

    Returns:
        New filename with appropriate extension
    """
    from apps.folders.models import NamingFormat

    # Use file date or current time
    dt = file_date if file_date else datetime.now()

    # Determine date string format based on naming format
    date_full = dt.strftime('%Y-%m-%d_%H%M%S')
    date_day = dt.strftime('%Y-%m-%d')
    date_hour = dt.strftime('%Y-%m-%d_%H')

    # Get extension
    ext = '.mp4' if is_video else '.jpg'

    # Generate base filename based on format
    event = folder.event_name.replace(' ', '_')

    if folder.naming_format == NamingFormat.DATE_EVENT:
        base_name = f"{date_full}_{event}"
    elif folder.naming_format == NamingFormat.EVENT_DATE:
        base_name = f"{event}_{date_full}"
    elif folder.naming_format == NamingFormat.DATE_ONLY:
        base_name = date_full
    elif folder.naming_format == NamingFormat.DATE_DAY_ONLY:
        base_name = date_day
    elif folder.naming_format == NamingFormat.DATE_DAY_EVENT:
        base_name = f"{date_day}_{event}"
    elif folder.naming_format == NamingFormat.EVENT_DATE_DAY:
        base_name = f"{event}_{date_day}"
    elif folder.naming_format == NamingFormat.DATE_HOUR_EVENT:
        base_name = f"{date_hour}_{event}"
    elif folder.naming_format == NamingFormat.EVENT_DATE_HOUR:
        base_name = f"{event}_{date_hour}"
    else:  # ORIGINAL
        base_name = Path(original_filename).stem

    return f"{base_name}{ext}"


def get_unique_filename(folder, filename: str, client) -> str:
    """
    Ensure filename is unique in the Nextcloud folder.

    Adds numeric suffix if file already exists.
    """
    base_path = folder.nextcloud_folder_path
    full_path = f"{base_path}/{filename}"

    if not client.file_exists(full_path):
        return filename

    # File exists, add suffix
    stem = Path(filename).stem
    ext = Path(filename).suffix

    counter = 1
    while True:
        new_filename = f"{stem}_{counter}{ext}"
        new_path = f"{base_path}/{new_filename}"
        if not client.file_exists(new_path):
            return new_filename
        counter += 1

        if counter > 9999:
            # Safety limit
            raise RuntimeError("Too many filename conflicts")
