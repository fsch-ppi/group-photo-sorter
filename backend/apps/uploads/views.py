"""
Views for handling file uploads.
"""

import os
import tempfile
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.folders.models import PhotoFolder
from .tasks import process_uploaded_file


def get_client_ip(request):
    """Extract client IP from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


@api_view(['GET'])
@permission_classes([AllowAny])
def folder_info(request, share_token):
    """
    Get public folder info for upload page.

    Does not require authentication.
    """
    try:
        folder = PhotoFolder.objects.get(
            share_token=share_token, is_active=True)
    except PhotoFolder.DoesNotExist:
        return Response(
            {'error': 'Folder not found or uploads disabled'},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        'name': folder.name,
        'event_name': folder.event_name,
        'nextcloud_share_url': folder.nextcloud_share_url,
        'supported_image_formats': list(settings.SUPPORTED_IMAGE_EXTENSIONS),
        'supported_video_formats': list(settings.SUPPORTED_VIDEO_EXTENSIONS),
        'max_upload_size_mb': settings.MAX_UPLOAD_SIZE_MB,
    })


@api_view(['POST'])
# Disable authentication to skip CSRF from SessionAuthentication
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser])
def upload_file(request, share_token):
    """
    Handle file upload from public upload page.

    Files are saved to temp storage and processed by Celery.
    """
    # Validate folder
    try:
        folder = PhotoFolder.objects.get(
            share_token=share_token, is_active=True)
    except PhotoFolder.DoesNotExist:
        return Response(
            {'error': 'Folder not found or uploads disabled'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Check for file in request
    if 'file' not in request.FILES:
        return Response(
            {'error': 'No file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )

    uploaded_file = request.FILES['file']
    original_filename = uploaded_file.name
    file_ext = Path(original_filename).suffix.lower()

    # Validate file type
    all_supported = settings.SUPPORTED_IMAGE_EXTENSIONS | settings.SUPPORTED_VIDEO_EXTENSIONS
    if file_ext not in all_supported:
        return Response(
            {'error': f'Unsupported file format: {file_ext}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    is_video = file_ext in settings.SUPPORTED_VIDEO_EXTENSIONS

    # Check file size
    if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
        return Response(
            {'error': f'File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Save to temp file
    temp_dir = settings.TEMP_UPLOAD_DIR
    temp_dir.mkdir(parents=True, exist_ok=True)
    # Ensure temp dir is accessible by celery worker
    os.chmod(temp_dir, 0o777)

    with tempfile.NamedTemporaryFile(
        dir=temp_dir,
        suffix=file_ext,
        delete=False
    ) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        temp_path = tmp.name

    # Make temp file readable by celery worker
    os.chmod(temp_path, 0o666)

    # Get client IP
    client_ip = get_client_ip(request)

    # Queue processing task
    task = process_uploaded_file.delay(
        folder_id=folder.id,
        temp_file_path=temp_path,
        original_filename=original_filename,
        uploader_ip=client_ip,
        is_video=is_video
    )

    return Response({
        'success': True,
        'task_id': task.id,
        'message': 'File uploaded and queued for processing',
        'filename': original_filename,
        'nextcloud_share_url': folder.nextcloud_share_url,
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([AllowAny])
def task_status(request, task_id):
    """
    Check the status of a processing task.
    """
    from celery.result import AsyncResult

    result = AsyncResult(task_id)

    response = {
        'task_id': task_id,
        'status': result.status,
    }

    if result.successful():
        response['result'] = result.result
    elif result.failed():
        response['error'] = str(result.result)

    return Response(response)
