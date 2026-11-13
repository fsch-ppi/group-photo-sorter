"""
Views for folder management.
"""

from django.db.models import Count, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.cache_utils import safe_cache_delete
from .models import PhotoFolder
from .nextcloud_client import NextcloudClient
from .serializers import (
    NamingFormatChoicesSerializer,
    PhotoFolderCreateSerializer,
    PhotoFolderDetailSerializer,
    PhotoFolderListSerializer,
    UploadStatisticsSerializer,
)


class PhotoFolderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing photo folders."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only folders owned by the current user."""
        return PhotoFolder.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return PhotoFolderListSerializer
        elif self.action == 'create':
            return PhotoFolderCreateSerializer
        return PhotoFolderDetailSerializer

    def get_nextcloud_client(self):
        """Get Nextcloud client for the current user."""
        try:
            profile = self.request.user.profile
            if not profile.nextcloud_access_token:
                return None
            return NextcloudClient(profile.nextcloud_access_token, user_profile=profile)
        except Exception:
            return None

    def create(self, request, *args, **kwargs):
        """Create a new folder and set up Nextcloud folder + share."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client = self.get_nextcloud_client()
        if not client:
            return Response(
                {'error': 'Nextcloud connection not available. Please re-authenticate.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        folder_path = serializer.validated_data['nextcloud_folder_path']

        # Create folder in Nextcloud
        result = client.create_folder(folder_path)
        if not result['success']:
            return Response(
                {'error': f"Failed to create Nextcloud folder: {result.get('error', 'Unknown error')}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create public share for the folder (read-only)
        share_result = client.create_public_share(folder_path, permissions=1)

        # Save the folder
        folder = serializer.save()

        if share_result['success']:
            folder.nextcloud_share_token = share_result['token']
            folder.save(update_fields=['nextcloud_share_token', 'updated_at'])

        # Create README in the folder
        self._sync_readme(folder, client)

        return Response(
            PhotoFolderDetailSerializer(folder).data,
            status=status.HTTP_201_CREATED
        )

    def perform_update(self, serializer):
        folder = serializer.save()
        client = self.get_nextcloud_client()
        if client:
            self._sync_readme(folder, client)

    def _sync_readme(self, folder, client) -> None:
        """Best-effort update of README.md in the Nextcloud folder."""
        try:
            readme_content = self._generate_readme(folder)
            client.upload_file(
                f"{folder.nextcloud_folder_path}/README.md",
                readme_content.encode('utf-8'),
                'text/markdown'
            )
        except Exception:
            pass

    def _generate_readme(self, folder):
        """Generate README content for the folder."""
        content = f"# {folder.name}\n\n"
        content += f"**Event:** {folder.event_name}\n\n"

        if folder.readme_message:
            content += f"{folder.readme_message}\n\n"

        content += "---\n"
        content += "*This folder was created by Photo Import Sorter*\n"
        content += f"*Upload link: {folder.upload_url}*\n"

        return content

    def destroy(self, request, *args, **kwargs):
        """Delete folder configuration and revoke Nextcloud share."""
        folder = self.get_object()

        # Revoke Nextcloud share if it exists
        if folder.nextcloud_share_token:
            client = self.get_nextcloud_client()
            if client:
                shares_result = client.get_shares_for_path(
                    folder.nextcloud_folder_path
                )
                if shares_result['success']:
                    for share in shares_result['shares']:
                        if share.get('share_type') == 3:  # Public link
                            client.delete_share(share['id'])

        safe_cache_delete(f"folder_filenames:{folder.id}")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def regenerate_token(self, request, pk=None):
        """Regenerate the upload share token."""
        folder = self.get_object()
        new_token = folder.regenerate_share_token()
        client = self.get_nextcloud_client()
        if client:
            self._sync_readme(folder, client)
        return Response({
            'share_token': new_token,
            'upload_url': folder.upload_url
        })

    @action(detail=True, methods=['post'])
    def regenerate_nextcloud_share(self, request, pk=None):
        """Regenerate the Nextcloud public share link."""
        folder = self.get_object()

        client = self.get_nextcloud_client()
        if not client:
            return Response(
                {'error': 'Nextcloud connection not available'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        shares_result = client.get_shares_for_path(
            folder.nextcloud_folder_path
        )
        if shares_result['success']:
            for share in shares_result['shares']:
                if share.get('share_type') == 3:  # Public link
                    client.delete_share(share['id'])

        share_result = client.create_public_share(
            folder.nextcloud_folder_path, permissions=1
        )

        if share_result['success']:
            folder.nextcloud_share_token = share_result['token']
            folder.save(update_fields=['nextcloud_share_token', 'updated_at'])
            return Response({
                'nextcloud_share_token': folder.nextcloud_share_token,
                'nextcloud_share_url': folder.nextcloud_share_url
            })

        return Response(
            {'error': 'Failed to create new share'},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get upload statistics for a folder."""
        folder = self.get_object()
        stats = folder.statistics.all()

        agg = stats.aggregate(
            total_uploads=Count('id'),
            total_original=Sum('file_size_original'),
            total_converted=Sum('file_size_converted'),
        )

        ip_rows = stats.values('uploader_ip').annotate(count=Count('id'))
        ip_counts = {row['uploader_ip']: row['count'] for row in ip_rows}

        recent = UploadStatisticsSerializer(stats[:20], many=True).data

        return Response({
            'total_uploads': agg['total_uploads'] or 0,
            'total_size_original_bytes': agg['total_original'] or 0,
            'total_size_converted_bytes': agg['total_converted'] or 0,
            'uploads_by_ip': ip_counts,
            'recent_uploads': recent
        })

    @action(detail=False, methods=['get'])
    def naming_formats(self, request):
        """Get available naming format options."""
        return Response(NamingFormatChoicesSerializer.get_choices())
