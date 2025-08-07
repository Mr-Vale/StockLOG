import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget

from views.active_cattle import ActiveCattlePage
from views.cattle_entry import CattleEntryPage
from views.cattle_exit import CattleExitPage
from views.cattle_edit import CattleEditPage

DATA_DIR = os.path.join(os.environ.get("PROGRAMDATA"), "StockLOG")
CORE_DIR = os.path.join(DATA_DIR, "Core")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
CONFIG_PATH = os.path.join(DATA_DIR, "Config", "settings.json")

class StockLogApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StockLOG - Cattle Management")
        self.setGeometry(100, 100, 1000, 700)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.active_cattle_page = ActiveCattlePage(self)
        self.cattle_entry_page = CattleEntryPage(self)
        self.cattle_exit_page = CattleExitPage(self)
        self.cattle_edit_page = CattleEditPage(self)

        self.tabs.addTab(self.active_cattle_page, "Active Cattle")
        self.tabs.addTab(self.cattle_entry_page, "Cattle Entry")
        self.tabs.addTab(self.cattle_exit_page, "Cattle Exit")
        self.tabs.addTab(self.cattle_edit_page, "Cattle Edit")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = StockLogApp()
    window.show()
    sys.exit(app.exec_())
