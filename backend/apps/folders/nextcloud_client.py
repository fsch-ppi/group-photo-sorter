"""
Nextcloud API client for folder and file operations.
"""

import requests
from django.conf import settings
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET


class NextcloudClient:
    """Client for interacting with Nextcloud WebDAV and OCS APIs."""

    def __init__(self, access_token: str):
        self.base_url = settings.NEXTCLOUD_URL.rstrip('/')
        self.access_token = access_token
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'OCS-APIRequest': 'true',
        }

    @property
    def webdav_url(self) -> str:
        return f"{self.base_url}/remote.php/dav/files"

    def _get_username(self) -> Optional[str]:
        """Get the current user's username."""
        url = f"{self.base_url}/ocs/v2.php/cloud/user"
        response = requests.get(
            url,
            headers={**self.headers, 'Accept': 'application/json'}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('ocs', {}).get('data', {}).get('id')
        return None

    def create_folder(self, path: str) -> Dict[str, Any]:
        """
        Create a folder in Nextcloud.

        Args:
            path: Folder path relative to user's root (e.g., 'Photos/Wedding2026')

        Returns:
            Dict with success status and message
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        # Ensure path doesn't start with /
        path = path.lstrip('/')

        # Create parent directories if needed
        parts = path.split('/')
        current_path = ''

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            url = f"{self.webdav_url}/{username}/{current_path}"

            response = requests.request(
                'MKCOL',
                url,
                headers=self.headers
            )

            # 201 = created, 405 = already exists (both are OK)
            if response.status_code not in [201, 405]:
                return {
                    'success': False,
                    'error': f'Failed to create folder: {response.status_code} {response.text}'
                }

        return {'success': True, 'path': path}

    def upload_file(self, remote_path: str, file_content: bytes, content_type: str = 'application/octet-stream') -> Dict[str, Any]:
        """
        Upload a file to Nextcloud.

        Args:
            remote_path: Full path including filename (e.g., 'Photos/Wedding/photo1.jpg')
            file_content: File content as bytes
            content_type: MIME type of the file

        Returns:
            Dict with success status
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        remote_path = remote_path.lstrip('/')
        url = f"{self.webdav_url}/{username}/{remote_path}"

        response = requests.put(
            url,
            headers={**self.headers, 'Content-Type': content_type},
            data=file_content
        )

        if response.status_code in [201, 204]:
            return {'success': True, 'path': remote_path}

        return {
            'success': False,
            'error': f'Failed to upload file: {response.status_code} {response.text}'
        }

    def create_public_share(self, path: str, permissions: int = 1) -> Dict[str, Any]:
        """
        Create a public share link for a folder.

        Args:
            path: Folder path relative to user's root
            permissions: 1 = read, 2 = update, 4 = create, 8 = delete, 16 = share
                        For read-only: 1

        Returns:
            Dict with share token and URL
        """
        url = f"{self.base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares"

        response = requests.post(
            url,
            headers={**self.headers, 'Accept': 'application/json'},
            data={
                'path': f'/{path.lstrip("/")}',
                'shareType': 3,  # Public link
                'permissions': permissions,
            }
        )

        if response.status_code in [200, 201]:
            data = response.json()
            share_data = data.get('ocs', {}).get('data', {})
            return {
                'success': True,
                'token': share_data.get('token', ''),
                'url': share_data.get('url', ''),
                'share_id': share_data.get('id'),
            }

        return {
            'success': False,
            'error': f'Failed to create share: {response.status_code} {response.text}'
        }

    def delete_share(self, share_id: int) -> Dict[str, Any]:
        """
        Delete a share by ID.

        Args:
            share_id: The share ID to delete

        Returns:
            Dict with success status
        """
        url = f"{self.base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}"

        response = requests.delete(
            url,
            headers={**self.headers, 'Accept': 'application/json'}
        )

        if response.status_code == 200:
            return {'success': True}

        return {
            'success': False,
            'error': f'Failed to delete share: {response.status_code} {response.text}'
        }

    def get_shares_for_path(self, path: str) -> Dict[str, Any]:
        """
        Get all shares for a specific path.

        Args:
            path: Folder path relative to user's root

        Returns:
            Dict with list of shares
        """
        url = f"{self.base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares"

        response = requests.get(
            url,
            headers={**self.headers, 'Accept': 'application/json'},
            params={'path': f'/{path.lstrip("/")}'}
        )

        if response.status_code == 200:
            data = response.json()
            shares = data.get('ocs', {}).get('data', [])
            return {
                'success': True,
                'shares': shares
            }

        return {
            'success': False,
            'error': f'Failed to get shares: {response.status_code}'
        }

    def file_exists(self, path: str) -> bool:
        """Check if a file or folder exists."""
        username = self._get_username()
        if not username:
            return False

        path = path.lstrip('/')
        url = f"{self.webdav_url}/{username}/{path}"

        response = requests.request(
            'PROPFIND',
            url,
            headers={**self.headers, 'Depth': '0'}
        )

        return response.status_code == 207

    def list_folder(self, path: str) -> Dict[str, Any]:
        """
        List contents of a folder.

        Args:
            path: Folder path relative to user's root

        Returns:
            Dict with list of files/folders
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        path = path.lstrip('/')
        url = f"{self.webdav_url}/{username}/{path}"

        response = requests.request(
            'PROPFIND',
            url,
            headers={**self.headers, 'Depth': '1'}
        )

        if response.status_code == 207:
            # Parse WebDAV XML response
            items = []
            try:
                root = ET.fromstring(response.content)
                ns = {'d': 'DAV:'}
                for resp in root.findall('.//d:response', ns):
                    href = resp.find('d:href', ns)
                    if href is not None:
                        item_path = href.text
                        is_collection = resp.find(
                            './/d:collection', ns) is not None
                        items.append({
                            'path': item_path,
                            'is_folder': is_collection
                        })
            except ET.ParseError:
                pass

            return {'success': True, 'items': items}

        return {
            'success': False,
            'error': f'Failed to list folder: {response.status_code}'
        }
