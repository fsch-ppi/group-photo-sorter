"""
Celery tasks for file processing.
"""

import json
import os
import time
import glob
from datetime import datetime, timedelta
from pathlib import Path
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.folders.models import PhotoFolder, UploadStatistics
from apps.folders.nextcloud_client import NextcloudClient
from .converters import (
    convert_image_to_jpeg,
    convert_video_to_mp4,
    generate_filename,
    get_unique_filename
)


# GDPR: IP address retention period
IP_RETENTION_DAYS = 30

# Batch settings for image uploads
IMAGE_BATCH_SIZE = 20
IMAGE_BATCH_TIMEOUT = 30  # seconds to wait before flushing partial batch


@shared_task
def cleanup_temp_files():
    """
    Clean up old temporary files that weren't properly deleted.

    This runs periodically to ensure temp files don't accumulate.
    Files are normally deleted immediately after processing, but this
    catches any orphaned files from failed tasks.
    """
    temp_dir = settings.TEMP_UPLOAD_DIR
    max_age_hours = settings.TEMP_FILE_MAX_AGE_HOURS

    if not temp_dir.exists():
        return {'cleaned': 0, 'message': 'Temp directory does not exist'}

    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    cleaned_count = 0

    for filepath in temp_dir.glob('*'):
        if filepath.is_file():
            try:
                file_mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                if file_mtime < cutoff_time:
                    filepath.unlink()
                    cleaned_count += 1
            except Exception as e:
                # Log but don't fail the task
                print(f"Failed to clean up {filepath}: {e}")

    return {'cleaned': cleaned_count, 'max_age_hours': max_age_hours}


@shared_task
def anonymize_old_ip_addresses():
    """
    GDPR compliance: Anonymize IP addresses older than 30 days.

    This task runs daily and replaces real IP addresses with
    anonymized versions (e.g., "192.168.1.100" -> "xxx.xxx.xxx.xxx")
    for upload statistics older than the retention period.
    """
    cutoff_date = timezone.now() - timedelta(days=IP_RETENTION_DAYS)

    # Find all records with non-anonymized IPs older than retention period
    old_records = UploadStatistics.objects.filter(
        uploaded_at__lt=cutoff_date
    ).exclude(
        uploader_ip='xxx.xxx.xxx.xxx'
    )

    count = old_records.count()

    # Anonymize the IP addresses
    old_records.update(uploader_ip='xxx.xxx.xxx.xxx')

    return {
        'anonymized_count': count,
        'retention_days': IP_RETENTION_DAYS,
        'cutoff_date': cutoff_date.isoformat(),
    }


def _get_batch_key(folder_id: int) -> str:
    """Get Redis cache key for image batch."""
    return f"image_batch:{folder_id}"


def _get_batch_lock_key(folder_id: int) -> str:
    """Get Redis lock key for batch processing."""
    return f"image_batch_lock:{folder_id}"


@shared_task(bind=True, max_retries=3)
def process_image_for_batch(
    self,
    folder_id: int,
    temp_file_path: str,
    original_filename: str,
    uploader_ip: str
):
    """
    Convert an image and add it to the batch queue.
    
    Images are converted immediately but uploaded in batches of 20
    to avoid Nextcloud rate limiting.
    """
    start_time = time.time()
    
    try:
        folder = PhotoFolder.objects.select_related('owner__profile').get(id=folder_id)
        profile = folder.owner.profile
        
        if not profile.nextcloud_access_token:
            raise RuntimeError("Owner's Nextcloud access token not available")
        
        # Convert the image
        converted_bytes, metadata = convert_image_to_jpeg(
            temp_file_path,
            quality=folder.jpeg_quality
        )
        file_date = metadata.get('exif_date')
        
        # Generate filename (we'll verify uniqueness during batch upload)
        new_filename = generate_filename(
            folder,
            original_filename,
            file_date,
            is_video=False
        )
        
        conversion_time = time.time() - start_time
        
        # Create the batch item
        batch_item = {
            'remote_path': f"{folder.nextcloud_folder_path}/{new_filename}",
            'content_b64': __import__('base64').b64encode(converted_bytes).decode('ascii'),
            'content_type': 'image/jpeg',
            'original_filename': original_filename,
            'new_filename': new_filename,
            'uploader_ip': uploader_ip,
            'original_size': metadata['original_size'],
            'converted_size': metadata['converted_size'],
            'conversion_time': conversion_time,
            'mtime': int(time.time()),
        }
        
        # Add to batch in Redis
        batch_key = _get_batch_key(folder_id)
        
        # Get current batch
        batch_data = cache.get(batch_key, [])
        batch_data.append(batch_item)
        
        # Save batch back (with 5 minute expiry as safety)
        cache.set(batch_key, batch_data, timeout=300)
        
        # Check if batch is full
        if len(batch_data) >= IMAGE_BATCH_SIZE:
            # Trigger batch upload
            flush_image_batch.delay(folder_id)
        else:
            # Schedule a delayed flush in case no more images come
            flush_image_batch.apply_async(
                args=[folder_id],
                countdown=IMAGE_BATCH_TIMEOUT
            )
        
        return {
            'success': True,
            'queued_for_batch': True,
            'batch_size': len(batch_data),
            'filename': new_filename,
        }
        
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
    
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


