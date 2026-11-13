"""
Celery tasks for file processing.
"""

import base64
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Set

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, Retry
from django.conf import settings
from django.utils import timezone

from apps.core.cache_utils import (
    redis_lock,
    safe_cache_delete,
    safe_cache_get,
    safe_cache_set,
)
from apps.folders.models import PhotoFolder, UploadStatistics
from apps.folders.nextcloud_client import NextcloudClient
from .converters import (
    convert_image_to_jpeg,
    convert_video_to_mp4,
    generate_filename,
    get_unique_filename,
)

logger = logging.getLogger(__name__)

# GDPR: IP address retention period
IP_RETENTION_DAYS = 30

# Batch settings for image uploads
IMAGE_BATCH_SIZE = 20
IMAGE_BATCH_TIMEOUT = 30  # seconds to wait before flushing partial batch
IMAGE_BATCH_CACHE_TTL = 86400  # 24 hours (prevents premature Redis eviction)


@shared_task
def cleanup_temp_files():
    """
    Clean up old temporary files that weren't properly deleted.
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
                logger.warning(f"Failed to clean up {filepath}: {e}")

    return {'cleaned': cleaned_count, 'max_age_hours': max_age_hours}


@shared_task
def anonymize_old_ip_addresses():
    """
    GDPR compliance: Anonymize IP addresses older than 30 days.
    """
    cutoff_date = timezone.now() - timedelta(days=IP_RETENTION_DAYS)

    old_records = UploadStatistics.objects.filter(
        uploaded_at__lt=cutoff_date
    ).exclude(
        uploader_ip='0.0.0.0'
    ).exclude(
        uploader_ip='xxx.xxx.xxx.xxx'
    )

    count = old_records.count()
    old_records.update(uploader_ip='0.0.0.0')

    return {
        'anonymized_count': count,
        'retention_days': IP_RETENTION_DAYS,
        'cutoff_date': cutoff_date.isoformat(),
    }


def _get_batch_key(folder_id: int) -> str:
    """Get Redis cache key for image batch."""
    return f"image_batch:{folder_id}"


def _get_batch_mutex_name(folder_id: int) -> str:
    """Get distributed lock name for reading/modifying image batch."""
    return f"image_batch_mutex:{folder_id}"


def _get_batch_flush_lock_name(folder_id: int) -> str:
    """Get distributed lock name for flushing image batch."""
    return f"image_batch_flush:{folder_id}"


@shared_task(bind=True, max_retries=3)
def process_image_for_batch(
    self,
    folder_id: int,
    temp_file_path: str,
    original_filename: str,
    uploader_ip: str
):
    """
    Convert an image and add it to the batch queue safely using distributed Redis locks.
    """
    start_time = time.time()

    try:
        folder = PhotoFolder.objects.select_related(
            'owner__profile'
        ).get(id=folder_id)
        profile = folder.owner.profile

        if not profile.nextcloud_access_token:
            raise RuntimeError("Owner's Nextcloud access token not available")

        converted_bytes, metadata = convert_image_to_jpeg(
            temp_file_path,
            quality=folder.jpeg_quality
        )
        file_date = metadata.get('exif_date')
        mtime = int(file_date.timestamp()) if file_date else int(time.time())

        new_filename = generate_filename(
            folder,
            original_filename,
            file_date,
            is_video=False
        )

        conversion_time = time.time() - start_time

        batch_item = {
            'item_id': f"{self.request.id or int(time.time() * 1000)}_{os.path.basename(temp_file_path)}",
            'remote_path': f"{folder.nextcloud_folder_path}/{new_filename}",
            'content_b64': base64.b64encode(converted_bytes).decode('ascii'),
            'content_type': 'image/jpeg',
            'original_filename': original_filename,
            'new_filename': new_filename,
            'uploader_ip': uploader_ip,
            'original_size': metadata['original_size'],
            'converted_size': metadata['converted_size'],
            'conversion_time': conversion_time,
            'mtime': mtime,
        }

        batch_key = _get_batch_key(folder_id)
        with redis_lock(_get_batch_mutex_name(folder_id), timeout=15, wait_timeout=10.0) as acquired:
            if not acquired:
                # If Redis lock is unavailable, fall back to direct upload so the file is never lost
                client = NextcloudClient(profile.nextcloud_access_token, user_profile=profile)
                unique_filename = get_unique_filename(folder, new_filename, client)
                remote_path = f"{folder.nextcloud_folder_path}/{unique_filename}"
                up_res = client.upload_file(remote_path, converted_bytes, 'image/jpeg', mtime=mtime)
                if not up_res['success']:
                    raise RuntimeError(f"Direct fallback upload failed: {up_res.get('error')}")
                UploadStatistics.objects.create(
                    folder=folder,
                    uploader_ip=uploader_ip,
                    filename_original=original_filename,
                    filename_converted=unique_filename,
                    file_size_original=metadata['original_size'],
                    file_size_converted=metadata['converted_size'],
                    file_type='image',
                    conversion_time_seconds=conversion_time,
                )
                if os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception:
                        pass
                return {
                    'success': True,
                    'queued_for_batch': False,
                    'filename': unique_filename,
                    'original_size': metadata['original_size'],
                    'converted_size': metadata['converted_size'],
                    'conversion_time': conversion_time,
                }

            batch_data = safe_cache_get(batch_key, [])
            if not isinstance(batch_data, list):
                batch_data = []
            batch_data.append(batch_item)
            saved = safe_cache_set(batch_key, batch_data, timeout=IMAGE_BATCH_CACHE_TTL)
            batch_len = len(batch_data)

        if not saved:
            raise RuntimeError("Failed to persist image batch in Redis")

        if batch_len >= IMAGE_BATCH_SIZE:
            flush_image_batch.delay(folder_id)
        else:
            flush_image_batch.apply_async(
                args=[folder_id],
                countdown=IMAGE_BATCH_TIMEOUT
            )

        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

        return {
            'success': True,
            'queued_for_batch': True,
            'batch_size': batch_len,
            'filename': new_filename,
            'original_size': metadata['original_size'],
            'converted_size': metadata['converted_size'],
            'conversion_time': conversion_time,
        }

    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
            raise


@shared_task(bind=True, max_retries=5)
def flush_image_batch(self, folder_id: int):
    """
    Upload queued images for a folder without race conditions or data loss.
    """
    batch_key = _get_batch_key(folder_id)

    with redis_lock(_get_batch_flush_lock_name(folder_id), timeout=180, wait_timeout=1.0) as acquired:
        if not acquired:
            # Another flush is currently running; reschedule so remaining items aren't stranded
            remaining = safe_cache_get(batch_key, [])
            if remaining:
                flush_image_batch.apply_async(args=[folder_id], countdown=10)
            return {'skipped': True, 'reason': 'flush_in_progress_rescheduled'}

        try:
            # Snapshot current batch without deleting it yet (prevents data loss on crash)
            with redis_lock(_get_batch_mutex_name(folder_id), timeout=15, wait_timeout=10.0):
                batch_data = safe_cache_get(batch_key, [])
                if not batch_data:
                    return {'success': True, 'uploaded': 0, 'reason': 'empty_batch'}
                items_to_process = list(batch_data[:IMAGE_BATCH_SIZE])

            folder = PhotoFolder.objects.select_related(
                'owner__profile'
            ).get(id=folder_id)
            profile = folder.owner.profile

            if not profile.nextcloud_access_token:
                raise RuntimeError("Owner's Nextcloud access token not available")

            client = NextcloudClient(
                profile.nextcloud_access_token, user_profile=profile
            )

            reserved_names: Set[str] = set()
            files_to_upload = []
            for item in items_to_process:
                unique_filename = get_unique_filename(
                    folder,
                    item['new_filename'],
                    client,
                    reserved_names=reserved_names,
                )
                files_to_upload.append({
                    'remote_path': f"{folder.nextcloud_folder_path}/{unique_filename}",
                    'content': base64.b64decode(item['content_b64']),
                    'content_type': item['content_type'],
                    'mtime': item.get('mtime', int(time.time())),
                    '_original': item,
                    '_unique_filename': unique_filename,
                })

            result = client.bulk_upload(files_to_upload)
            succeeded_ids: Set[str] = set()

            if result.get('success'):
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
                    if original.get('item_id'):
                        succeeded_ids.add(original['item_id'])
                upload_method = 'bulk'
            else:
                # Fall back to individual WebDAV PUT uploads with mtime preserved
                for file_info in files_to_upload:
                    original = file_info['_original']
                    individual_result = client.upload_file(
                        file_info['remote_path'],
                        file_info['content'],
                        file_info['content_type'],
                        mtime=file_info['mtime'],
                    )
                    if individual_result.get('success'):
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
                        if original.get('item_id'):
                            succeeded_ids.add(original['item_id'])
                upload_method = 'individual'

            # Atomically remove only the succeeded items from Redis batch_key
            remaining_count = 0
            with redis_lock(_get_batch_mutex_name(folder_id), timeout=15, wait_timeout=10.0):
                current_batch = safe_cache_get(batch_key, [])
                if isinstance(current_batch, list):
                    updated_batch = [
                        it for it in current_batch
                        if it.get('item_id') not in succeeded_ids
                    ]
                    remaining_count = len(updated_batch)
                    if updated_batch:
                        safe_cache_set(batch_key, updated_batch, timeout=IMAGE_BATCH_CACHE_TTL)
                    else:
                        safe_cache_delete(batch_key)

            if len(succeeded_ids) < len(files_to_upload):
                failed_cnt = len(files_to_upload) - len(succeeded_ids)
                raise RuntimeError(f"Failed to upload {failed_cnt} file(s) in batch")

            # If more items arrived while we were uploading, trigger another flush
            if remaining_count > 0:
                flush_image_batch.apply_async(args=[folder_id], countdown=2)

            return {
                'success': True,
                'uploaded': len(succeeded_ids),
                'folder_id': folder_id,
                'method': upload_method,
            }

        except Exception as exc:
            raise self.retry(exc=exc, countdown=30)


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

    Uses Redis-cached Nextcloud user metadata, Redis-locked unique filename
    reservation, and persistent HTTP connection pooling so each file upload
    requires only a single WebDAV PUT request and only reports SUCCESS after
    Nextcloud confirms the upload.
    """
    start_time = time.time()
    converted_file_path = None

    try:
        folder = PhotoFolder.objects.select_related(
            'owner__profile'
        ).get(id=folder_id)
        profile = folder.owner.profile

        if not profile.nextcloud_access_token:
            raise RuntimeError("Owner's Nextcloud access token not available")

        client = NextcloudClient(
            profile.nextcloud_access_token, user_profile=profile
        )

        if is_video:
            # Acquire non-blocking video encode lock; if another worker is already encoding a video,
            # reschedule this video on the low queue so this worker stays free to process high-priority photos!
            with redis_lock("video_ffmpeg_encode_lock", timeout=3600, wait_timeout=0) as acquired:
                if not acquired:
                    raise self.retry(countdown=15, max_retries=240, queue='low')
                converted_file_path, metadata = convert_video_to_mp4(
                    temp_file_path,
                    crf=settings.VIDEO_CRF,
                    stream_mode=True
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

        mtime = int(file_date.timestamp()) if file_date else int(time.time())

        new_filename = generate_filename(
            folder,
            original_filename,
            file_date,
            is_video
        )

        unique_filename = get_unique_filename(folder, new_filename, client)
        remote_path = f"{folder.nextcloud_folder_path}/{unique_filename}"

        if is_video:
            result = client.upload_file_streaming(
                remote_path,
                converted_file_path,
                content_type,
                mtime=mtime,
            )
            if converted_file_path and os.path.exists(converted_file_path):
                os.unlink(converted_file_path)
                converted_file_path = None
        else:
            result = client.upload_file(
                remote_path,
                converted_bytes,
                content_type,
                mtime=mtime,
            )

        if not result['success']:
            raise RuntimeError(f"Upload failed: {result.get('error')}")

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

        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

        return {
            'success': True,
            'filename': unique_filename,
            'original_size': metadata['original_size'],
            'converted_size': metadata['converted_size'],
            'conversion_time': conversion_time
        }

    except Retry:
        raise
    except Exception as exc:
        if converted_file_path and os.path.exists(converted_file_path):
            try:
                os.unlink(converted_file_path)
            except Exception:
                pass
        try:
            raise self.retry(exc=exc, countdown=30, max_retries=3)
        except MaxRetriesExceededError:
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
            raise
