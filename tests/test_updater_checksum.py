"""Checksum behaviour of the in-app updater. No network, no GUI."""

import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock

import updater
from updater import (
    DownloadResult,
    ReleaseInfo,
    Sha256MismatchError,
    download_release_exe,
    fetch_latest_release,
    file_sha256,
    format_sha256_preview,
    is_sha256_hex,
    local_frozen_exe_sha256,
    make_sha256_verification,
    update_prompt_mode,
    verification_before_download,
)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXE_URL = (
    "https://github.com/nico2511/CyberScribe/releases/download/v9.9.9/CyberScribe.exe"
)
SHA_URL = EXE_URL + ".sha256"


def _digest_for(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _release(**overrides) -> ReleaseInfo:
    data = dict(
        version="9.9.9",
        tag="v9.9.9",
        exe_url=EXE_URL,
        exe_size=None,
        sha256_url=None,
        release_page="https://github.com/nico2511/CyberScribe/releases/tag/v9.9.9",
        notes="",
        expected_sha256=None,
    )
    data.update(overrides)
    return ReleaseInfo(**data)


class ChecksumHelpersTest(unittest.TestCase):
    def test_preview_is_truncated_and_distinct_from_full_hash(self):
        digest = "ab" * 32
        preview = format_sha256_preview(digest)
        self.assertNotEqual(preview, digest)
        self.assertTrue(preview.startswith(digest[:16]))
        self.assertTrue(preview.endswith(digest[-8:]))
        self.assertIn("…", preview)

    def test_is_sha256_hex(self):
        self.assertTrue(is_sha256_hex("AB" * 32))
        self.assertFalse(is_sha256_hex(("ab" * 32) + "  CyberScribe.exe"))
        self.assertFalse(is_sha256_hex("zz" * 32))
        self.assertFalse(is_sha256_hex(""))

    def test_status_and_prompt_mode(self):
        pending = make_sha256_verification(
            sidecar_present=True, expected="ab" * 32, actual=None
        )
        self.assertEqual(pending.status, "pending")
        self.assertEqual(update_prompt_mode(pending.status), "confirm")

        missing = make_sha256_verification(
            sidecar_present=False, expected="ab" * 32, actual="cd" * 32
        )
        self.assertIsNone(missing.expected)
        self.assertEqual(missing.actual, "cd" * 32)
        self.assertEqual(missing.status, "sidecar_missing")
        self.assertFalse(missing.verified)
        self.assertEqual(update_prompt_mode(missing.status), "warn")

        unread = make_sha256_verification(
            sidecar_present=True, expected="nope", actual="cd" * 32
        )
        self.assertEqual(unread.status, "sidecar_unreadable")
        self.assertEqual(update_prompt_mode(unread.status), "warn")

        match = make_sha256_verification(
            sidecar_present=True, expected="AB" * 32, actual="ab" * 32
        )
        self.assertTrue(match.verified)
        self.assertEqual(match.status, "verified")
        self.assertEqual(match.expected, "ab" * 32)
        self.assertEqual(update_prompt_mode(match.status), "confirm")

        mismatch = make_sha256_verification(
            sidecar_present=True, expected="ab" * 32, actual="cd" * 32
        )
        self.assertEqual(mismatch.status, "mismatch")
        self.assertFalse(mismatch.verified)
        self.assertEqual(update_prompt_mode(mismatch.status), "block")

    def test_local_exe_hash_only_when_frozen(self):
        self.assertIsNone(local_frozen_exe_sha256())
        payload = b"frozen-exe"
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(payload)
            path = handle.name
        try:
            with mock.patch.object(updater.sys, "frozen", True, create=True), mock.patch.object(
                updater.sys, "executable", path
            ):
                self.assertEqual(local_frozen_exe_sha256(), file_sha256(path))
        finally:
            os.remove(path)


class FetchSidecarTest(unittest.TestCase):
    def test_bare_and_filename_forms(self):
        digest = "ab" * 32
        with mock.patch.object(updater, "_api_request", return_value=digest.upper().encode()):
            self.assertEqual(updater._fetch_expected_sha256(SHA_URL, "1.5.0"), digest)
        styled = f"{digest}  CyberScribe.exe\n".encode()
        with mock.patch.object(updater, "_api_request", return_value=styled):
            self.assertEqual(updater._fetch_expected_sha256(SHA_URL, "1.5.0"), digest)

    def test_invalid_sidecar_is_none(self):
        with mock.patch.object(updater, "_api_request", return_value=b"not-a-hash"):
            self.assertIsNone(updater._fetch_expected_sha256(SHA_URL, "1.5.0"))

    def test_refuses_non_release_url(self):
        with mock.patch.object(updater, "_api_request") as api:
            with self.assertRaises(ValueError):
                updater._fetch_expected_sha256("https://example.invalid/CyberScribe.exe.sha256", "1.5.0")
            api.assert_not_called()

    def test_latest_release_exposes_expected_hash(self):
        digest = "cd" * 32
        payload = {
            "tag_name": "v9.9.9",
            "html_url": "https://github.com/nico2511/CyberScribe/releases/tag/v9.9.9",
            "body": "notes",
            "assets": [
                {
                    "name": "CyberScribe.exe",
                    "browser_download_url": EXE_URL,
                    "size": 12,
                },
                {
                    "name": "CyberScribe.exe.sha256",
                    "browser_download_url": SHA_URL,
                },
            ],
        }

        def fake_api(url, app_version, timeout=20.0):
            if url.endswith(".sha256"):
                return digest.encode()
            return json.dumps(payload).encode()

        with mock.patch.object(updater, "_api_request", side_effect=fake_api):
            info = fetch_latest_release("1.5.0")
        self.assertEqual(info.expected_sha256, digest)
        preview = verification_before_download(info)
        self.assertEqual(preview.status, "pending")
        self.assertEqual(preview.expected, digest)
        self.assertIsNone(preview.actual)
        self.assertFalse(preview.verified)

    def test_missing_sidecar_warns_before_download(self):
        payload = {
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/nico2511/CyberScribe/releases/tag/v1.2.0",
            "body": "",
            "assets": [
                {
                    "name": "CyberScribe.exe",
                    "browser_download_url": EXE_URL.replace("v9.9.9", "v1.2.0"),
                    "size": 12,
                }
            ],
        }
        with mock.patch.object(updater, "_api_request", return_value=json.dumps(payload).encode()):
            info = fetch_latest_release("1.0.0")
        preview = verification_before_download(info)
        self.assertEqual(preview.status, "sidecar_missing")
        self.assertEqual(update_prompt_mode(preview.status), "warn")
        self.assertIsNone(info.expected_sha256)
        self.assertIsNone(info.sha256_url)


class DownloadVerificationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.app_dir = self._tmp.name
        self.payload = b"cyberscribe-bytes"
        self.digest = _digest_for(self.payload)
        self._floor = updater.MIN_EXE_BYTES
        updater.MIN_EXE_BYTES = 1

    def tearDown(self):
        updater.MIN_EXE_BYTES = self._floor
        self._tmp.cleanup()

    def _write_download(self, url, dest_path, app_version, progress=None, timeout=300.0):
        self.assertEqual(url, EXE_URL)
        with open(dest_path, "wb") as handle:
            handle.write(self.payload)

    def test_verified_download_returns_details(self):
        release = _release(sha256_url=SHA_URL, expected_sha256="ff" * 32)
        with mock.patch.object(updater, "_download_file", side_effect=self._write_download), mock.patch.object(
            updater, "_fetch_expected_sha256", return_value=self.digest
        ) as fetch:
            result = download_release_exe(release, self.app_dir, "1.5.0")
        self.assertIsInstance(result, DownloadResult)
        self.assertTrue(os.path.isfile(result.path))
        self.assertTrue(result.path.endswith("CyberScribe.update.exe"))
        self.assertTrue(result.verification.verified)
        self.assertEqual(result.verification.status, "verified")
        self.assertEqual(result.verification.expected, self.digest)
        self.assertEqual(result.verification.actual, self.digest)
        self.assertTrue(result.verification.sidecar_present)
        fetch.assert_called_once_with(SHA_URL, "1.5.0")

    def test_missing_sidecar_keeps_file_and_actual_hash(self):
        release = _release(sha256_url=None)
        with mock.patch.object(updater, "_download_file", side_effect=self._write_download), mock.patch.object(
            updater, "_fetch_expected_sha256"
        ) as fetch:
            result = download_release_exe(release, self.app_dir, "1.5.0")
        fetch.assert_not_called()
        self.assertTrue(os.path.isfile(result.path))
        self.assertEqual(result.verification.status, "sidecar_missing")
        self.assertFalse(result.verification.verified)
        self.assertEqual(result.verification.actual, self.digest)
        self.assertIsNone(result.verification.expected)
        self.assertEqual(update_prompt_mode(result.verification.status), "warn")

    def test_unreadable_sidecar_does_not_block(self):
        release = _release(sha256_url=SHA_URL)
        with mock.patch.object(updater, "_download_file", side_effect=self._write_download), mock.patch.object(
            updater, "_fetch_expected_sha256", return_value=None
        ):
            result = download_release_exe(release, self.app_dir, "1.5.0")
        self.assertEqual(result.verification.status, "sidecar_unreadable")
        self.assertFalse(result.verification.verified)
        self.assertEqual(result.verification.actual, self.digest)
        self.assertTrue(os.path.isfile(result.path))

    def test_mismatch_discards_download(self):
        release = _release(sha256_url=SHA_URL)
        with mock.patch.object(updater, "_download_file", side_effect=self._write_download), mock.patch.object(
            updater, "_fetch_expected_sha256", return_value="ab" * 32
        ):
            with self.assertRaises(Sha256MismatchError) as caught:
                download_release_exe(release, self.app_dir, "1.5.0")
        verification = caught.exception.verification
        self.assertEqual(verification.status, "mismatch")
        self.assertEqual(verification.expected, "ab" * 32)
        self.assertEqual(verification.actual, self.digest)
        self.assertFalse(os.path.exists(os.path.join(self.app_dir, "CyberScribe.update.exe")))
        self.assertFalse(any(name.startswith("cyberscribe_dl_") for name in os.listdir(self.app_dir)))

    def test_rejects_url_outside_this_repo(self):
        release = _release(exe_url="https://github.com/other/repo/releases/download/v1/CyberScribe.exe")
        with mock.patch.object(updater, "_download_file") as download:
            with self.assertRaises(ValueError):
                download_release_exe(release, self.app_dir, "1.5.0")
            download.assert_not_called()

    def test_too_small_file_aborts(self):
        updater.MIN_EXE_BYTES = 100

        def write_short(url, dest_path, app_version, progress=None, timeout=300.0):
            with open(dest_path, "wb") as handle:
                handle.write(b"tiny")

        release = _release()
        with mock.patch.object(updater, "_download_file", side_effect=write_short):
            with self.assertRaises(ValueError):
                download_release_exe(release, self.app_dir, "1.5.0")
        self.assertFalse(os.path.exists(os.path.join(self.app_dir, "CyberScribe.update.exe")))


class ProductPinTest(unittest.TestCase):
    def test_version_is_1_5_0_and_ui_mentions_checksum(self):
        app = os.path.join(ROOT, "CyberScribe.py")
        with open(app, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('__version__ = "1.5.0"', source)
        self.assertNotIn('__version__ = "1.4.0"', source)
        self.assertIn("Somme SHA256 vérifiée", source)
        self.assertIn("Continuer quand même", source)
        self.assertIn("Installer quand même", source)
        self.assertIn("Mise à jour refusée : somme SHA256 incorrecte.", source)
        self.assertIn("Aucun texte dicté n'est envoyé.", source)
        self.assertNotIn("clipboard history", source.lower())
        self.assertNotIn("transcript store", source.lower())


if __name__ == "__main__":
    unittest.main()
