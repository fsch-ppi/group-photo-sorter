"""
Views for handling file uploads.
"""

import logging
import os
import tempfile
from pathlib import Path

from celery.result import AsyncResult
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.cache_utils import append_to_cached_list, safe_cache_get
from apps.folders.models import PhotoFolder
from apps.folders.nextcloud_client import NextcloudClient
from .tasks import process_image_for_batch, process_uploaded_file

logger = logging.getLogger(__name__)

SESSION_CACHE_TTL = 7 * 24 * 60 * 60  # 7 days


def get_client_ip(request) -> str:
    """Extract client IP from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip or '0.0.0.0'


def _get_session_cache_key(share_token: str, session_id: str) -> str:
    return f"upload_session:{share_token}:{session_id}"


@api_view(['GET'])
@permission_classes([AllowAny])
def folder_info(request, share_token):
    """
    Get public folder info for upload page.

    Does not require authentication.
    """
    try:
        folder = PhotoFolder.objects.get(
            share_token=share_token, is_active=True
        )
    except PhotoFolder.DoesNotExist:
        return Response(
            {'error': 'Folder not found or uploads disabled'},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        'name': folder.name,
        'event_name': folder.event_name,
        'readme_message': folder.readme_message,
        'show_download_link': folder.show_download_link,
        'nextcloud_share_url': (
            folder.nextcloud_share_url if folder.show_download_link else None
        ),
        'supported_image_formats': sorted(settings.SUPPORTED_IMAGE_EXTENSIONS),
        'supported_video_formats': sorted(settings.SUPPORTED_VIDEO_EXTENSIONS),
        'max_upload_size_mb': settings.MAX_UPLOAD_SIZE_MB,
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser])
def upload_file(request, share_token):
    """
    Handle file upload from public upload page.

    Files are saved to temp storage and processed by Celery.
    """
    try:
        folder = PhotoFolder.objects.select_related('owner__profile').get(
            share_token=share_token, is_active=True
        )
    except PhotoFolder.DoesNotExist:
        return Response(
            {'error': 'Folder not found or uploads disabled'},
            status=status.HTTP_404_NOT_FOUND
        )

    if 'file' not in request.FILES:
        return Response(
            {'error': 'No file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )

    uploaded_file = request.FILES['file']
    original_filename = uploaded_file.name
    file_ext = Path(original_filename).suffix.lower()

    all_supported = settings.SUPPORTED_IMAGE_EXTENSIONS | settings.SUPPORTED_VIDEO_EXTENSIONS
    if file_ext not in all_supported:
        return Response(
            {'error': f'Unsupported file format: {file_ext}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    is_video = file_ext in settings.SUPPORTED_VIDEO_EXTENSIONS

    if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
        return Response(
            {'error': f'File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check storage limit before queuing (uses Redis-cached folder size)
    if folder.storage_limit_gb:
        try:
            profile = folder.owner.profile
            if profile.nextcloud_access_token:
                client = NextcloudClient(
                    profile.nextcloud_access_token, user_profile=profile
                )
                size_result = client.get_folder_size(
                    folder.nextcloud_folder_path
                )
                if size_result.get('success'):
                    current_size_gb = size_result['total_bytes'] / (1024 * 1024 * 1024)
                    upload_size_gb = uploaded_file.size / (1024 * 1024 * 1024)
                    if current_size_gb + upload_size_gb > folder.storage_limit_gb:
                        return Response(
                            {
                                'error': (
                                    f'Storage limit exceeded. Folder limit is '
                                    f'{folder.storage_limit_gb}GB, current usage is '
                                    f'{current_size_gb:.2f}GB.'
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
        except Exception as e:
            logger.warning(
                f"Failed to check storage limit for folder {folder.id}: {e}"
            )

    temp_dir = settings.TEMP_UPLOAD_DIR
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(temp_dir, 0o777)
    except Exception:
        pass

    with tempfile.NamedTemporaryFile(
        dir=temp_dir,
        suffix=file_ext,
        delete=False
    ) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        temp_path = tmp.name

    try:
        os.chmod(temp_path, 0o666)
    except Exception:
        pass

    client_ip = get_client_ip(request)
    use_batch = os.getenv('USE_IMAGE_BATCHING', 'false').lower() in ('true', '1', 'yes')

    if is_video:
        task = process_uploaded_file.apply_async(
            kwargs={
                'folder_id': folder.id,
                'temp_file_path': temp_path,
                'original_filename': original_filename,
                'uploader_ip': client_ip,
                'is_video': True
            },
            queue='low'
        )
    elif use_batch:
        task = process_image_for_batch.apply_async(
            kwargs={
                'folder_id': folder.id,
                'temp_file_path': temp_path,
                'original_filename': original_filename,
                'uploader_ip': client_ip
            },
            queue='high'
        )
    else:
        task = process_uploaded_file.apply_async(
            kwargs={
                'folder_id': folder.id,
                'temp_file_path': temp_path,
                'original_filename': original_filename,
                'uploader_ip': client_ip,
                'is_video': False
            },
            queue='high'
        )

    # Record task in Redis session cache if session_id was provided
    session_id = request.data.get('session_id') or request.POST.get('session_id')
    if session_id:
        session_key = _get_session_cache_key(share_token, str(session_id))
        append_to_cached_list(
            session_key,
            {
                'taskId': task.id,
                'name': original_filename,
                'size': uploaded_file.size,
            },
            timeout=SESSION_CACHE_TTL,
        )

    return Response({
        'success': True,
        'task_id': task.id,
        'message': 'File uploaded and queued for processing',
        'filename': original_filename,
        'nextcloud_share_url': (
            folder.nextcloud_share_url if folder.show_download_link else None
        ),
    }, status=status.HTTP_202_ACCEPTED)


def _serialize_async_result(task_id: str) -> dict:
    """Safely inspect Celery AsyncResult status without crashing on Redis errors."""
    try:
        result = AsyncResult(task_id)
        task_state = result.status
        payload = {
            'task_id': task_id,
            'status': task_state,
        }
        if result.successful():
            payload['result'] = result.result
        elif result.failed():
            payload['error'] = str(result.result)
        return payload
    except Exception as exc:
        logger.warning(f"Failed to query AsyncResult for task {task_id}: {exc}")
        return {
            'task_id': task_id,
            'status': 'PENDING',
        }


@api_view(['GET'])
@permission_classes([AllowAny])
def task_status(request, task_id):
    """
    Check the status of a processing task.
    """
    return Response(_serialize_async_result(task_id))


@api_view(['GET'])
@permission_classes([AllowAny])
def session_status(request, share_token, session_id):
    """
    Get statuses of all uploaded files in a guest upload session.
    """
    try:
        PhotoFolder.objects.get(share_token=share_token, is_active=True)
    except PhotoFolder.DoesNotExist:
        return Response(
            {'error': 'Folder not found or uploads disabled'},
            status=status.HTTP_404_NOT_FOUND
        )

    session_key = _get_session_cache_key(share_token, session_id)
    session_items = safe_cache_get(session_key, [])
    if not isinstance(session_items, list):
        session_items = []

    files = []
    for item in session_items:
        task_id = item.get('taskId')
        if not task_id:
            continue
        info = _serialize_async_result(task_id)
        file_entry = {
            'taskId': task_id,
            'name': item.get('name', ''),
            'size': item.get('size', 0),
            'status': info.get('status', 'PENDING'),
        }
        if 'result' in info:
            file_entry['result'] = info['result']
        if 'error' in info:
            file_entry['error'] = info['error']
        files.append(file_entry)

    return Response({'files': files})
