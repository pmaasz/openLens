"""
OpenLens PySide6 Dialogs - Startup
Fixed layout and styling based on user feedback.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QListWidget, QLabel, QWidget, QFileDialog, QMessageBox, QFrame,
                               QScrollArea)
from PySide6.QtCore import Qt, Signal


class StartupDialog(QDialog):
    """Startup dialog for creating or opening lenses"""
    
    result_selected = Signal(str, object)  # action, data
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome to OpenLens")
        self.setModal(True)
        self.setFixedSize(650, 650)
        
        self._selected_action = None
        self._selected_data = None
        self._force_centered_count = 0
        
        # Load database items once
        from src.gui.storage import LensStorage
        try:
            storage = LensStorage("openlens.db", lambda x: None)
            self._all_items = storage.load_lenses()
        except Exception as e:
            print(f"Error loading database: {e}")
            self._all_items = []
            
        self._setup_ui()
    
    def _recenter(self):
        from PySide6.QtGui import QGuiApplication, QCursor
        screen = QGuiApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        
        if screen:
            avail_geom = screen.availableGeometry()
            x = avail_geom.x() + (avail_geom.width() - self.width()) // 2
            y = avail_geom.y() + (avail_geom.height() - self.height()) // 2
            self.move(x, y)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(40, 40, 40, 40)
        
        title = QLabel("Welcome to OpenLens")
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        button_width = 350
        btn_style = """
            QPushButton {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 10px;
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
        self.list_header_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; margin-top: 10px;")
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

    def _show_list(self, list_type):
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
            from src.lens import Lens as TypeClass
        else:
            title = "Available Assemblies"
            from src.optical_system import OpticalSystem as TypeClass

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
        list_widget.setMinimumHeight(400)
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                padding: 10px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #333333;
                color: #ffffff;
            }
        """)
        
        # Filter items
        items = [item for item in self._all_items if isinstance(item, TypeClass)]
        for item in items:
            list_widget.addItem(getattr(item, 'name', 'Unnamed'))
            
        container_layout.addWidget(list_widget)
        self.list_layout.addWidget(container)

        # Rebuild fixed bottom controls
        self.bottom_controls.setVisible(True)
        
        # Spacer to push buttons
        self.bottom_controls_layout.addStretch(1)

        # Open Selected button in the center
        open_btn = QPushButton("Open Selected")
        open_btn.setFixedWidth(150)
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
        open_btn.clicked.connect(lambda: self._open_selected(list_widget, items, list_type))
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
                qproperty-icon: url(none); /* Clear existing */
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        # Create a simple SVG-like icon using a painter or just better styling
        from PySide6.QtGui import QIcon, QPainter, QPen, QPixmap, QColor
        def create_icon(icon_type):
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
        minus_btn.clicked.connect(lambda: self._on_delete(list_widget, items, list_type))

        action_layout.addWidget(plus_btn)
        action_layout.addWidget(minus_btn)
        self.bottom_controls_layout.addWidget(action_btns)
        
        # Double-click to open
        list_widget.itemDoubleClicked.connect(lambda item: self._open_selected(list_widget, items, list_type))
        
        self._recenter()
        
        # Double-click to open
        list_widget.itemDoubleClicked.connect(lambda item: self._open_selected(list_widget, items, list_type))
        
        self._recenter()

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout(child.layout())

    def _open_selected(self, list_widget, items, list_type):
        idx = list_widget.currentRow()
        if idx >= 0:
            self._selected_data = items[idx]
            self._selected_action = f"open_{list_type}"
            self.accept()

    def _on_import(self, list_type):
        """Import from JSON file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, f"Import {list_type.capitalize()}", "", "JSON Files (*.json);;All Files (*)"
        )
        if filename:
            try:
                import json
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                from src.lens import Lens
                from src.optical_system import OpticalSystem
                
                if list_type == "lens":
                    imported = Lens.from_dict(data)
                else:
                    imported = OpticalSystem.from_dict(data)
                
                self._selected_data = imported
                self._selected_action = f"open_{list_type}"
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")

    def _on_delete(self, list_widget, items, list_type):
        """Delete from database"""
        idx = list_widget.currentRow()
        if idx < 0:
            return
            
        item = items[idx]
        name = getattr(item, 'name', 'Unnamed')
        
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete '{name}' from the database?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            from src.gui.storage import LensStorage
            try:
                storage = LensStorage("openlens.db", lambda x: None)
                remaining = [i for i in self._all_items if i != item]
                storage.save_lenses(remaining)
                self._all_items = remaining
                self._show_list(list_type) # Refresh
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete: {e}")

    def _create_new_lens(self):
        self._selected_action = "create_lens"
        self.accept()

    def _create_new_assembly(self):
        self._selected_action = "create_assembly"
        self.accept()

    def get_result(self):
        return self._selected_action, self._selected_data
