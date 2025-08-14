import os
import json
import time
import sqlite3
import subprocess
import csv
import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QPushButton, QDialog, QFormLayout, QLineEdit, QDateEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtGui import QPainter, QPageLayout

DATA_DIR = r"C:\ProgramData\StockLOG"
DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

TABLE_COLUMNS = [
    "date_received", "product_name", "form", "unit", "package_size", "package_type",
    "quantity", "total_quantity", "price_per_unit", "total_value",
    "batch_number", "expiry_date", "dom_date", "application_type", "withholding_period", "notes"
]

class ChemicalDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add/Edit Chemical Product")
        layout = QFormLayout(self)

        # Date received
        self.date_received = QDateEdit()
        self.date_received.setCalendarPopup(True)
        self.date_received.setDisplayFormat("yyyy-MM-dd")
        self.date_received.setDate(QDate.currentDate())
        layout.addRow("Date Received", self.date_received)

        # Product name
        self.product_name = QLineEdit()
        self.product_name.setPlaceholderText("Product name")
        layout.addRow("Product Name", self.product_name)

        # Form
        self.form_combo = QComboBox()
        self.form_combo.addItems(["LIQUID", "POWDER", "TABLET", "AEROSOL", "OTHER"])
        layout.addRow("Form", self.form_combo)

        # Unit
        self.unit = QLineEdit()
        self.unit.setPlaceholderText("Unit (e.g. L, mL, g, tablet, can)")
        layout.addRow("Unit", self.unit)

        # Package size
        self.package_size = QLineEdit()
        self.package_size.setPlaceholderText("Package Size (e.g. 20 for 20L)")
        layout.addRow("Package Size", self.package_size)

        # Package type
        self.package_type = QLineEdit()
        self.package_type.setPlaceholderText("Package Type (e.g. drum, vial, can, box)")
        layout.addRow("Package Type", self.package_type)

        # Quantity
        self.quantity = QLineEdit()
        self.quantity.setPlaceholderText("Number of packages")
        layout.addRow("Quantity", self.quantity)

        # Price per unit
        self.price_per_unit = QLineEdit()
        self.price_per_unit.setPlaceholderText("Price per unit (e.g. $/mL, $/tablet)")
        layout.addRow("Price per Unit", self.price_per_unit)

        # Batch number
        self.batch_number = QLineEdit()
        self.batch_number.setPlaceholderText("Batch number")
        layout.addRow("Batch Number", self.batch_number)

        # Expiry date
        self.expiry_date = QDateEdit()
        self.expiry_date.setCalendarPopup(True)
        self.expiry_date.setDisplayFormat("yyyy-MM-dd")
        self.expiry_date.setDate(QDate.currentDate())
        layout.addRow("Expiry Date", self.expiry_date)

        # Date of manufacture
        self.dom_date = QDateEdit()
        self.dom_date.setCalendarPopup(True)
        self.dom_date.setDisplayFormat("yyyy-MM-dd")
        self.dom_date.setDate(QDate.currentDate())
        layout.addRow("Date of Manufacture", self.dom_date)

        # Application type
        self.application_type = QComboBox()
        self.application_type.addItems(["INDIVIDUAL", "MOB"])
        layout.addRow("Application Type", self.application_type)

        # Withholding period
        self.withholding_period = QLineEdit()
        self.withholding_period.setPlaceholderText("Withholding period (days)")
        layout.addRow("Withholding Period (days)", self.withholding_period)

        # Notes
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Notes")
        layout.addRow("Notes", self.notes)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._ok_clicked)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

        self.setLayout(layout)

    def _ok_clicked(self):
        # Basic validation
        if not self.product_name.text().strip():
            QMessageBox.warning(self, "Missing Field", "Product name is required.")
            return
        if not self.unit.text().strip():
            QMessageBox.warning(self, "Missing Field", "Unit is required.")
            return
        if not self.package_size.text().strip():
            QMessageBox.warning(self, "Missing Field", "Package size is required.")
            return
        if not self.package_type.text().strip():
            QMessageBox.warning(self, "Missing Field", "Package type is required.")
            return
        if not self.quantity.text().strip():
            QMessageBox.warning(self, "Missing Field", "Quantity is required.")
            return
        if not self.price_per_unit.text().strip():
            QMessageBox.warning(self, "Missing Field", "Price per unit is required.")
            return
        if not self.batch_number.text().strip():
            QMessageBox.warning(self, "Missing Field", "Batch number is required.")
            return
        if not self.withholding_period.text().strip():
            QMessageBox.warning(self, "Missing Field", "Withholding period is required.")
            return
        self.accept()

    def get_final_values(self):
        # Safe conversion for all date fields
        dt_received = self.date_received.date().toPyDate()
        date_received = int(datetime.datetime(dt_received.year, dt_received.month, dt_received.day).timestamp())

        dt_expiry = self.expiry_date.date().toPyDate()
        expiry_date = int(datetime.datetime(dt_expiry.year, dt_expiry.month, dt_expiry.day).timestamp())

        dt_dom = self.dom_date.date().toPyDate()
        dom_date = int(datetime.datetime(dt_dom.year, dt_dom.month, dt_dom.day).timestamp())

        try:
            package_size = float(self.package_size.text())
        except Exception:
            package_size = 0.0
        try:
            quantity = float(self.quantity.text())
        except Exception:
            quantity = 0.0
        try:
            price_per_unit = float(self.price_per_unit.text())
        except Exception:
            price_per_unit = 0.0
        try:
            withholding_period = int(self.withholding_period.text())
        except Exception:
            withholding_period = 0
        total_quantity = package_size * quantity
        total_value = total_quantity * price_per_unit

        return {
            "date_received": date_received,
            "product_name": self.product_name.text().strip().upper(),
            "form": self.form_combo.currentText(),
            "unit": self.unit.text().strip(),
            "package_size": package_size,
            "package_type": self.package_type.text().strip(),
            "quantity": quantity,
            "total_quantity": total_quantity,
            "price_per_unit": price_per_unit,
            "total_value": total_value,
            "batch_number": self.batch_number.text().strip().upper(),
            "expiry_date": expiry_date,
            "dom_date": dom_date,
            "application_type": self.application_type.currentText(),
            "withholding_period": withholding_period,
            "notes": self.notes.text().strip(),
            "last_updated": int(time.time()),
            "created_at": int(time.time())
        }

