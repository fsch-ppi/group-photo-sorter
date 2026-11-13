"""
Nextcloud API client for folder and file operations.
"""

import hashlib
import logging
import os
import posixpath
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from django.conf import settings

from apps.core.cache_utils import (
    redis_lock,
    safe_cache_delete,
    safe_cache_get,
    safe_cache_set,
)

logger = logging.getLogger(__name__)


class NextcloudClient:
    """Client for interacting with Nextcloud WebDAV and OCS APIs."""

    # Retry configuration for rate limiting
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 2  # seconds
    MAX_BACKOFF = 60  # seconds

    # Redis cache TTLs
    USERNAME_CACHE_TTL = 3600  # 1 hour
    FOLDER_SIZE_CACHE_TTL = 60  # 1 minute

    def __init__(self, access_token: str, user_profile=None):
        """
        Initialize the Nextcloud client.

        Args:
            access_token: OAuth2 access token
            user_profile: Optional UserProfile instance for automatic token refresh
        """
        self.base_url = settings.NEXTCLOUD_URL.rstrip('/')
        self.access_token = access_token
        self.user_profile = user_profile
        self._token_refreshed = False  # Track if we've already tried refreshing
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'OCS-APIRequest': 'true',
        }
        self._cached_username: Optional[str] = None

        # Use a persistent Session for TCP/TLS connection reuse
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def _get_user_cache_id(self) -> str:
        """Return a stable identifier for caching user-scoped data in Redis."""
        if self.user_profile and getattr(self.user_profile, 'id', None):
            return f"profile_{self.user_profile.id}"
        token_hash = hashlib.sha256((self.access_token or '').encode('utf-8')).hexdigest()[:16]
        return f"token_{token_hash}"

    def _get_folder_size_cache_key(self, path: str) -> str:
        normalized = path.strip('/')
        path_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
        return f"nc_folder_size:{self._get_user_cache_id()}:{path_hash}"

    def increment_cached_folder_size(self, path: str, delta_bytes: int) -> None:
        """Increment cached folder size in Redis after an upload."""
        cache_key = self._get_folder_size_cache_key(path)
        current = safe_cache_get(cache_key)
        if isinstance(current, int):
            safe_cache_set(cache_key, max(0, current + int(delta_bytes)), timeout=self.FOLDER_SIZE_CACHE_TTL)

    def invalidate_folder_size_cache(self, path: str) -> None:
        """Invalidate cached folder size for a path."""
        safe_cache_delete(self._get_folder_size_cache_key(path))

    def _encode_webdav_path(self, path: str) -> str:
        """URL-encode each segment of a WebDAV path while preserving slashes."""
        clean = path.lstrip('/')
        return '/'.join(urllib.parse.quote(segment, safe='') for segment in clean.split('/') if segment)

    def _refresh_token(self) -> bool:
        """
        Attempt to refresh the OAuth2 access token using a distributed Redis lock
        so concurrent workers do not race on single-use refresh tokens.

        Returns:
            True if refresh succeeded, False otherwise
        """
        if not self.user_profile or not self.user_profile.nextcloud_refresh_token:
            return False

        if self._token_refreshed:
            return False

        self._token_refreshed = True
        lock_name = f"nc_token_refresh:{self.user_profile.id}"

        with redis_lock(lock_name, timeout=15, wait_timeout=10.0):
            try:
                # Reload profile from DB in case another worker just refreshed it
                self.user_profile.refresh_from_db()
                if (
                    self.user_profile.nextcloud_access_token
                    and self.user_profile.nextcloud_access_token != self.access_token
                ):
                    self.access_token = self.user_profile.nextcloud_access_token
                    self.headers['Authorization'] = f'Bearer {self.access_token}'
                    logger.info(
                        f"Adopted freshly rotated Nextcloud token for user {self.user_profile.user}"
                    )
                    return True

                url = f'{self.base_url}/index.php/apps/oauth2/api/v1/token'
                data = {
                    'grant_type': 'refresh_token',
                    'refresh_token': self.user_profile.nextcloud_refresh_token,
                    'client_id': settings.SOCIAL_AUTH_NEXTCLOUD_KEY,
                    'client_secret': settings.SOCIAL_AUTH_NEXTCLOUD_SECRET,
                }
                response = self.session.post(url, data=data, timeout=15)

                if response.status_code == 200:
                    tokens = response.json()
                    new_access_token = tokens.get('access_token')
                    new_refresh_token = tokens.get('refresh_token')

                    if new_access_token:
                        self.access_token = new_access_token
                        self.headers['Authorization'] = f'Bearer {new_access_token}'

                        self.user_profile.nextcloud_access_token = new_access_token
                        if new_refresh_token:
                            self.user_profile.nextcloud_refresh_token = new_refresh_token
                        self.user_profile.save(
                            update_fields=['nextcloud_access_token', 'nextcloud_refresh_token', 'updated_at']
                        )

                        logger.info(
                            f"Successfully refreshed Nextcloud token for user {self.user_profile.user}"
                        )
                        return True

                logger.warning(f"Failed to refresh token: {response.status_code}")
                return False

            except Exception as e:
                logger.error(f"Error refreshing Nextcloud token: {e}")
                return False

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make an HTTP request with exponential backoff retry on rate limiting
        or transient connection errors. Automatically attempts token refresh on 401.
        """
        backoff = self.INITIAL_BACKOFF
        last_response = None
        kwargs.setdefault('timeout', 60)

        for attempt in range(self.MAX_RETRIES):
            if 'headers' in kwargs and isinstance(kwargs['headers'], dict):
                kwargs['headers'] = {
                    **kwargs['headers'],
                    'Authorization': f'Bearer {self.access_token}',
                }

            try:
                response = self.session.request(method, url, **kwargs)
                last_response = response
            except requests.RequestException as exc:
                logger.warning(
                    f"Nextcloud request error ({method} {url}, attempt {attempt + 1}/{self.MAX_RETRIES}): {exc}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                    continue
                raise

            # Check for authentication failure (401) - try token refresh
            if response.status_code == 401 and not self._token_refreshed:
                if self._refresh_token():
                    continue

            # Check for rate limiting (429), WebDAV lock (423), or server overload (502, 503, 504)
            if response.status_code in [423, 429, 502, 503, 504]:
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = backoff
                else:
                    wait_time = backoff

                wait_time = min(wait_time, self.MAX_BACKOFF)

                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(wait_time)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                    continue

            return response

        return last_response

    @property
    def webdav_url(self) -> str:
        return f"{self.base_url}/remote.php/dav/files"

    def _get_username(self) -> Optional[str]:
        """Get the current user's Nextcloud username (cached in memory, DB profile, and Redis)."""
        if self._cached_username:
            return self._cached_username

        # 1. Check UserProfile field if available
        if self.user_profile and getattr(self.user_profile, 'nextcloud_user_id', ''):
            self._cached_username = self.user_profile.nextcloud_user_id
            return self._cached_username

        # 2. Check Redis cache
        cache_key = f"nc_username:{self._get_user_cache_id()}"
        cached = safe_cache_get(cache_key)
        if cached and isinstance(cached, str):
            self._cached_username = cached
            return self._cached_username

        # 3. Query Nextcloud OCS user endpoint
        url = f"{self.base_url}/ocs/v2.php/cloud/user"
        response = self._request_with_retry(
            'GET',
            url,
            headers={**self.headers, 'Accept': 'application/json'}
        )
        if response.status_code == 200:
            data = response.json()
            username = data.get('ocs', {}).get('data', {}).get('id')
            if username:
                self._cached_username = username
                safe_cache_set(cache_key, username, timeout=self.USERNAME_CACHE_TTL)
                if self.user_profile and not self.user_profile.nextcloud_user_id:
                    try:
                        self.user_profile.nextcloud_user_id = username
                        self.user_profile.save(update_fields=['nextcloud_user_id', 'updated_at'])
                    except Exception:
                        pass
                return self._cached_username
        return None

    def create_folder(self, path: str) -> Dict[str, Any]:
        """
        Create a folder in Nextcloud recursively.

        Args:
            path: Folder path relative to user's root (e.g., 'Photos/Wedding2026')

        Returns:
            Dict with success status and message
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        path = path.strip('/')
        if not path:
            return {'success': True, 'path': ''}

        parts = [p for p in path.split('/') if p]
        current_path = ''

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            encoded_path = self._encode_webdav_path(current_path)
            url = f"{self.webdav_url}/{urllib.parse.quote(username, safe='')}/{encoded_path}"

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

    def upload_file(
        self,
        remote_path: str,
        file_content: bytes,
        content_type: str = 'application/octet-stream',
        mtime: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Nextcloud.

        Args:
            remote_path: Full path including filename (e.g., 'Photos/Wedding/photo1.jpg')
            file_content: File content as bytes
            content_type: MIME type of the file
            mtime: Optional Unix timestamp for file modification time (X-OC-Mtime)

        Returns:
            Dict with success status
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        remote_path = remote_path.lstrip('/')
        encoded_path = self._encode_webdav_path(remote_path)
        url = f"{self.webdav_url}/{urllib.parse.quote(username, safe='')}/{encoded_path}"

        put_headers = {**self.headers, 'Content-Type': content_type}
        if mtime is not None:
            put_headers['X-OC-Mtime'] = str(int(mtime))

        response = self._request_with_retry(
            'PUT',
            url,
            headers=put_headers,
            data=file_content
        )

        # If parent directory is missing (404 or 409), create it and retry once
        if response.status_code in [404, 409]:
            parent_dir = posixpath.dirname(remote_path)
            if parent_dir:
                self.create_folder(parent_dir)
                response = self._request_with_retry(
                    'PUT',
                    url,
                    headers=put_headers,
                    data=file_content
                )

        if response.status_code in [200, 201, 204]:
            parent_dir = posixpath.dirname(remote_path)
            if parent_dir:
                self.increment_cached_folder_size(parent_dir, len(file_content))
            return {'success': True, 'path': remote_path}

        return {
            'success': False,
            'error': f'Failed to upload file: {response.status_code} {response.text}'
        }

    def upload_file_streaming(
        self,
        remote_path: str,
        file_path: str,
        content_type: str = 'application/octet-stream',
        chunk_size: int = 8 * 1024 * 1024,
        mtime: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Nextcloud by streaming from disk (memory-efficient).
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        remote_path = remote_path.lstrip('/')
        encoded_path = self._encode_webdav_path(remote_path)
        url = f"{self.webdav_url}/{urllib.parse.quote(username, safe='')}/{encoded_path}"

        file_size = os.path.getsize(file_path)

        put_headers = {
            **self.headers,
            'Content-Type': content_type,
            'Content-Length': str(file_size),
        }
        if mtime is not None:
            put_headers['X-OC-Mtime'] = str(int(mtime))

        def _do_stream_put() -> requests.Response:
            with open(file_path, 'rb') as f:
                return self._request_with_retry(
                    'PUT',
                    url,
                    headers=put_headers,
                    data=f,
                    timeout=600,
                )

        response = _do_stream_put()

        if response.status_code in [404, 409]:
            parent_dir = posixpath.dirname(remote_path)
            if parent_dir:
                self.create_folder(parent_dir)
                response = _do_stream_put()

        if response.status_code in [200, 201, 204]:
            parent_dir = posixpath.dirname(remote_path)
            if parent_dir:
                self.increment_cached_folder_size(parent_dir, file_size)
            return {'success': True, 'path': remote_path}

        return {
            'success': False,
            'error': f'Failed to upload file: {response.status_code} {response.text}'
        }

    def bulk_upload(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upload multiple files in a single bulk request to Nextcloud.
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        if not files:
            return {'success': True, 'results': {}}

        boundary = f"boundary_{uuid.uuid4().hex}"
        body_parts = []

        for file_info in files:
            remote_path = file_info['remote_path'].lstrip('/')
            content = file_info['content']
            mtime = file_info.get('mtime', int(time.time()))
            md5_hash = hashlib.md5(content).hexdigest()

            part_headers = [
                f"--{boundary}\r\n",
                f"X-File-Path: /{remote_path}\r\n",
                f"X-OC-Mtime: {mtime}\r\n",
                f"X-File-Md5: {md5_hash}\r\n",
                f"Content-Length: {len(content)}\r\n",
                "\r\n",
            ]

            body_parts.append("".join(part_headers).encode('utf-8'))
            body_parts.append(content)
            body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}--\r\n".encode('utf-8'))
        body = b"".join(body_parts)

        url = f"{self.base_url}/remote.php/dav/bulk"
        logger.info(f"Attempting bulk upload to {url} with {len(files)} files")

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
                if not isinstance(results, dict):
                    return {
                        'success': False,
                        'error': 'Unexpected non-dict JSON response from bulk upload'
                    }
                all_success = all(
                    isinstance(r, dict) and not r.get('error', False)
                    for r in results.values()
                )
                return {
                    'success': all_success,
                    'results': results,
                    'uploaded_count': len([
                        r for r in results.values()
                        if isinstance(r, dict) and not r.get('error')
                    ])
                }
            except Exception as e:
                logger.warning(f"Failed to parse bulk upload JSON response: {e}")
                return {
                    'success': False,
                    'error': f'Invalid JSON response from bulk upload: {e}'
                }

        logger.warning(f"Bulk upload failed: {response.status_code} - {response.text[:500]}")
        return {
            'success': False,
            'error': f'Bulk upload failed: {response.status_code} {response.text}'
        }

    def create_public_share(self, path: str, permissions: int = 1) -> Dict[str, Any]:
        """
        Create a public share link for a folder.
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
        """Delete a share by ID."""
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
        """Get all shares for a specific path."""
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

        encoded_path = self._encode_webdav_path(path)
        url = f"{self.webdav_url}/{urllib.parse.quote(username, safe='')}/{encoded_path}"

        response = self._request_with_retry(
            'PROPFIND',
            url,
            headers={**self.headers, 'Depth': '0'}
        )

        return response.status_code == 207

    def list_folder(self, path: str) -> Dict[str, Any]:
        """
        List contents of a folder.

        Returns:
            Dict with list of items ({'path', 'name', 'is_folder'})
        """
        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        encoded_path = self._encode_webdav_path(path)
        url = f"{self.webdav_url}/{urllib.parse.quote(username, safe='')}/{encoded_path}"

        response = self._request_with_retry(
            'PROPFIND',
            url,
            headers={**self.headers, 'Depth': '1'}
        )

        if response.status_code == 207:
            items = []
            try:
                root = ET.fromstring(response.content)
                ns = {'d': 'DAV:'}
                for idx, resp in enumerate(root.findall('.//d:response', ns)):
                    href = resp.find('d:href', ns)
                    if href is not None and href.text:
                        item_path = urllib.parse.unquote(href.text)
                        is_collection = resp.find('.//d:collection', ns) is not None
                        name = posixpath.basename(item_path.rstrip('/'))
                        # Skip the first response entry if it represents the folder itself
                        if idx == 0 and is_collection:
                            continue
                        items.append({
                            'path': item_path,
                            'name': name,
                            'is_folder': is_collection
                        })
            except ET.ParseError:
                return {'success': False, 'error': 'Failed to parse WebDAV response'}

            return {'success': True, 'items': items}

        if response.status_code == 404:
            return {'success': True, 'items': []}

        return {
            'success': False,
            'error': f'Failed to list folder: {response.status_code}'
        }

    def get_folder_size(self, path: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get the total size of a folder and its contents.

        Uses Redis caching (TTL 60s) and a lightweight WebDAV PROPFIND Depth: 0
        request reading Nextcloud's `<oc:size/>` property to avoid expensive
        `Depth: infinity` queries and double-counting bugs.
        """
        cache_key = self._get_folder_size_cache_key(path)
        if use_cache:
            cached_bytes = safe_cache_get(cache_key)
            if isinstance(cached_bytes, int):
                return {'success': True, 'total_bytes': cached_bytes, 'cached': True}

        username = self._get_username()
        if not username:
            return {'success': False, 'error': 'Could not determine username'}

        encoded_path = self._encode_webdav_path(path)
        url = f"{self.webdav_url}/{urllib.parse.quote(username, safe='')}/{encoded_path}"

        propfind_body = '''<?xml version="1.0" encoding="UTF-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:prop>
                <d:getcontentlength/>
                <oc:size/>
            </d:prop>
        </d:propfind>'''

        # First query Depth: 0 to read Nextcloud's precomputed <oc:size> on the folder
        response = self._request_with_retry(
            'PROPFIND',
            url,
            headers={
                **self.headers,
                'Depth': '0',
                'Content-Type': 'application/xml',
            },
            data=propfind_body
        )

        if response.status_code == 207:
            try:
                root = ET.fromstring(response.content)
                ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
                size_elem = root.find('.//oc:size', ns)
                if size_elem is not None and size_elem.text:
                    total_bytes = int(size_elem.text)
                    safe_cache_set(cache_key, total_bytes, timeout=self.FOLDER_SIZE_CACHE_TTL)
                    return {'success': True, 'total_bytes': total_bytes}
            except (ET.ParseError, ValueError):
                pass

        if response.status_code == 404:
            safe_cache_set(cache_key, 0, timeout=self.FOLDER_SIZE_CACHE_TTL)
            return {'success': True, 'total_bytes': 0}

        # Fallback: Depth: 1 summing only non-collection file content lengths
        response = self._request_with_retry(
            'PROPFIND',
            url,
            headers={
                **self.headers,
                'Depth': '1',
                'Content-Type': 'application/xml',
            },
            data=propfind_body
        )

        if response.status_code == 207:
            total_bytes = 0
            try:
                root = ET.fromstring(response.content)
                ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
                for resp in root.findall('.//d:response', ns):
                    if resp.find('.//d:collection', ns) is not None:
                        continue
                    length_elem = resp.find('.//d:getcontentlength', ns)
                    if length_elem is not None and length_elem.text:
                        try:
                            total_bytes += int(length_elem.text)
                        except ValueError:
                            pass
            except ET.ParseError:
                return {'success': False, 'error': 'Failed to parse folder size response'}

            safe_cache_set(cache_key, total_bytes, timeout=self.FOLDER_SIZE_CACHE_TTL)
            return {'success': True, 'total_bytes': total_bytes}

        return {
            'success': False,
            'error': f'Failed to get folder size: {response.status_code}'
        }
