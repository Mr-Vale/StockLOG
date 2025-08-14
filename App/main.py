import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QDialog, QLabel
)
from views.active_cattle import ActiveCattlePage
from views.cattle_entry import CattleEntryPage
from views.cattle_exit import CattleExitPage
from views.cattle_edit import CattleEditPage
from views.feed_supplies import FeedAndSuppliesPage
from views.cattle_feed import CattleFeedPage
from views.chem_inventory import ChemInventoryPage  # <-- NEW TAB IMPORT

DATA_DIR = os.path.join(os.environ.get("PROGRAMDATA"), "StockLOG")
CORE_DIR = os.path.join(DATA_DIR, "Core")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
CONFIG_PATH = os.path.join(DATA_DIR, "Config", "settings.json")

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings page placeholder. Add settings widgets here."))

class StockLogApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StockLOG - Cattle Management")
        self.setGeometry(100, 100, 1000, 700)

        # Central Widget: Use a QWidget with VBoxLayout to host the Toolbar + TabWidget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Toolbar with right-justified buttons
        button_bar = QHBoxLayout()
        button_bar.addStretch()  # This pushes the following buttons to the right

        self.refresh_button = QPushButton("Refresh All")
        self.refresh_button.setToolTip("Refresh all tabs and data displays")
        self.refresh_button.clicked.connect(self.refresh_all_tabs)
        button_bar.addWidget(self.refresh_button)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setToolTip("Open application settings")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        button_bar.addWidget(self.settings_button)

        main_layout.addLayout(button_bar)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.active_cattle_page = ActiveCattlePage(self)
        self.cattle_entry_page = CattleEntryPage(self)
        self.cattle_exit_page = CattleExitPage(self)
        self.cattle_edit_page = CattleEditPage(self)
        self.feed_and_supplies_page = FeedAndSuppliesPage(self)
        self.cattle_feed_page = CattleFeedPage(self)
        self.chem_inventory_page = ChemInventoryPage(self)  # <-- NEW TAB INSTANCE

        self.tabs.addTab(self.active_cattle_page, "Active Cattle")
        self.tabs.addTab(self.cattle_entry_page, "Cattle Entry")
        self.tabs.addTab(self.cattle_exit_page, "Cattle Exit")
        self.tabs.addTab(self.cattle_edit_page, "Cattle Edit")
        self.tabs.addTab(self.feed_and_supplies_page, "Feed and Supplies")
        self.tabs.addTab(self.cattle_feed_page, "Cattle Feed")
        self.tabs.addTab(self.chem_inventory_page, "Chemical Inventory")  # <-- NEW TAB

    def refresh_all_tabs(self):
        """
        Call refresh_data() on all pages/tabs.
        Also, ensure status check (exit date/status) is performed, even if Active Cattle tab is not visible.
        """
        # Always run active cattle page's refresh first so status is checked/updated for all cattle
        if hasattr(self.active_cattle_page, "refresh_data"):
            self.active_cattle_page.refresh_data()
        # Then refresh the other tabs
        for page in [
            self.cattle_entry_page,
            self.cattle_exit_page,
            self.cattle_edit_page,
            self.feed_and_supplies_page,
            self.cattle_feed_page,
            self.chem_inventory_page,         # <-- Add new tab here
        ]:
            if hasattr(page, "refresh_data"):
                page.refresh_data()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = StockLogApp()
    window.show()
    sys.exit(app.exec_())