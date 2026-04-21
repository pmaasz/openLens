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
        
        # Container for the dynamic list view
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_scroll.setStyleSheet("background: transparent;")
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 20, 0, 0)
        self.list_scroll.setWidget(self.list_container)
        layout.addWidget(self.list_scroll)
        
        layout.addStretch()

    def _show_list(self, list_type):
        """Show list of items with overlay +/- buttons at bottom right"""
        # Clear existing list UI
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        if list_type == "lens":
            title = "Stored Lenses"
            from src.lens import Lens as TypeClass
        else:
            title = "Stored Assemblies"
            from src.optical_system import OpticalSystem as TypeClass

        # List Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #aaaaaa; margin-bottom: 5px;")
        self.list_layout.addWidget(title_label)
        
        # Create a container for list + buttons
        list_wrapper = QWidget()
        wrapper_layout = QVBoxLayout(list_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        
        # List widget
        list_widget = QListWidget()
        list_widget.setMinimumHeight(250)
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #333333;
                padding: 2px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #252525;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
        """)
        
        # Filter items by type
        items = [item for item in self._all_items if isinstance(item, TypeClass)]
        for item in items:
            list_widget.addItem(getattr(item, 'name', 'Unnamed'))
            
        wrapper_layout.addWidget(list_widget)
        
        # Floating-style buttons at bottom right of the list area
        buttons_container = QWidget(list_widget)
        btn_layout = QHBoxLayout(buttons_container)
        btn_layout.setContentsMargins(0, 0, 10, 10)
        btn_layout.setSpacing(5)
        
        # Minus (-) button for delete
        delete_btn = QPushButton("-")
        delete_btn.setToolTip(f"Delete selected {list_type}")
        delete_btn.setFixedSize(26, 26)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #444444;
                font-size: 18px;
                font-family: 'Courier New', Courier, monospace;
                font-weight: bold;
                border-radius: 0px;
                line-height: 26px;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #442222;
                color: #ff5555;
                border: 1px solid #ff5555;
            }
        """)
        delete_btn.clicked.connect(lambda: self._on_delete(list_widget, items, list_type))
        
        # Plus (+) button for import
        import_btn = QPushButton("+")
        import_btn.setToolTip(f"Import {list_type} from file")
        import_btn.setFixedSize(26, 26)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #444444;
                font-size: 18px;
                font-family: 'Courier New', Courier, monospace;
                font-weight: bold;
                border-radius: 0px;
                line-height: 26px;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #224422;
                color: #55ff55;
                border: 1px solid #55ff55;
            }
        """)
        import_btn.clicked.connect(lambda: self._on_import(list_type))
        
        btn_layout.addStretch()
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(import_btn)
        
        # Position buttons at the bottom right of the list_widget
        def update_button_pos():
            buttons_container.resize(list_widget.width(), 40)
            buttons_container.move(0, list_widget.height() - 40)
        
        list_widget.resized = update_button_pos
        # Note: In PySide6 we'd typically override resizeEvent, but for this dynamic layout:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10, update_button_pos)

        self.list_layout.addWidget(list_wrapper)
        
        # Double-click to open
        list_widget.itemDoubleClicked.connect(lambda item: self._open_selected(list_widget, items, list_type))
        
        # Adjust dialog size and recenter if needed
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
