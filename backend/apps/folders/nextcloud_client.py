"""
Nextcloud API client for folder and file operations.
"""

import hashlib
import time
import uuid
import requests
from django.conf import settings
from typing import Optional, Dict, Any, List
import xml.etree.ElementTree as ET


class NextcloudClient:
    """Client for interacting with Nextcloud WebDAV and OCS APIs."""

    # Retry configuration for rate limiting
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 2  # seconds
    MAX_BACKOFF = 60  # seconds

    def __init__(self, access_token: str):
        self.base_url = settings.NEXTCLOUD_URL.rstrip('/')
        self.access_token = access_token
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'OCS-APIRequest': 'true',
        }
        self._cached_username = None  # Cache username to reduce API calls

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make an HTTP request with exponential backoff retry on rate limiting.

        Args:
            method: HTTP method (GET, PUT, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object

        Raises:
            requests.RequestException on non-retryable errors after max retries
        """
        backoff = self.INITIAL_BACKOFF
        last_response = None

        for attempt in range(self.MAX_RETRIES):
            response = requests.request(method, url, **kwargs)
            last_response = response

            # Check for rate limiting (429) or server overload (503)
            if response.status_code in [429, 503]:
                # Check for Retry-After header
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = backoff
                else:
                    wait_time = backoff

                # Cap the wait time
                wait_time = min(wait_time, self.MAX_BACKOFF)

                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(wait_time)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                    continue

            # For all other status codes, return immediately
            return response

        # Return the last response if all retries exhausted
        return last_response

    @property
    def webdav_url(self) -> str:
        return f"{self.base_url}/remote.php/dav/files"

    def _get_username(self) -> Optional[str]:
        """Get the current user's username (cached to reduce API calls)."""
        if self._cached_username:
            return self._cached_username

        url = f"{self.base_url}/ocs/v2.php/cloud/user"
        response = self._request_with_retry(
            'GET',
            url,
            headers={**self.headers, 'Accept': 'application/json'}
        )
        if response.status_code == 200:
            data = response.json()
            self._cached_username = data.get(
                'ocs', {}).get('data', {}).get('id')
            return self._cached_username
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

            response = self._request_with_retry(
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

        response = self._request_with_retry(
            'PUT',
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

    def bulk_upload(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upload multiple files in a single bulk request to Nextcloud.

        This uses the Nextcloud bulk upload API at /remote.php/dav/bulk
        to upload many files in one HTTP request, avoiding rate limits.

        Args:
            files: List of dicts, each containing:
                - remote_path: Full path including filename
                - content: File content as bytes
                - content_type: MIME type (e.g., 'image/jpeg')
                - mtime: Optional modification time (unix timestamp)

        Returns:
            Dict with success status and results per file
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        if not files:
            return {'success': True, 'results': {}}

        # Generate a unique boundary for multipart
        boundary = f"bulk_upload_{uuid.uuid4().hex}"

        # Build multipart body
        body_parts = []

        for file_info in files:
            remote_path = file_info['remote_path'].lstrip('/')
            content = file_info['content']
            content_type = file_info.get(
                'content_type', 'application/octet-stream')
            mtime = file_info.get('mtime', int(time.time()))

            # Calculate MD5 checksum
            md5_hash = hashlib.md5(content).hexdigest()

            # Build headers for this part
            part_headers = [
                f"--{boundary}",
                f"X-File-Path: /{username}/{remote_path}",
                f"X-OC-Mtime: {mtime}",
                f"X-File-Md5: {md5_hash}",
                f"Content-Length: {len(content)}",
                f"Content-Type: {content_type}",
                "",  # Empty line before content
            ]

            body_parts.append("\r\n".join(part_headers).encode('utf-8'))
            body_parts.append(content)
            body_parts.append(b"\r\n")

        # Add closing boundary
        body_parts.append(f"--{boundary}--\r\n".encode('utf-8'))

        # Combine all parts
        body = b"".join(body_parts)

        # Make the bulk upload request
        url = f"{self.base_url}/remote.php/dav/bulk"

        response = self._request_with_retry(
            'POST',
            url,
            headers={
                **self.headers,
                'Content-Type': f'multipart/related; boundary={boundary}',
            },
            data=body
        )

        if response.status_code == 200:
            try:
                results = response.json()
                # Check if all files succeeded
                all_success = all(
                    not r.get('error', False)
                    for r in results.values()
                )
                return {
                    'success': all_success,
                    'results': results,
                    'uploaded_count': len([r for r in results.values() if not r.get('error')])
                }
            except Exception as e:
                return {
                    'success': True,
                    'results': {},
                    'uploaded_count': len(files)
                }

        return {
            'success': False,
            'error': f'Bulk upload failed: {response.status_code} {response.text}'
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

        response = self._request_with_retry(
            'POST',
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

        response = self._request_with_retry(
            'DELETE',
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

        response = self._request_with_retry(
            'GET',
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

        response = self._request_with_retry(
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

        response = self._request_with_retry(
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

    def get_folder_size(self, path: str) -> Dict[str, Any]:
        """
        Get the total size of a folder and its contents.

        Uses WebDAV PROPFIND with Depth: infinity to get all file sizes.

        Args:
            path: Folder path relative to user's root

        Returns:
            Dict with success status and total_bytes
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        path = path.lstrip('/')
        url = f"{self.webdav_url}/{username}/{path}"

        # Request with Depth: infinity to get all nested files
        # Note: Some servers may limit depth, but Nextcloud supports it
        propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:prop>
                <d:getcontentlength/>
                <oc:size/>
            </d:prop>
        </d:propfind>'''

        response = self._request_with_retry(
            'PROPFIND',
            url,
            headers={**self.headers, 'Depth': 'infinity',
                     'Content-Type': 'application/xml'},
            data=propfind_body
        )

        if response.status_code == 207:
            total_bytes = 0
            try:
                root = ET.fromstring(response.content)
                ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
                for resp in root.findall('.//d:response', ns):
                    # Check for oc:size first (folder size from Nextcloud)
                    size_elem = resp.find('.//oc:size', ns)
                    if size_elem is not None and size_elem.text:
                        try:
                            total_bytes = max(total_bytes, int(size_elem.text))
                        except ValueError:
                            pass
                    # Then check for file size
                    length_elem = resp.find('.//d:getcontentlength', ns)
                    if length_elem is not None and length_elem.text:
                        try:
                            total_bytes += int(length_elem.text)
                        except ValueError:
                            pass
            except ET.ParseError:
                return {'success': False, 'error': 'Failed to parse folder size response'}

            return {'success': True, 'total_bytes': total_bytes}

        if response.status_code == 404:
            # Folder doesn't exist yet, size is 0
            return {'success': True, 'total_bytes': 0}

        return {
            'success': False,
            'error': f'Failed to get folder size: {response.status_code}'
        }