@shared_task(bind=True, max_retries=3)
def flush_image_batch(self, folder_id: int):
    """
    Upload all queued images for a folder in a single bulk request.
    """
    import base64
    
    batch_key = _get_batch_key(folder_id)
    lock_key = _get_batch_lock_key(folder_id)
    
    # Use a lock to prevent concurrent batch flushes
    if cache.get(lock_key):
        # Another flush is in progress, skip
        return {'skipped': True, 'reason': 'flush_in_progress'}
    
    # Set lock with 60 second expiry
    cache.set(lock_key, True, timeout=60)
    
    try:
        # Get and clear the batch atomically
        batch_data = cache.get(batch_key, [])
        if not batch_data:
            return {'success': True, 'uploaded': 0, 'reason': 'empty_batch'}
        
        # Clear the batch from cache
        cache.delete(batch_key)
        
        # Get folder and client
        folder = PhotoFolder.objects.select_related('owner__profile').get(id=folder_id)
        profile = folder.owner.profile
        
        if not profile.nextcloud_access_token:
            # Re-queue the batch items for later
            cache.set(batch_key, batch_data, timeout=300)
            raise RuntimeError("Owner's Nextcloud access token not available")
        
        client = NextcloudClient(profile.nextcloud_access_token)
        
        # Prepare files for bulk upload
        files_to_upload = []
        for item in batch_data:
            # Ensure unique filename
            unique_filename = get_unique_filename(
                folder, 
                item['new_filename'], 
                client
            )
            
            files_to_upload.append({
                'remote_path': f"{folder.nextcloud_folder_path}/{unique_filename}",
                'content': base64.b64decode(item['content_b64']),
                'content_type': item['content_type'],
                'mtime': item['mtime'],
                # Keep original data for statistics
                '_original': item,
                '_unique_filename': unique_filename,
            })
        
        # Bulk upload to Nextcloud
        result = client.bulk_upload(files_to_upload)
        
        if not result['success']:
            # Re-queue failed items
            cache.set(batch_key, batch_data, timeout=300)
            raise RuntimeError(f"Bulk upload failed: {result.get('error')}")
        
        # Record statistics for each uploaded file
        for file_info in files_to_upload:
            original = file_info['_original']
            UploadStatistics.objects.create(
                folder=folder,
                uploader_ip=original['uploader_ip'],
                filename_original=original['original_filename'],
                filename_converted=file_info['_unique_filename'],
                file_size_original=original['original_size'],
                file_size_converted=original['converted_size'],
                file_type='image',
                conversion_time_seconds=original['conversion_time']
            )
        
        return {
            'success': True,
            'uploaded': len(files_to_upload),
            'folder_id': folder_id,
        }
        
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
    
    finally:
        # Release lock
        cache.delete(lock_key)


@shared_task(bind=True, max_retries=3)
def process_uploaded_file(
    self,
    folder_id: int,
    temp_file_path: str,
    original_filename: str,
    uploader_ip: str,
    is_video: bool
):
    """
    Process an uploaded file: convert and upload to Nextcloud.

    Args:
        folder_id: PhotoFolder ID
        temp_file_path: Path to temporary uploaded file
        original_filename: Original filename from upload
        uploader_ip: IP address of uploader
        is_video: True if video file, False if image
    """
    start_time = time.time()

    try:
        # Get folder and owner's Nextcloud credentials
        folder = PhotoFolder.objects.select_related(
            'owner__profile').get(id=folder_id)
        profile = folder.owner.profile

        if not profile.nextcloud_access_token:
            raise RuntimeError("Owner's Nextcloud access token not available")

        client = NextcloudClient(profile.nextcloud_access_token)

        # Convert file
        if is_video:
            converted_bytes, metadata = convert_video_to_mp4(
                temp_file_path,
                crf=settings.VIDEO_CRF
            )
            file_date = metadata.get('creation_date')
            content_type = 'video/mp4'
        else:
            converted_bytes, metadata = convert_image_to_jpeg(
                temp_file_path,
                quality=folder.jpeg_quality
            )
            file_date = metadata.get('exif_date')
            content_type = 'image/jpeg'

        # Generate filename
        new_filename = generate_filename(
            folder,
            original_filename,
            file_date,
            is_video
        )

        # Ensure unique filename
        unique_filename = get_unique_filename(folder, new_filename, client)

        # Upload to Nextcloud
        remote_path = f"{folder.nextcloud_folder_path}/{unique_filename}"
        result = client.upload_file(remote_path, converted_bytes, content_type)

        if not result['success']:
            raise RuntimeError(f"Upload failed: {result.get('error')}")

        # Record statistics
        conversion_time = time.time() - start_time
        UploadStatistics.objects.create(
            folder=folder,
            uploader_ip=uploader_ip,
            filename_original=original_filename,
            filename_converted=unique_filename,
            file_size_original=metadata['original_size'],
            file_size_converted=metadata['converted_size'],
            file_type='video' if is_video else 'image',
            conversion_time_seconds=conversion_time
        )

        return {
            'success': True,
            'filename': unique_filename,
            'original_size': metadata['original_size'],
            'converted_size': metadata['converted_size'],
            'conversion_time': conversion_time
        }

    except Exception as exc:
        # Retry on failure
        raise self.retry(exc=exc, countdown=60)

    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
