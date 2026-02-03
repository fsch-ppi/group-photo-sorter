"""
Views for folder management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import PhotoFolder, UploadStatistics
from .serializers import (
    PhotoFolderListSerializer,
    PhotoFolderDetailSerializer,
    PhotoFolderCreateSerializer,
    UploadStatisticsSerializer,
    NamingFormatChoicesSerializer
)
from .nextcloud_client import NextcloudClient


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
            return NextcloudClient(profile.nextcloud_access_token, user_profile=profile)
        except Exception:
            return None

    def create(self, request, *args, **kwargs):
        """Create a new folder and set up Nextcloud folder + share."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create folder in Nextcloud
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
            folder.save()

        # Create README in the folder
        readme_content = self._generate_readme(folder)
        client.upload_file(
            f"{folder_path}/README.md",
            readme_content.encode('utf-8'),
            'text/markdown'
        )

        return Response(
            PhotoFolderDetailSerializer(folder).data,
            status=status.HTTP_201_CREATED
        )

    def _generate_readme(self, folder):
        """Generate README content for the folder."""
        content = f"# {folder.name}\n\n"
        content += f"**Event:** {folder.event_name}\n\n"

        if folder.readme_message:
            content += f"{folder.readme_message}\n\n"

        content += "---\n"
        content += f"*This folder was created by Photo Import Sorter*\n"
        content += f"*Upload link: {folder.upload_url}*\n"

        return content

    def destroy(self, request, *args, **kwargs):
        """Delete folder configuration and revoke Nextcloud share."""
        folder = self.get_object()

        # Revoke Nextcloud share if it exists
        if folder.nextcloud_share_token:
            client = self.get_nextcloud_client()
            if client:
                # Get existing shares and delete them
                shares_result = client.get_shares_for_path(
                    folder.nextcloud_folder_path)
                if shares_result['success']:
                    for share in shares_result['shares']:
                        if share.get('share_type') == 3:  # Public link
                            client.delete_share(share['id'])

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def regenerate_token(self, request, pk=None):
        """Regenerate the upload share token."""
        folder = self.get_object()
        new_token = folder.regenerate_share_token()
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

        # Get existing shares and delete them
        shares_result = client.get_shares_for_path(
            folder.nextcloud_folder_path)
        if shares_result['success']:
            for share in shares_result['shares']:
                if share.get('share_type') == 3:  # Public link
                    client.delete_share(share['id'])

        # Create new share
        share_result = client.create_public_share(
            folder.nextcloud_folder_path, permissions=1)

        if share_result['success']:
            folder.nextcloud_share_token = share_result['token']
            folder.save()
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

        # Aggregate statistics
        total_uploads = stats.count()
        total_size_original = sum(s.file_size_original for s in stats)
        total_size_converted = sum(s.file_size_converted for s in stats)

        # Group by IP
        ip_counts = {}
        for stat in stats:
            ip_counts[stat.uploader_ip] = ip_counts.get(
                stat.uploader_ip, 0) + 1

        # Recent uploads
        recent = UploadStatisticsSerializer(stats[:20], many=True).data

        return Response({
            'total_uploads': total_uploads,
            'total_size_original_bytes': total_size_original,
            'total_size_converted_bytes': total_size_converted,
            'uploads_by_ip': ip_counts,
            'recent_uploads': recent
        })

    @action(detail=False, methods=['get'])
    def naming_formats(self, request):
        """Get available naming format options."""
        return Response(NamingFormatChoicesSerializer.get_choices())
