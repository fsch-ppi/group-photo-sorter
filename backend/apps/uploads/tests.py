"""
Unit tests for Redis caching, distributed locking, Nextcloud client,
file conversion (EXIF, RGBA orientation, ffprobe timestamps, unique filenames),
and upload/batch Celery tasks.
"""
import io
import json
import os
import tempfile
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from PIL import Image

from apps.core.cache_utils import (
    append_to_cached_list,
    redis_lock,
    safe_cache_delete,
    safe_cache_get,
    safe_cache_set,
    update_cached_list,
)
from apps.core.models import UserProfile
from apps.folders.models import PhotoFolder
from apps.folders.nextcloud_client import NextcloudClient
from apps.uploads.converters import (
    convert_image_to_jpeg,
    get_exif_date,
    get_unique_filename,
    get_video_creation_date,
)
from apps.uploads.tasks import flush_image_batch, process_image_for_batch

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "photo-sorter-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class CacheUtilsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_safe_cache_roundtrip(self):
        self.assertTrue(safe_cache_set("test_key", {"a": 1}, timeout=60))
        self.assertEqual(safe_cache_get("test_key"), {"a": 1})
        self.assertTrue(safe_cache_delete("test_key"))
        self.assertIsNone(safe_cache_get("test_key"))

    def test_redis_lock_acquires_and_releases(self):
        with redis_lock("unit_lock", timeout=10) as acquired:
            self.assertTrue(acquired)
            # While held, a non-blocking attempt should fail
            with redis_lock("unit_lock", timeout=10, wait_timeout=0) as second:
                self.assertFalse(second)

        # After exit, lock is released
        with redis_lock("unit_lock", timeout=10, wait_timeout=0) as acquired_again:
            self.assertTrue(acquired_again)

    def test_append_and_update_cached_list(self):
        append_to_cached_list("batch_list", {"id": 1}, timeout=60)
        append_to_cached_list("batch_list", {"id": 2}, timeout=60)
        self.assertEqual(safe_cache_get("batch_list"), [{"id": 1}, {"id": 2}])

        updated = update_cached_list(
            "batch_list",
            lambda items: [i for i in items if i["id"] != 1],
            timeout=60,
        )
        self.assertEqual(updated, [{"id": 2}])
        self.assertEqual(safe_cache_get("batch_list"), [{"id": 2}])


@override_settings(CACHES=LOCMEM_CACHE)
class ConvertersTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_get_exif_date_reads_datetime_original(self):
        img = Image.new("RGB", (32, 24), color=(100, 150, 200))
        exif = img.getexif()
        # 36867 = DateTimeOriginal
        exif[36867] = "2026:07:19 15:42:10"
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif.tobytes())
        buf.seek(0)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(buf.read())
            tmp_path = tmp.name

        try:
            with Image.open(tmp_path) as opened_img:
                dt = get_exif_date(opened_img)
            self.assertEqual(dt, datetime(2026, 7, 19, 15, 42, 10))
        finally:
            os.unlink(tmp_path)

    def test_convert_image_to_jpeg_preserves_rgba_orientation(self):
        # Create a 40x20 RGBA image with EXIF Orientation = 6 (Rotate 90 CW -> 20x40)
        img = Image.new("RGBA", (40, 20), color=(255, 0, 0, 128))
        exif = img.getexif()
        exif[274] = 6  # Orientation = Rotate 90 CW

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as src_tmp:
            img.save(src_tmp.name, format="PNG", exif=exif.tobytes())
            src_path = src_tmp.name

        try:
            jpeg_bytes, metadata = convert_image_to_jpeg(src_path, quality=90)
            with Image.open(io.BytesIO(jpeg_bytes)) as out_img:
                self.assertEqual(out_img.mode, "RGB")
                # Width and height should be transposed from (40, 20) to (20, 40)
                self.assertEqual(out_img.size, (20, 40))
                self.assertEqual((metadata["width"], metadata["height"]), (20, 40))
        finally:
            if os.path.exists(src_path):
                os.unlink(src_path)

    @patch("apps.uploads.converters.subprocess.run")
    def test_get_video_creation_date_parses_27_char_ffprobe_iso_timestamp(self, mock_run):
        # 27-character ISO string that previously failed due to date_str[:26] slicing off 'Z'
        ffprobe_output = {
            "format": {
                "tags": {
                    "creation_time": "2026-01-12T14:30:52.000000Z"
                }
            },
            "streams": [],
        }
        mock_run.return_value = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(ffprobe_output),
        )

        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
            dt = get_video_creation_date(tmp.name)

        self.assertEqual(dt, datetime(2026, 1, 12, 14, 30, 52))

    def test_get_unique_filename_uses_redis_set_and_avoids_collisions(self):
        client = MagicMock()
        client.list_folder.return_value = {
            "success": True,
            "items": [
                {"name": "2026-05-01_120000_wedding.jpg", "is_dir": False},
            ],
        }
        folder = SimpleNamespace(id=42, nextcloud_folder_path="/Photos/Event")

        first = get_unique_filename(folder, "2026-05-01_120000_wedding.jpg", client)
        second = get_unique_filename(folder, "2026-05-01_120000_wedding.jpg", client)

        self.assertEqual(first, "2026-05-01_120000_wedding_1.jpg")
        self.assertEqual(second, "2026-05-01_120000_wedding_2.jpg")
        # list_folder should only be called once to seed the Redis cache
        self.assertEqual(client.list_folder.call_count, 1)


