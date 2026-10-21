#!/usr/bin/env python3
"""Startup update-status UI tests (#42)."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from openlens.gui.dialogs.startup import StartupDialog
    from openlens.gui.storage import LensStorage
    from openlens.updater import (
        RELEASES_PAGE_URL,
        STATUS_ERROR,
        STATUS_NO_ASSET,
        STATUS_UP_TO_DATE,
        STATUS_UPDATE_AVAILABLE,
        InstallPlan,
        ReleaseAsset,
        UpdateCheckResult,
    )

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = None
except ImportError as _e:
    QTest = None  # type: ignore
    QApplication = None  # type: ignore
    StartupDialog = None  # type: ignore
    LensStorage = None  # type: ignore
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e


RELEASE_URL = "https://example.test/releases/tag/openlens-v0.8.0"


class FakeChecker:
    """Return one canned update result and record downloads."""

    def __init__(self, result):
        self.result = result
        self.current_version = result.current_version
        self.releases_page = RELEASES_PAGE_URL
        self.downloads = []

    def check(self):
        return self.result

    def download(self, result):
        self.downloads.append(result)
        path = Path(tempfile.mkdtemp(prefix="openlens-test-download-")) / "OpenLens"
        path.write_bytes(b"new build")
        return path


class FakeInstaller:
    """Record install plans without launching anything."""

    def __init__(self, can_self_update=True, system="linux"):
        self._can_self_update = can_self_update
        self.system = system
        self.prepared = []
        self.launched = []

    def can_self_update(self):
        return self._can_self_update

    def prepare(self, downloaded, result):
        self.prepared.append((Path(downloaded), result))
        return InstallPlan(
            kind="replace", target=Path("/opt/OpenLens"), script=Path("/tmp/x.sh")
        )

    def launch(self, plan):
        self.launched.append(plan)


def update_result(status=STATUS_UPDATE_AVAILABLE, with_asset=True):
    return UpdateCheckResult(
        status=status,
        current_version="0.7.0",
        latest_version="0.8.0",
        release_url=RELEASE_URL,
        asset=(
            ReleaseAsset(
                "OpenLens-0.8.0-Linux",
                "https://example.test/OpenLens-0.8.0-Linux",
                9,
            )
            if with_asset
            else None
        ),
    )


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestStartupUpdateStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = LensStorage(str(Path(self.temp.name) / "test.db"))
        self.dialogs = []

    def tearDown(self):
        for dialog in self.dialogs:
            dialog.close()
        self.dialogs = []

    def _dialog(
        self,
        result=None,
        can_self_update=True,
        system="linux",
        update_checks_enabled=False,
    ):
        checker = FakeChecker(result or update_result())
        installer = FakeInstaller(can_self_update=can_self_update, system=system)
        dialog = StartupDialog(
            storage=self.storage,
            update_checker=checker,
            update_installer=installer,
            update_checks_enabled=update_checks_enabled,
        )
        self.dialogs.append(dialog)
        return dialog, checker, installer

    def test_available_update_shows_status_and_install_button(self):
        dialog, _checker, _installer = self._dialog()

        dialog._apply_update_result(update_result())

        self.assertIn("0.7.0", dialog.update_status_label.text())
        self.assertIn("0.8.0", dialog.update_status_label.text())
        self.assertFalse(dialog.update_button.isHidden())
        self.assertEqual(dialog.update_button.text(), "Download and install")

    def test_current_version_hides_the_action(self):
        dialog, _checker, _installer = self._dialog()

        dialog._apply_update_result(update_result(STATUS_UP_TO_DATE, with_asset=False))

        self.assertIn("up to date", dialog.update_status_label.text())
        self.assertTrue(dialog.update_button.isHidden())

    def test_missing_platform_asset_offers_the_release_page(self):
        dialog, _checker, _installer = self._dialog()

        dialog._apply_update_result(update_result(STATUS_NO_ASSET, with_asset=False))

        self.assertIn("no build for this platform", dialog.update_status_label.text())
        self.assertEqual(dialog.update_button.text(), "Open release page")

    def test_check_failure_offers_retry_without_a_popup(self):
        dialog, _checker, _installer = self._dialog()

        with mock.patch("openlens.gui.dialogs.startup.QMessageBox.warning") as warning:
            dialog._apply_update_result(update_result(STATUS_ERROR, with_asset=False))

        warning.assert_not_called()
        self.assertIn("Could not check", dialog.update_status_label.text())
        self.assertEqual(dialog.update_button.text(), "Retry")

    def test_self_update_click_starts_the_download(self):
        dialog, _checker, _installer = self._dialog(can_self_update=True)
        result = update_result()
        dialog._apply_update_result(result)

        with mock.patch.object(dialog, "_start_update_download") as start_download:
            dialog._on_update_clicked()

        start_download.assert_called_once_with(result)

    def test_pip_or_dev_install_opens_the_release_page(self):
        dialog, _checker, _installer = self._dialog(can_self_update=False)
        dialog._apply_update_result(update_result())

        with mock.patch.object(dialog, "_open_release_page") as open_page:
            dialog._on_update_clicked()

        open_page.assert_called_once_with(RELEASE_URL)

    def test_retry_starts_another_check(self):
        dialog, _checker, _installer = self._dialog()
        dialog._apply_update_result(update_result(STATUS_ERROR, with_asset=False))

        with mock.patch.object(dialog, "_start_update_check") as start_check:
            dialog._on_update_clicked()

        start_check.assert_called_once_with()

    def test_download_and_install_runs_checker_then_installer(self):
        dialog, checker, installer = self._dialog()
        result = update_result()

        plan = dialog._download_and_install(result)

        self.assertEqual(checker.downloads, [result])
        self.assertEqual(len(installer.prepared), 1)
        self.assertEqual(installer.launched, [plan])

    def test_download_failure_removes_the_partial_file(self):
        dialog, checker, installer = self._dialog()
        result = update_result()
        downloaded = (
            Path(tempfile.mkdtemp(prefix="openlens-test-download-")) / "OpenLens"
        )
        downloaded.write_bytes(b"partial")
        checker.download = mock.Mock(return_value=downloaded)
        installer.prepare = mock.Mock(side_effect=OSError("disk full"))

        with self.assertRaises(OSError):
            dialog._download_and_install(result)

        self.assertFalse(downloaded.exists())

    def test_replace_plan_restarts_by_dismissing_the_welcome_screen(self):
        dialog, _checker, _installer = self._dialog()

        with mock.patch.object(dialog, "reject") as reject:
            dialog._on_update_ready(
                InstallPlan(
                    kind="replace",
                    target=Path("/opt/OpenLens"),
                    script=Path("/tmp/apply.sh"),
                )
            )
            QTest.qWait(350)

        reject.assert_called_once_with()
        self.assertIn("Restarting", dialog.update_status_label.text())

    def test_macos_plan_leaves_the_old_copy_open(self):
        dialog, _checker, _installer = self._dialog()

        with mock.patch.object(dialog, "reject") as reject:
            dialog._on_update_ready(
                InstallPlan(kind="open_bundle", app_path=Path("/tmp/OpenLens.app"))
            )
            QTest.qWait(350)

        reject.assert_not_called()
        self.assertIn("new app has opened", dialog.update_status_label.text())

    def test_env_var_disables_the_automatic_check(self):
        with mock.patch.dict(os.environ, {"OPENLENS_NO_UPDATE_CHECK": "1"}):
            dialog, _checker, _installer = self._dialog(update_checks_enabled=True)
            dialog.show()
            QTest.qWait(50)

        self.assertIsNone(dialog._update_result)
        self.assertEqual(dialog.update_status_label.text(), "OpenLens 0.7.0")

    def test_showing_the_welcome_screen_starts_the_check(self):
        dialog, _checker, _installer = self._dialog(update_checks_enabled=True)
        dialog.show()
        deadline = time.monotonic() + 3.0
        while dialog._update_result is None and time.monotonic() < deadline:
            QTest.qWait(20)

        self.assertIsNotNone(dialog._update_result)
        self.assertIn("0.8.0", dialog.update_status_label.text())


if __name__ == "__main__":
    unittest.main()
