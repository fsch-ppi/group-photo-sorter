#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from datetime import datetime

# Optional imports with graceful fallbacks
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

try:
    import rawpy
    RAW_AVAILABLE = True
except ImportError:
    RAW_AVAILABLE = False


def get_image_metadata(path):
    if not PIL_AVAILABLE:
        return {"error": "Pillow not available"}

    metadata = {
        "creation_date": None,
        "width": 0,
        "height": 0,
        "type": "image"
    }

    ext = os.path.splitext(path)[1].lower()

    try:
        if ext in ['.cr2', '.nef', '.arw', '.dng', '.raw'] and RAW_AVAILABLE:
            with rawpy.imread(path) as raw:
                # RAW doesn't directly open with PIL, but we can get dimensions
                metadata["width"] = raw.sizes.width
                metadata["height"] = raw.sizes.height
                # Try to get EXIF from rawpy if possible
                try:
                    # Often raw files have embedded exif
                    pass
                except Exception:
                    pass
        else:
            with Image.open(path) as img:
                metadata["width"] = img.width
                metadata["height"] = img.height

                exif_data = img._getexif()
                if exif_data:
                    date_fields = [36867, 36868, 306]  # DateTimeOriginal, DateTimeDigitized, DateTime
                    dates = []
                    for field_id in date_fields:
                        if field_id in exif_data:
                            date_str = exif_data[field_id]
                            try:
                                dt = datetime.strptime(str(date_str), "%Y:%m:%d %H:%M:%S")
                                dates.append(dt)
                            except (ValueError, TypeError):
                                pass
                    if dates:
                        metadata["creation_date"] = min(dates).isoformat()
    except Exception as e:
        metadata["error"] = str(e)

    return metadata


def get_video_metadata(path):
    metadata = {
        "creation_date": None,
        "width": 0,
        "height": 0,
        "type": "video"
    }

    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                path
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            
            # Dimensions
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    metadata["width"] = int(stream.get('width', 0))
                    metadata["height"] = int(stream.get('height', 0))
                    break

            # Creation date
            tags = data.get('format', {}).get('tags', {})
            date_fields = ['creation_time', 'date', 'com.apple.quicktime.creationdate']
            for field in date_fields:
                if field in tags:
                    date_str = tags[field]
                    for fmt in [
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                        "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d",
                    ]:
                        try:
                            # Parse up to seconds
                            parsed = datetime.strptime(date_str[:19], fmt[:19])
                            metadata["creation_date"] = parsed.isoformat()
                            return metadata
                        except ValueError:
                            continue
    except Exception as e:
        metadata["error"] = str(e)

    return metadata


def convert_image(input_path, output_path, quality=90):
    if not PIL_AVAILABLE:
        print("Error: Pillow is required for image conversion.")
        sys.exit(1)

    ext = os.path.splitext(input_path)[1].lower()

    try:
        if ext in ['.cr2', '.nef', '.arw', '.dng', '.raw']:
            if not RAW_AVAILABLE:
                print("Error: rawpy is required for RAW formats.")
                sys.exit(1)
            with rawpy.imread(input_path) as raw:
                rgb = raw.postprocess()
                img = Image.fromarray(rgb)
        else:
            img = Image.open(input_path)

        # Transpose orientation based on EXIF
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Convert to RGB mode if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Save to output JPEG
        img.save(output_path, format='JPEG', quality=int(quality), optimize=True)
        print(json.dumps({"success": True}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: converter.py [metadata|convert-image] [args...]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "metadata":
        if len(sys.argv) < 3:
            print("Usage: converter.py metadata <file_path>")
            sys.exit(1)
        path = sys.argv[2]
        
        # Check file extension to decide metadata method
        ext = os.path.splitext(path)[1].lower()
        video_exts = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.hevc', '.m4v', '.wmv', '.flv', '.3gp']
        
        if ext in video_exts:
            res = get_video_metadata(path)
        else:
            res = get_image_metadata(path)
        
        print(json.dumps(res))

    elif cmd == "convert-image":
        if len(sys.argv) < 4:
            print("Usage: converter.py convert-image <input_path> <output_path> [quality]")
            sys.exit(1)
        input_path = sys.argv[2]
        output_path = sys.argv[3]
        quality = sys.argv[4] if len(sys.argv) > 4 else 90
        convert_image(input_path, output_path, quality)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