class RemoveChemicalDialog(QDialog):
    def __init__(self, products, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remove Chemical Product")
        layout = QFormLayout(self)
        self.product_combo = QComboBox()
        self.product_combo.addItems(products)
        layout.addRow("Product to Remove", self.product_combo)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        self.setLayout(layout)

    def get_selected_product(self):
        return str(self.product_combo.currentText().strip()).upper()

class ChemInventoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()

        header = QLabel("Chemical Inventory")
        header.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 12px;")
        layout.addWidget(header)

        # Main Table
        self.chem_table = QTableWidget(0, len(TABLE_COLUMNS))
        self.chem_table.setHorizontalHeaderLabels([
            "Date Received", "Product Name", "Form", "Unit", "Package Size", "Package Type",
            "Quantity", "Total Quantity", "Price/Unit", "Total Value",
            "Batch Number", "Expiry Date", "DOM", "Application Type", "Withholding Period", "Notes"
        ])
        self.chem_table.setAlternatingRowColors(True)
        self.chem_table.setSortingEnabled(False)
        layout.addWidget(self.chem_table)

        btn_row = QHBoxLayout()
        self.add_chem_btn = QPushButton("Add/Edit")
        self.remove_chem_btn = QPushButton("Remove")
        self.refresh_btn = QPushButton("Refresh")
        self.export_btn = QPushButton("Export Table")
        self.print_btn = QPushButton("Print Table")

        self.add_chem_btn.clicked.connect(self.add_chemical_product)
        self.remove_chem_btn.clicked.connect(self.remove_chemical_product)
        self.refresh_btn.clicked.connect(self.refresh_chem_table)
        self.export_btn.clicked.connect(self.export_table_csv)
        self.print_btn.clicked.connect(self.print_table)

        btn_row.addWidget(self.add_chem_btn)
        btn_row.addWidget(self.remove_chem_btn)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.print_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.setLayout(layout)
        self.refresh_chem_table()

    def _ensure_table(self):
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chemical_inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_received INTEGER,
                    product_name TEXT,
                    form TEXT,
                    unit TEXT,
                    package_size REAL,
                    package_type TEXT,
                    quantity REAL,
                    total_quantity REAL,
                    price_per_unit REAL,
                    total_value REAL,
                    batch_number TEXT,
                    expiry_date INTEGER,
                    dom_date INTEGER,
                    application_type TEXT,
                    withholding_period INTEGER,
                    notes TEXT,
                    last_updated INTEGER,
                    created_at INTEGER
                )
            """)
            conn.commit()
            conn.close()

    def refresh_chem_table(self):
        self._ensure_table()
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT date_received, product_name, form, unit, package_size, package_type, quantity, total_quantity, price_per_unit, total_value, batch_number, expiry_date, dom_date, application_type, withholding_period, notes FROM chemical_inventory")
            rows = cur.fetchall()
            conn.close()
        else:
            rows = []

        self.chem_table.setSortingEnabled(False)
        self.chem_table.setRowCount(0)
        for row in rows:
            row_num = self.chem_table.rowCount()
            self.chem_table.insertRow(row_num)
            # Format dates and currency
            def fmt_date(ts):
                try:
                    return time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else ""
                except Exception:
                    return str(ts) if ts else ""
            def fmt_currency(val):
                try:
                    return f"${float(val):,.2f}" if val is not None else ""
                except Exception:
                    return str(val) if val is not None else ""
            values = [
                fmt_date(row[0]),                # Date received
                row[1],                          # Product name
                row[2],                          # Form
                row[3],                          # Unit
                str(row[4]),                     # Package size
                row[5],                          # Package type
                str(row[6]),                     # Quantity
                str(row[7]),                     # Total quantity
                fmt_currency(row[8]),            # Price per unit
                fmt_currency(row[9]),            # Total value
                row[10],                         # Batch number
                fmt_date(row[11]),               # Expiry date
                fmt_date(row[12]),               # DOM
                row[13],                         # Application type
                str(row[14]),                    # Withholding period
                row[15],                         # Notes
            ]
            for col, val in enumerate(values):
                alignment = Qt.AlignLeft | Qt.AlignVCenter if col in [1, 2, 5, 10, 13, 15] else Qt.AlignCenter
                item = QTableWidgetItem(val)
                item.setTextAlignment(alignment)
                self.chem_table.setItem(row_num, col, item)
        self.chem_table.resizeColumnsToContents()
        self.chem_table.resizeRowsToContents()
        self.chem_table.setSortingEnabled(True)

    def add_chemical_product(self):
        products = self._get_product_names()
        dlg = ChemicalDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            values = dlg.get_final_values()
            unix_ts = int(time.time())
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR)
            filename = f"{unix_ts}_chem_inventory_entry.json"
            filepath = os.path.join(UPLOAD_DIR, filename)
            # Write user input fields as a JSON file in the upload queue
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([values], f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write chemical inventory entry log:\n{e}")
                return
            # Call the merge script to process the new info
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
                    QMessageBox.information(self, "Merge Complete", merge_msg)
            except Exception as e:
                QMessageBox.critical(self, "Merge Error", f"Failed to run merge:\n{e}")

            self.refresh_chem_table()

    def remove_chemical_product(self):
        products = self._get_product_names()
        if not products:
            QMessageBox.information(self, "No Products", "No products to remove.")
            return
        dlg = RemoveChemicalDialog(products, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            product = dlg.get_selected_product()
            unix_ts = int(time.time())
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR)
            filename = f"{unix_ts}_chem_inventory_remove.json"
            filepath = os.path.join(UPLOAD_DIR, filename)
            removal_record = {"product_name": product, "remove": True}
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([removal_record], f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write chemical inventory remove log:\n{e}")
                return
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
                    QMessageBox.information(self, "Merge Complete", merge_msg)
            except Exception as e:
                QMessageBox.critical(self, "Merge Error", f"Failed to run merge:\n{e}")

            self.refresh_chem_table()

    def _get_product_names(self):
        self._ensure_table()
        products = []
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT product_name FROM chemical_inventory")
            rows = cur.fetchall()
            products = [str(row[0]) for row in rows if row[0]]
            conn.close()
        return products

    def export_table_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Chemical Inventory CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        headers = [
            "Date Received", "Product Name", "Form", "Unit", "Package Size", "Package Type",
            "Quantity", "Total Quantity", "Price/Unit", "Total Value",
            "Batch Number", "Expiry Date", "DOM", "Application Type", "Withholding Period", "Notes"
        ]
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in range(self.chem_table.rowCount()):
                row_items = []
                for col in range(self.chem_table.columnCount()):
                    item = self.chem_table.item(row, col)
                    val = item.text() if item else ""
                    row_items.append(val)
                writer.writerow(row_items)

    def print_table(self):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Landscape)
        layout = QPageLayout()
        layout.setOrientation(QPageLayout.Landscape)
        printer.setPageLayout(layout)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Chemical Inventory Table")
        if dialog.exec_() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            page_rect = printer.pageRect()
            widget_rect = self.chem_table.rect()

            x_scale = page_rect.width() / widget_rect.width()
            y_scale = page_rect.height() / widget_rect.height()
            scale = min(x_scale, y_scale)

            painter.translate(page_rect.x(), page_rect.y())
            painter.scale(scale, scale)
            self.chem_table.render(painter)
            painter.end()

    def refresh_data(self):
        self.refresh_chem_table()