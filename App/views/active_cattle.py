import os
import sqlite3
import datetime
import csv
import time
import json
import subprocess

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableView,
    QHeaderView, QGroupBox, QGridLayout, QPushButton, QHBoxLayout,
    QLineEdit, QMenu, QFileDialog, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QVariant
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtGui import QPainter

DATA_DIR = r"C:\ProgramData\StockLOG"
CORE_DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

class CattleTableModel(QAbstractTableModel):
    def __init__(self, data, headers):
        super().__init__()
        self._data = data
        self._headers = headers

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        row = index.row()
        col = index.column()
        value = self._data[row][col]
        if role == Qt.DisplayRole:
            # Entry date, Age, and Safe Sale Date columns: show formatted string
            if col == 0 or col == 7 or col == 8:
                return value[1]
            return value
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._headers[section]
            else:
                return section + 1
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        return QVariant()

class AllColumnsFilterProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        filter_text = self.filterRegExp().pattern()
        if not filter_text:
            return True
        for column in range(self.sourceModel().columnCount()):
            index = self.sourceModel().index(source_row, column, source_parent)
            data = str(self.sourceModel().data(index, Qt.DisplayRole))
            if filter_text.lower() in data.lower():
                return True
        return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return section + 1
        return super().headerData(section, orientation, role)

    def lessThan(self, left, right):
        column = left.column()
        # Entry date sorting
        if column == 0:
            left_raw = self.sourceModel()._data[left.row()][0][0]
            right_raw = self.sourceModel()._data[right.row()][0][0]
            return left_raw < right_raw
        # Age sorting
        if column == 7:
            left_raw = self.sourceModel()._data[left.row()][7][0]
            right_raw = self.sourceModel()._data[right.row()][7][0]
            return left_raw < right_raw
        # Safe Sale Date sorting
        if column == 8:
            left_raw = self.sourceModel()._data[left.row()][8][0]
            right_raw = self.sourceModel()._data[right.row()][8][0]
            return left_raw < right_raw
        return super().lessThan(left, right)

class ActiveCattlePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout()

        # --- Summary cards row: Cattle Summary | Mob Summary ---
        summary_cards_row = QHBoxLayout()

        # Cattle summary section (table style)
        self.summary_group = QGroupBox(" Cattle Summary ")
        self.summary_layout = QGridLayout()
        self.summary_group.setLayout(self.summary_layout)
        summary_cards_row.addWidget(self.summary_group)

        # Mob summary section (table style)
        self.mob_group = QGroupBox(" Mob Summary ")
        self.mob_layout = QGridLayout()
        self.mob_group.setLayout(self.mob_layout)
        summary_cards_row.addWidget(self.mob_group)

        self.layout.addLayout(summary_cards_row)

        # --- Controls row: Refresh button + Filter + Export Buttons + Print Button ---
        controls_row = QHBoxLayout()
        self.refresh_button = QPushButton(" Refresh ")
        self.refresh_button.clicked.connect(self.load_data_with_status_check)
        controls_row.addWidget(self.refresh_button)

        self.export_table_btn = QPushButton(" Export Table ")
        self.export_table_btn.clicked.connect(self.export_table_csv)
        controls_row.addWidget(self.export_table_btn)

        self.export_summary_btn = QPushButton(" Export Cattle Summary ")
        self.export_summary_btn.clicked.connect(self.export_summary_csv)
        controls_row.addWidget(self.export_summary_btn)

        self.export_mob_btn = QPushButton(" Export Mob Summary ")
        self.export_mob_btn.clicked.connect(self.export_mob_csv)
        controls_row.addWidget(self.export_mob_btn)

        self.print_btn = QPushButton(" Print ")
        self.print_btn.clicked.connect(self.print_prompt)
        controls_row.addWidget(self.print_btn)

        controls_row.addWidget(QLabel("Filter:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Type to filter...")
        self.filter_edit.textChanged.connect(self.apply_filter)
        controls_row.addWidget(self.filter_edit)
        controls_row.addStretch()

        self.layout.addLayout(controls_row)

        # --- Main Table ---
        self.table_headers = [
            " FARM ENTRY DATE ", " NLIS ID NO. ", " NLIS RFID NO. ",
            " BREED/DESCRIPTION ", " SEX ", " MOB NUMBER ",
            " TOTAL VALUE ", " AGE ", " SAFE SALE DATE "
        ]
        self.table_data = []

        self.table_view = QTableView()
        self.model = CattleTableModel(self.table_data, self.table_headers)
        self.proxy_model = AllColumnsFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setAlternatingRowColors(True)

        # Center headers and make columns resizable by user
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setDefaultAlignment(Qt.AlignCenter)

        # Enable right-click to copy
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_table_context_menu)

        self.layout.addWidget(self.table_view)
        self.setLayout(self.layout)

        # Store summaries for export
        self.cattle_summary_rows = []
        self.mob_summary_rows = []
        
        # Refresh Button
        self.load_data_with_status_check()
    
    # Global refresh button
    def refresh_data(self):
        self.load_data_with_status_check()
        

    def apply_filter(self, text):
        self.proxy_model.setFilterWildcard(text)

    def show_table_context_menu(self, pos):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
        menu = QMenu()
        copy_action = menu.addAction(" Copy Selected ")
        action = menu.exec_(self.table_view.viewport().mapToGlobal(pos))
        if action == copy_action:
            self.copy_selected_cells()

    def copy_selected_cells(self):
        selection = self.table_view.selectionModel().selectedIndexes()
        if not selection:
            return
        selection = sorted(selection, key=lambda x: (x.row(), x.column()))
        current_row = selection[0].row()
        row_data = []
        all_rows = []
        for index in selection:
            if index.row() != current_row:
                all_rows.append(','.join(row_data))
                row_data = []
                current_row = index.row()
            row_data.append(str(index.data()))
        if row_data:
            all_rows.append(','.join(row_data))
        clipboard = QApplication.clipboard()
        clipboard.setText('\n'.join(all_rows))

    def export_table_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Table CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([header.strip() for header in self.table_headers])
            for row in range(self.proxy_model.rowCount()):
                row_items = []
                for col in range(self.proxy_model.columnCount()):
                    index = self.proxy_model.index(row, col)
                    val = index.data()
                    if isinstance(val, str):
                        val = val.strip()
                    row_items.append(val)
                writer.writerow(row_items)

    def export_summary_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Cattle Summary CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Type", "Total", "Males", "Females"])
            for row in self.cattle_summary_rows:
                writer.writerow(row)

    def export_mob_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Mob Summary CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Mob", "Total", "Males", "Females", "Total Value"])
            for row in self.mob_summary_rows:
                writer.writerow(row)

    def print_prompt(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Print Selection")
        msg.setText("What would you like to print?")
        table_btn = msg.addButton("Table Only", QMessageBox.AcceptRole)
        page_btn = msg.addButton("Whole Page", QMessageBox.AcceptRole)
        msg.addButton(QMessageBox.Cancel)
        msg.exec_()
        chosen_btn = msg.clickedButton()
        if chosen_btn == table_btn:
            self.print_table()
        elif chosen_btn == page_btn:
            self.print_page()

    def print_table(self):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPrinter.A4)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Active Cattle Table")
        if dialog.exec_() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            page_rect = printer.pageRect()
            widget_rect = self.table_view.rect()

            x_scale = page_rect.width() / widget_rect.width()
            y_scale = page_rect.height() / widget_rect.height()
            scale = min(x_scale, y_scale)

            painter.translate(page_rect.x(), page_rect.y())
            painter.scale(scale, scale)
            self.table_view.render(painter)
            painter.end()

    def print_page(self):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPrinter.A4)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Active Cattle Page")
        if dialog.exec_() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            page_rect = printer.pageRect()
            widget_rect = self.rect()

            x_scale = page_rect.width() / widget_rect.width()
            y_scale = page_rect.height() / widget_rect.height()
            scale = min(x_scale, y_scale)

            painter.translate(page_rect.x(), page_rect.y())
            painter.scale(scale, scale)
            self.render(painter)
            painter.end()

    def load_data_with_status_check(self):
        # Perform status check and update if required
        status_updates = self.check_and_update_cattle_status()
        if status_updates:
            # Write a .json file to the upload queue and call the merge script
            ts = int(time.time())
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR)
            log_path = os.path.join(UPLOAD_DIR, f"{ts}_status_update_log.json")
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    json.dump(status_updates, f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write status update log:\n{e}")
                return
            # Call the merge script
            try:
                result = subprocess.run(
                    ["python", MERGE_SCRIPT_PATH],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode != 0:
                    QMessageBox.warning(self, "Merge Failed", f"Merge script failed:\n{result.stderr}")
                else:
                    merge_msg = result.stdout if result.stdout else "Merge finished."
                    QMessageBox.information(self, "Status Synced", f"{len(status_updates)} animal(s) set to Inactive. Merge complete.\n{merge_msg}")
            except Exception as e:
                QMessageBox.critical(self, "Merge Error", f"Failed to run merge:\n{e}")
        self.load_data()

    def check_and_update_cattle_status(self):
        """
        For all cattle with exit_date set:
          - Set status to INACTIVE if exit_date <= now
          - Set status to ACTIVE if exit_date > now or not set
        Write a .json file to the upload queue and call the merge script if any status would change.
        """
        now_ts = int(time.time())
        updates = []
        if not os.path.exists(CORE_DB_PATH):
            return []

        conn = sqlite3.connect(CORE_DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT nlis_id, nlis_rfid, exit_date, status FROM cattle_registry
            WHERE exit_date IS NOT NULL AND exit_date != ''
        """)
        animals = cur.fetchall()
        conn.close()

        for nlis_id, nlis_rfid, exit_date, current_status in animals:
            try:
                exit_ts = int(exit_date)
                if exit_ts <= now_ts:
                    new_status = "INACTIVE"
                else:
                    new_status = "ACTIVE"
                # Only prepare update if status would change
                if current_status.upper() != new_status:
                    updates.append({
                        "nlis_id": nlis_id,
                        "nlis_rfid": nlis_rfid,
                        "status": new_status,
                        "last_updated": now_ts
                    })
            except Exception:
                continue

        if updates:
            # Write a .json file to the upload queue and call the merge script
            ts = int(time.time())
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR)
            log_path = os.path.join(UPLOAD_DIR, f"{ts}_status_update_log.json")
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    json.dump(updates, f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write status update log:\n{e}")
                return
            # Call the merge script
            try:
                result = subprocess.run(
                    ["python", MERGE_SCRIPT_PATH],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode != 0:
                    QMessageBox.warning(self, "Merge Failed", f"Merge script failed:\n{result.stderr}")
                else:
                    merge_msg = result.stdout if result.stdout else "Merge finished."
                    QMessageBox.information(self, "Status Synced", f"{len(updates)} animal(s) status updated. Merge complete.\n{merge_msg}")
            except Exception as e:
                QMessageBox.critical(self, "Merge Error", f"Failed to run merge:\n{e}")
        return updates

    def load_data(self):
        for i in reversed(range(self.mob_layout.count())):
            widget = self.mob_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        for i in reversed(range(self.summary_layout.count())):
            widget = self.summary_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        if not os.path.exists(CORE_DB_PATH):
            self.summary_group.setTitle("Database not found.")
            return

        conn = sqlite3.connect(CORE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                entry_date, nlis_id, nlis_rfid, breed_description,
                sex, mob, purchase_price, animal_value
            FROM cattle_registry
            WHERE LOWER(status) = 'active'
        """)

        rows = cursor.fetchall()
        conn.close()

        total = len(rows)
        males = females = 0
        adults = calves = 0
        adult_males = adult_females = 0
        calf_males = calf_females = 0
        mob_stats = {}

        self.table_data = []
        for row in rows:
            entry_date_unix = row[0]
            entry_date_dt = datetime.datetime.fromtimestamp(entry_date_unix)
            purchase_price = row[6] if row[6] else 0.0
            animal_value = row[7] if row[7] else 0.0
            total_value = purchase_price + animal_value

            age_days = (datetime.datetime.now() - entry_date_dt).days
            age_months = age_days // 30
            years = age_months // 12
            months = age_months % 12
            age_str = f"{months}M {years}Y"
            total_age_months = age_months

            sex = (row[4] or "").upper()
            if sex == 'M':
                males += 1
            elif sex == 'F':
                females += 1

            if age_months > 3:
                adults += 1
                if sex == 'M':
                    adult_males += 1
                elif sex == 'F':
                    adult_females += 1
            else:
                calves += 1
                if sex == 'M':
                    calf_males += 1
                elif sex == 'F':
                    calf_females += 1

            mob = (row[5] or "UNKNOWN").upper()
            if mob not in mob_stats:
                mob_stats[mob] = {"total": 0, "M": 0, "F": 0, "value": 0.0}
            mob_stats[mob]["total"] += 1
            mob_stats[mob][sex] += 1
            mob_stats[mob]["value"] += total_value

            entry_date_str = entry_date_dt.strftime("%d/%m/%Y")
            safe_sale_dt = entry_date_dt + datetime.timedelta(days=90)
            safe_sale_str = safe_sale_dt.strftime("%d/%m/%Y")

            self.table_data.append([
                (entry_date_dt, entry_date_str),
                (row[1] or "").upper(),
                str(row[2]) if row[2] is not None else "",
                (row[3] or "").upper(),
                sex,
                mob,
                f"${total_value:.2f}",            # <-- Total Value (purchase_price + animal_value)
                (total_age_months, age_str),
                (safe_sale_dt, safe_sale_str)
            ])

        self.model = CattleTableModel(self.table_data, self.table_headers)
        self.proxy_model.setSourceModel(self.model)
        self.table_view.setModel(self.proxy_model)
        
        header = self.table_view.horizontalHeader()
        for col in range(self.model.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        QApplication.processEvents()
        for col in range(self.model.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        
        def bold(text):
            return f"<b>{text}</b>"

        self.cattle_summary_rows = []
        self.summary_layout.addWidget(QLabel(bold("Type")), 0, 0, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(bold("Total")), 0, 1, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(bold("Males")), 0, 2, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(bold("Females")), 0, 3, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel("Active Cattle"), 1, 0, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(total)), 1, 1, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(males)), 1, 2, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(females)), 1, 3, alignment=Qt.AlignCenter)
        self.cattle_summary_rows.append(["Active Cattle", total, males, females])
        self.summary_layout.addWidget(QLabel("Adult Cattle"), 2, 0, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(adults)), 2, 1, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(adult_males)), 2, 2, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(adult_females)), 2, 3, alignment=Qt.AlignCenter)
        self.cattle_summary_rows.append(["Adult Cattle", adults, adult_males, adult_females])
        self.summary_layout.addWidget(QLabel("Calves"), 3, 0, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(calves)), 3, 1, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(calf_males)), 3, 2, alignment=Qt.AlignCenter)
        self.summary_layout.addWidget(QLabel(str(calf_females)), 3, 3, alignment=Qt.AlignCenter)
        self.cattle_summary_rows.append(["Calves", calves, calf_males, calf_females])

        self.mob_summary_rows = []
        self.mob_layout.addWidget(QLabel(bold("Mob")), 0, 0, alignment=Qt.AlignCenter)
        self.mob_layout.addWidget(QLabel(bold("Total")), 0, 1, alignment=Qt.AlignCenter)
        self.mob_layout.addWidget(QLabel(bold("Males")), 0, 2, alignment=Qt.AlignCenter)
        self.mob_layout.addWidget(QLabel(bold("Females")), 0, 3, alignment=Qt.AlignCenter)
        self.mob_layout.addWidget(QLabel(bold("Total Value")), 0, 4, alignment=Qt.AlignCenter)
        mob_row = 1
        for mob, stats in sorted(mob_stats.items()):
            self.mob_layout.addWidget(QLabel(mob), mob_row, 0, alignment=Qt.AlignCenter)
            self.mob_layout.addWidget(QLabel(str(stats['total'])), mob_row, 1, alignment=Qt.AlignCenter)
            self.mob_layout.addWidget(QLabel(str(stats['M'])), mob_row, 2, alignment=Qt.AlignCenter)
            self.mob_layout.addWidget(QLabel(str(stats['F'])), mob_row, 3, alignment=Qt.AlignCenter)
            self.mob_layout.addWidget(QLabel(f"${stats['value']:.2f}"), mob_row, 4, alignment=Qt.AlignCenter)
            self.mob_summary_rows.append([mob, stats['total'], stats['M'], stats['F'], f"{stats['value']:.2f}"])

            mob_row += 1