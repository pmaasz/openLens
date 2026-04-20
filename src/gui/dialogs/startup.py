"""
OpenLens PySide6 Dialogs
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QLabel, QGroupBox, QWidget
from PySide6.QtCore import Qt, Signal


class StartupDialog(QDialog):
    """Startup dialog for creating or opening lenses"""
    
    result_selected = Signal(str, object)  # action, data
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenLens")
        self.setModal(True)
        self.setFixedSize(650, 650)
        
        self._selected_action = None
        self._selected_data = None
        self._force_centered_count = 0
        
        self._setup_ui()
    
    def moveEvent(self, event):
        super().moveEvent(event)
        if self._force_centered_count < 5:
            self._recenter()
            self._force_centered_count += 1

    def showEvent(self, event):
        super().showEvent(event)
        self._recenter()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._recenter)
        QTimer.singleShot(500, self._recenter)

    def _recenter(self):
        from PySide6.QtGui import QGuiApplication, QCursor
        screen = QGuiApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        
        if screen:
            avail_geom = screen.availableGeometry()
            x = avail_geom.x() + avail_geom.width() - 325
            y = avail_geom.y() + avail_geom.height() - 325
            current_pos = self.pos()
            if current_pos.x() != x or current_pos.y() != y:
                self.move(x, y)
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("Welcome to OpenLens")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #e0e0e0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        layout.addWidget(QLabel(""))
        
        button_width = 250
        
        new_lens_btn = QPushButton("Create New Lens")
        new_lens_btn.setFixedWidth(button_width)
        new_lens_btn.clicked.connect(self._create_new_lens)
        layout.addWidget(new_lens_btn, alignment=Qt.AlignCenter)
        
        new_assembly_btn = QPushButton("Create New Assembly")
        new_assembly_btn.setFixedWidth(button_width)
        new_assembly_btn.clicked.connect(self._create_new_assembly)
        layout.addWidget(new_assembly_btn, alignment=Qt.AlignCenter)
        
        open_lens_btn = QPushButton("Open Existing Lens")
        open_lens_btn.setFixedWidth(button_width)
        open_lens_btn.clicked.connect(self._show_lens_list)
        layout.addWidget(open_lens_btn, alignment=Qt.AlignCenter)
        
        open_asm_btn = QPushButton("Open Existing Assembly")
        open_asm_btn.setFixedWidth(button_width)
        open_asm_btn.clicked.connect(self._show_assembly_list)
        layout.addWidget(open_asm_btn, alignment=Qt.AlignCenter)
        
        layout.addWidget(QLabel(""))
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list_container)
        
        from src.gui.storage import LensStorage
        try:
            storage = LensStorage("openlens.db", lambda x: None)
            self._all_items = storage.load_lenses()
        except:
            self._all_items = []
            
        layout.addStretch()

    def _show_lens_list(self):
        self._show_list("lens")

    def _show_assembly_list(self):
        self._show_list("assembly")

    def _show_list(self, list_type):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                def clear_layout(layout):
                    while layout.count():
                        child = layout.takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                        elif child.layout():
                            clear_layout(child.layout())
                clear_layout(item.layout())
        
        if list_type == "lens":
            title = "Available Lenses"
            action = "open_lens"
        else:
            title = "Available Assemblies"
            action = "open_assembly"
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        self.list_layout.addWidget(title_label)
        
        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3f3f3f;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #4fc3f7;
                color: #000;
            }
        """)
        
        items = [item for item in self._all_items if item.get('type') == list_type]
        for item in items:
            list_widget.addItem(item.get('name', 'Unnamed'))
        
        self.list_layout.addWidget(list_widget)
        
        btn_layout = QHBoxLayout()
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(lambda: self._open_selected(list_widget, list_type))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(lambda: self._cancel_list(list_type))
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(cancel_btn)
        self.list_layout.addLayout(btn_layout)

    def _open_selected(self, list_widget, list_type):
        current = list_widget.currentItem()
        if current:
            name = current.text()
            for item in self._all_items:
                if item.get('name') == name and item.get('type') == list_type:
                    self._selected_data = item
                    break
        
        self.accept()

    def _cancel_list(self, list_type):
        self._show_list(list_type)

    def _create_new_lens(self):
        self._selected_action = "new_lens"
        self.accept()

    def _create_new_assembly(self):
        self._selected_action = "new_assembly"
        self.accept()