@override_settings(CACHES=LOCMEM_CACHE)
class NextcloudClientTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="ncuser", password="secret")
        self.profile = UserProfile.objects.create(
            user=self.user,
            nextcloud_user_id="alice",
            nextcloud_access_token="initial_access",
            nextcloud_refresh_token="initial_refresh",
        )

    @patch.object(NextcloudClient, "_request_with_retry")
    def test_get_folder_size_does_not_double_count_and_caches(self, mock_req):
        xml_response = """<?xml version="1.0"?>
        <d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:response>
                <d:href>/remote.php/dav/files/alice/Photos/</d:href>
                <d:propstat>
                    <d:prop>
                        <oc:size>123456</oc:size>
                        <d:getcontentlength>123456</d:getcontentlength>
                    </d:prop>
                </d:propstat>
            </d:response>
        </d:multistatus>"""
        mock_req.return_value = SimpleNamespace(
            status_code=207,
            text=xml_response,
            content=xml_response.encode("utf-8"),
        )

        client = NextcloudClient("initial_access", user_profile=self.profile)
        size1 = client.get_folder_size("/Photos")
        size2 = client.get_folder_size("/Photos")

        self.assertEqual(size1, {"success": True, "total_bytes": 123456})
        self.assertEqual(size2, {"success": True, "total_bytes": 123456, "cached": True})
        self.assertEqual(mock_req.call_count, 1)

        # Increment cached size
        client.increment_cached_folder_size("/Photos", 1000)
        self.assertEqual(
            client.get_folder_size("/Photos"),
            {"success": True, "total_bytes": 124456, "cached": True},
        )
        self.assertEqual(mock_req.call_count, 1)


@override_settings(CACHES=LOCMEM_CACHE)
class BatchUploadTasksTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="owner", password="secret")
        self.profile = UserProfile.objects.create(
            user=self.user,
            nextcloud_user_id="owner_nc",
            nextcloud_access_token="token",
            nextcloud_refresh_token="refresh",
        )
        self.folder = PhotoFolder.objects.create(
            owner=self.user,
            name="Wedding",
            event_name="wedding",
            nextcloud_folder_path="/Photos/Wedding",
        )

    @patch("apps.uploads.tasks.flush_image_batch.apply_async")
    @patch("apps.uploads.tasks.NextcloudClient")
    def test_batch_upload_preserves_queue_on_failure_and_cleans_up_on_success(
        self, mock_nc_cls, mock_apply_async
    ):
        mock_nc = MagicMock()
        mock_nc.list_folder.return_value = {"success": True, "items": []}
        mock_nc_cls.return_value = mock_nc

        img = Image.new("RGB", (16, 16), color=(10, 20, 30))
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            img.save(tmp.name, format="JPEG")
            tmp_path = tmp.name

        # 1. Process image into batch (threshold is 50 so it won't auto-flush immediately)
        res = process_image_for_batch.run(
            self.folder.id, tmp_path, "photo.jpg", "127.0.0.1"
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["queued_for_batch"])

        batch_key = f"image_batch:{self.folder.id}"
        queued = safe_cache_get(batch_key)
        self.assertEqual(len(queued), 1)

        # 2. Simulate both bulk_upload and individual fallback failing -> batch must stay in Redis
        mock_nc.bulk_upload.return_value = {"success": False, "error": "503 Unavailable"}
        mock_nc.upload_file.return_value = {"success": False, "error": "503 Unavailable"}
        with self.assertRaises(Exception):
            flush_image_batch.run(self.folder.id)

        self.assertEqual(len(safe_cache_get(batch_key, [])), 1)

        # 3. Simulate bulk_upload success -> batch cleared from Redis
        mock_nc.bulk_upload.return_value = {"success": True, "uploaded": 1}
        flush_res = flush_image_batch.run(self.folder.id)
        self.assertTrue(flush_res["success"])
        self.assertEqual(flush_res["uploaded"], 1)
        self.assertEqual(safe_cache_get(batch_key, []), [])
