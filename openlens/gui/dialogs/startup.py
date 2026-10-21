"""
OpenLens PySide6 Dialogs - Startup
Fixed layout and styling based on user feedback.
"""

import logging
import os
from typing import Any, List, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QLabel,
    QWidget,
    QFileDialog,
    QMessageBox,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices

from ...database import LensInUseError
from ...updater import (
    STATUS_ERROR,
    STATUS_NO_ASSET,
    STATUS_UP_TO_DATE,
    STATUS_UPDATE_AVAILABLE,
    InstallPlan,
    UpdateCheckResult,
    UpdateChecker,
    UpdateInstaller,
)
from ..workers import AnalysisWorker, stop_worker

logger = logging.getLogger(__name__)


class StartupDialog(QDialog):
    """Startup dialog for creating or opening lenses"""

    result_selected = Signal(str, object)  # action, data

    def __init__(
        self,
        storage=None,
        update_checker: Optional[UpdateChecker] = None,
        update_installer: Optional[UpdateInstaller] = None,
        update_checks_enabled: bool = True,
    ) -> None:
        """Initialize the dialog and load stored lenses and assemblies.

        Loads all stored items once into ``_all_items``, falling back to an
        empty list when the database cannot be read.

        Args:
            storage: Optional :class:`~openlens.gui.storage.LensStorage` to use.
                Injected rather than constructed here so the dialog operates on
                the same database as the rest of the app; hard-coding
                ``"openlens.db"`` meant it deleted from a different file than
                the one the user was looking at.
            update_checker: Release checker; a default one is built when omitted.
            update_installer: Install planner; a default one is built when omitted.
            update_checks_enabled: Set false to suppress the automatic check,
                used by tests and by embedders that do not want network traffic.
        """
        super().__init__()
        self.setWindowTitle("Welcome to OpenLens")
        self.setModal(True)
        self.setFixedSize(650, 650)

        self._selected_action = None
        self._selected_data = None
        self._force_centered_count = 0

        self._update_checker = update_checker or UpdateChecker()
        self._update_installer = update_installer or UpdateInstaller()
        no_check = os.environ.get("OPENLENS_NO_UPDATE_CHECK", "").strip().lower()
        self._update_checks_enabled = update_checks_enabled and no_check not in {
            "1",
            "true",
            "yes",
        }
        self._update_check_started = False
        self._update_worker: Optional[AnalysisWorker] = None
        self._download_worker: Optional[AnalysisWorker] = None
        self._update_result: Optional[UpdateCheckResult] = None

        # Load database items once
        from ..storage import LensStorage

        self._storage = (
            storage if storage is not None else LensStorage(None, lambda x: None)
        )
        try:
            self._all_items = self._storage.load_lenses()
        except Exception as e:
            logger.warning("Could not load the lens library: %s", e)
            self._all_items = []

        self._setup_ui()

        if not self._update_checks_enabled:
            current = getattr(self._update_checker, "current_version", "")
            self._set_update_status(f"OpenLens {current}".strip())

    def _recenter(self) -> None:
        """Center the dialog on the screen containing the mouse cursor."""
        from PySide6.QtGui import QGuiApplication, QCursor

        screen = QGuiApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()

        if screen:
            avail_geom = screen.availableGeometry()
            x = avail_geom.x() + (avail_geom.width() - self.width()) // 2
            y = avail_geom.y() + (avail_geom.height() - self.height()) // 2
            self.move(x, y)

    def _setup_ui(self) -> None:
        """Build the static welcome screen with the four main action buttons."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Welcome to OpenLens")
        title.setStyleSheet(
            "font-size: 26px; font-weight: bold; color: #ffffff; margin-bottom: 10px;"
        )
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Update status sits under the title so it is visible on the welcome
        # screen without pushing the four primary actions around.
        self.update_bar = QWidget()
        update_layout = QHBoxLayout(self.update_bar)
        update_layout.setContentsMargins(0, 0, 0, 0)
        update_layout.setSpacing(8)
        self.update_status_label = QLabel("Checking for updates\u2026")
        self.update_status_label.setAlignment(Qt.AlignCenter)
        self.update_status_label.setStyleSheet("color: #9a9a9a; font-size: 12px;")
        update_layout.addWidget(self.update_status_label, 1)
        self.update_button = QPushButton("")
        self.update_button.setCursor(Qt.PointingHandCursor)
        self.update_button.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #444444;
                padding: 5px 10px;
                font-size: 12px;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #333333;
                border: 1px solid #0078d4;
            }
            QPushButton:disabled {
                color: #777777;
                border-color: #333333;
            }
            """)
        self.update_button.setVisible(False)
        self.update_button.clicked.connect(self._on_update_clicked)
        update_layout.addWidget(self.update_button, 0)
        layout.addWidget(self.update_bar)

        button_width = 350
        btn_style = """
            QPushButton {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 8px;
                font-size: 14px;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #444444;
                border: 1px solid #0078d4;
            }
        """

        # 1. Create New Lens
        new_lens_btn = QPushButton("Create New Lens")
        new_lens_btn.setFixedWidth(button_width)
        new_lens_btn.setStyleSheet(btn_style)
        new_lens_btn.clicked.connect(self._create_new_lens)
        layout.addWidget(new_lens_btn, alignment=Qt.AlignCenter)

        # 2. Create New Assembly
        new_assembly_btn = QPushButton("Create New Assembly")
        new_assembly_btn.setFixedWidth(button_width)
        new_assembly_btn.setStyleSheet(btn_style)
        new_assembly_btn.clicked.connect(self._create_new_assembly)
        layout.addWidget(new_assembly_btn, alignment=Qt.AlignCenter)

        # 3. Open Existing Lens
        open_lens_btn = QPushButton("Open Existing Lens")
        open_lens_btn.setFixedWidth(button_width)
        open_lens_btn.setStyleSheet(btn_style)
        open_lens_btn.clicked.connect(lambda: self._show_list("lens"))
        layout.addWidget(open_lens_btn, alignment=Qt.AlignCenter)

        # 4. Open Existing Assembly
        open_asm_btn = QPushButton("Open Existing Assembly")
        open_asm_btn.setFixedWidth(button_width)
        open_asm_btn.setStyleSheet(btn_style)
        open_asm_btn.clicked.connect(lambda: self._show_list("assembly"))
        layout.addWidget(open_asm_btn, alignment=Qt.AlignCenter)

        # Area for title and list
        self.list_header_label = QLabel("")
        self.list_header_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #ffffff; margin-top: 10px;"
        )
        self.list_header_label.setVisible(False)
        layout.addWidget(self.list_header_label)

        # Container for the dynamic list view
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_scroll.setStyleSheet("background: transparent;")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_scroll.setWidget(self.list_container)
        layout.addWidget(self.list_scroll)

        # Bottom controls area (fixed at bottom, outside scroll)
        self.bottom_controls = QWidget()
        self.bottom_controls.setFixedHeight(60)
        self.bottom_controls_layout = QHBoxLayout(self.bottom_controls)
        self.bottom_controls_layout.setContentsMargins(0, 0, 0, 10)
        self.bottom_controls.setVisible(False)
        layout.addWidget(self.bottom_controls)

        layout.addStretch()

    def showEvent(self, event) -> None:
        """Start the release check when the welcome screen is first shown."""
        super().showEvent(event)
        if self._update_checks_enabled and not self._update_check_started:
            self._update_check_started = True
            QTimer.singleShot(0, self._start_update_check)

    def closeEvent(self, event) -> None:
        """Stop background update work before the dialog goes away."""
        self._stop_update_workers()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        """Stop background update work however the dialog is dismissed."""
        self._stop_update_workers()
        super().done(result)

    def _stop_update_workers(self) -> None:
        """Ask any running update thread to stop and drop its reference.

        The wait is deliberately short: this runs when the user picks one of
        the welcome-screen actions, and a slow network request must not freeze
        the dialog. A terminated check or download has no side effect beyond
        an unfinished ``.part`` file.
        """
        for attribute in ("_update_worker", "_download_worker"):
            worker = getattr(self, attribute, None)
            if worker is not None and stop_worker(worker, timeout_ms=250):
                setattr(self, attribute, None)

    def _set_update_status(self, text: str, tooltip: str = "") -> None:
        """Set the small status line under the title."""
        self.update_status_label.setText(text)
        self.update_status_label.setToolTip(tooltip)

    def _show_update_button(self, text: str, enabled: bool = True) -> None:
        """Show the update action with the given label."""
        self.update_button.setText(text)
        self.update_button.setEnabled(enabled)
        self.update_button.setVisible(True)

    def _start_update_check(self) -> None:
        """Check for a newer release on a worker thread."""
        if self._update_worker is not None and self._update_worker.isRunning():
            return

        self._set_update_status("Checking for updates\u2026")
        self.update_button.setVisible(False)
        worker = AnalysisWorker(self._update_checker.check, self)
        worker.done.connect(self._apply_update_result)
        worker.failed.connect(self._on_update_check_failed)
        worker.finished.connect(self._on_check_worker_finished)
        self._update_worker = worker
        worker.start()

    def _on_check_worker_finished(self) -> None:
        """Release the check worker once its thread has actually finished."""
        worker = self.sender()
        if worker is self._update_worker:
            self._update_worker = None
        if worker is not None:
            worker.deleteLater()

    def _apply_update_result(self, result: UpdateCheckResult) -> None:
        """Render the result of a release check."""
        self._update_result = result

        if result.status == STATUS_UPDATE_AVAILABLE:
            latest = result.latest_version or "A newer version"
            self._set_update_status(
                f"OpenLens {result.current_version} \u2192 {latest} is available."
            )
            if self._update_installer.can_self_update():
                self._show_update_button("Download and install")
            else:
                self._show_update_button("Download from GitHub")
        elif result.status == STATUS_UP_TO_DATE:
            self._set_update_status(f"OpenLens {result.current_version} is up to date.")
            self.update_button.setVisible(False)
        elif result.status == STATUS_NO_ASSET:
            latest = result.latest_version or "A newer version"
            self._set_update_status(
                f"OpenLens {result.current_version} \u2192 {latest}: "
                "no build for this platform."
            )
            self._show_update_button("Open release page")
        else:
            self._set_update_status(
                "Could not check for updates.",
                result.message,
            )
            self._show_update_button("Retry")

    def _on_update_check_failed(self, message: str) -> None:
        """Render an unexpected worker failure as a retryable check error."""
        self._apply_update_result(
            UpdateCheckResult(
                status=STATUS_ERROR,
                current_version=self._update_checker.current_version,
                release_url=self._update_checker.releases_page,
                message=message,
            )
        )

    def _on_update_clicked(self) -> None:
        """Retry, download, or open the release page depending on the result."""
        result = self._update_result
        if result is None:
            self._start_update_check()
            return

        if result.status == STATUS_ERROR:
            self._start_update_check()
            return

        if (
            result.status == STATUS_UPDATE_AVAILABLE
            and self._update_installer.can_self_update()
        ):
            self._start_update_download(result)
            return

        self._open_release_page(result.release_url)

    def _open_release_page(self, url: Optional[str]) -> None:
        """Open the release page in the user's browser."""
        target = url or self._update_checker.releases_page
        if QDesktopServices.openUrl(QUrl(target)):
            self._set_update_status("Opened the release page in your browser.")
            self.update_button.setVisible(False)
        else:
            QMessageBox.warning(
                self,
                "Could not open browser",
                f"Open this page to download the update:\n\n{target}",
            )

    def _start_update_download(self, result: UpdateCheckResult) -> None:
        """Download and apply *result* on a worker thread."""
        self.update_button.setEnabled(False)
        latest = result.latest_version or "the new version"
        self._set_update_status(f"Downloading OpenLens {latest}\u2026")

        worker = AnalysisWorker(lambda: self._download_and_install(result), self)
        worker.done.connect(self._on_update_ready)
        worker.failed.connect(self._on_update_download_failed)
        worker.finished.connect(self._on_download_worker_finished)
        self._download_worker = worker
        worker.start()

    def _download_and_install(self, result: UpdateCheckResult) -> InstallPlan:
        """Download the asset, prepare the install, and launch the helper.

        This runs on the worker thread. It must not touch widgets.
        """
        downloaded = None
        try:
            downloaded = self._update_checker.download(result)
            plan = self._update_installer.prepare(downloaded, result)
            self._update_installer.launch(plan)
            return plan
        except Exception:
            # launch() is the last risky step. If it failed, no helper is
            # waiting for the file, so the partial download can be removed.
            if downloaded is not None:
                downloaded.unlink(missing_ok=True)
            raise

    def _on_download_worker_finished(self) -> None:
        """Release the download worker once its thread has actually finished."""
        worker = self.sender()
        if worker is self._download_worker:
            self._download_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_update_ready(self, plan: InstallPlan) -> None:
        """React to a successfully launched installer."""
        if plan.kind == "replace":
            self._set_update_status("Update downloaded. Restarting\u2026")
            self.update_button.setVisible(False)
            QTimer.singleShot(250, self.reject)
        elif plan.kind == "open_bundle":
            self._set_update_status(
                "The new app has opened. Drag it to Applications, then close this copy."
            )
            self.update_button.setVisible(False)
        else:
            self._open_release_page(plan.release_url)

    def _on_update_download_failed(self, message: str) -> None:
        """Report a download/install failure without quitting the app."""
        self._set_update_status("Update download failed.", message)
        self._show_update_button("Try again")
        QMessageBox.warning(
            self,
            "Update failed",
            f"OpenLens could not download or prepare the update:\n\n{message}",
        )

    def _show_list(self, list_type: str) -> None:
        """Show list of items matching the visual design in the image"""
        # Clear existing list UI
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        # Clear existing bottom controls
        while self.bottom_controls_layout.count():
            item = self.bottom_controls_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        if list_type == "lens":
            title = "Available Lenses"
            from ...lens import Lens as TypeClass
        else:
            title = "Available Assemblies"
            from ...optical_system import OpticalSystem as TypeClass

        # Update and show header
        self.list_header_label.setText(title)
        self.list_header_label.setVisible(True)

        # Main container for list (inside scroll area)
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                border: 1px solid #333333;
                background-color: transparent;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # List widget
        list_widget = QListWidget()
        list_widget.setMinimumHeight(450)
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                padding: 10px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: #333333;
                color: #ffffff;
            }
        """)

        # Filter items
        items = [item for item in self._all_items if isinstance(item, TypeClass)]
        for item in items:
            list_widget.addItem(getattr(item, "name", "Unnamed"))

        container_layout.addWidget(list_widget)
        self.list_layout.addWidget(container)

        # Rebuild fixed bottom controls
        self.bottom_controls.setVisible(True)

        # Spacer to push buttons
        self.bottom_controls_layout.addStretch(1)

        # Open Selected button in the center
        open_btn = QPushButton("Open Selected")
        open_btn.setFixedWidth(125)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #444444;
                padding: 8px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #333333;
                border: 1px solid #555555;
            }
        """)
        open_btn.clicked.connect(
            lambda: self._open_selected(list_widget, items, list_type)
        )
        self.bottom_controls_layout.addWidget(open_btn)

        self.bottom_controls_layout.addStretch(1)

        # +/- Buttons at the right
        action_btns = QWidget()
        action_layout = QHBoxLayout(action_btns)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(10)

        plus_btn = QPushButton()
        plus_btn.setFixedSize(36, 36)
        plus_btn.setToolTip("Import from file")
        plus_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: 1px solid #555555;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        # Create a simple SVG-like icon using a painter or just better styling
        from PySide6.QtGui import QIcon, QPainter, QPen, QPixmap, QColor

        def create_icon(icon_type: str) -> QIcon:
            """Draw a plus ("plus") or minus icon pixmap."""
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor("#ffffff"), 3)
            painter.setPen(pen)
            if icon_type == "plus":
                painter.drawLine(16, 8, 16, 24)
                painter.drawLine(8, 16, 24, 16)
            else:
                painter.drawLine(8, 16, 24, 16)
            painter.end()
            return QIcon(pixmap)

        plus_btn.setIcon(create_icon("plus"))
        plus_btn.clicked.connect(lambda: self._on_import(list_type))

        minus_btn = QPushButton()
        minus_btn.setFixedSize(36, 36)
        minus_btn.setToolTip("Delete selected")
        minus_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: 1px solid #555555;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        minus_btn.setIcon(create_icon("minus"))
        minus_btn.clicked.connect(
            lambda: self._on_delete(list_widget, items, list_type)
        )

        action_layout.addWidget(plus_btn)
        action_layout.addWidget(minus_btn)
        self.bottom_controls_layout.addWidget(action_btns)

        # Double-click to open
        list_widget.itemDoubleClicked.connect(
            lambda item: self._open_selected(list_widget, items, list_type)
        )

        self._recenter()

        # Double-click to open
        list_widget.itemDoubleClicked.connect(
            lambda item: self._open_selected(list_widget, items, list_type)
        )

        self._recenter()

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        """Recursively remove and delete all widgets and sub-layouts."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout(child.layout())

    def _open_selected(
        self, list_widget: QListWidget, items: List[Any], list_type: str
    ) -> None:
        """Accept the dialog with an ``open_<list_type>`` action for the highlighted item.

        Sets ``_selected_action`` to "open_lens" or "open_assembly" and
        ``_selected_data`` to the selected Lens/OpticalSystem instance.
        """
        idx = list_widget.currentRow()
        if idx >= 0:
            self._selected_data = items[idx]
            self._selected_action = f"open_{list_type}"
            self.accept()

    def _on_import(self, list_type: str) -> None:
        """Import from JSON file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            f"Import {list_type.capitalize()}",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if filename:
            try:
                import json

                from ...validation import (
                    reject_non_finite_numbers,
                    validate_json_file_path,
                    validate_lens_data_schema,
                )

                with open(validate_json_file_path(filename, must_exist=True), "r") as f:
                    data = json.load(f)

                # json.load accepts the bare NaN and Infinity literals, which
                # are not valid JSON. Without this a hand-edited file installs a
                # lens with a NaN radius, whose focal length is NaN - and NaN
                # compares false against every threshold, so it passes every
                # downstream check silently.
                reject_non_finite_numbers(data, "imported file")

                from ...lens import Lens
                from ...optical_system import OpticalSystem

                if list_type == "lens":
                    imported = Lens.from_dict(validate_lens_data_schema(data))
                else:
                    imported = OpticalSystem.from_dict(data)

                self._selected_data = imported
                self._selected_action = f"open_{list_type}"
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")

    def _on_delete(
        self, list_widget: QListWidget, items: List[Any], list_type: str
    ) -> None:
        """Delete from database"""
        idx = list_widget.currentRow()
        if idx < 0:
            return

        item = items[idx]
        name = getattr(item, "name", "Unnamed")

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{name}' from the database?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # delete_item, not save_lenses(remaining): save_lenses defaults to
            # reconcile=False and only inserts or replaces rows, so nothing was
            # ever deleted and the item came back on the next start. It is also
            # the only path that enforces the in-use guard, so an assembly
            # cannot be left pointing at a deleted lens.
            try:
                self._storage.delete_item(item.id)
            except LensInUseError as e:
                QMessageBox.warning(
                    self,
                    "Cannot delete",
                    f"'{name}' is still used by an assembly:\n\n{e}",
                )
                return
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete: {e}")
                return

            self._all_items = [i for i in self._all_items if i != item]
            self._show_list(list_type)  # Refresh

    def _create_new_lens(self) -> None:
        """Accept the dialog with the "create_lens" action and no data selected."""
        self._selected_action = "create_lens"
        self.accept()

    def _create_new_assembly(self) -> None:
        """Accept the dialog with the "create_assembly" action and no data selected."""
        self._selected_action = "create_assembly"
        self.accept()

    def get_result(self) -> Tuple[Optional[str], Optional[Any]]:
        """Return the selected action and associated data.

        Returns:
            Tuple ``(action, data)`` where ``action`` is one of "create_lens",
            "create_assembly", "open_lens", or "open_assembly" (or ``None`` if
            nothing was selected), and ``data`` is the selected
            Lens/OpticalSystem instance for "open_*" actions and ``None`` for
            "create_*" actions.
        """
        return self._selected_action, self._selected_data
