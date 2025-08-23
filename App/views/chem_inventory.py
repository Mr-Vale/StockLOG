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

DATA_DIR = r"C:\ProgramData\StockLOG"
DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

TABLE_COLUMNS = [
    "date_received", "product_name", "form", "unit", "package_size", "package_type",
    "quantity", "total_quantity", "price_per_unit", "total_value",
    "batch_number", "expiry_date", "dom_date", "application_type", "withholding_period", "notes"
]

def force_upper(s):
    return s.upper() if isinstance(s, str) else s

def is_positive_number(s):
    try:
        val = float(s)
        return val > 0
    except Exception:
        return False

class ChemicalDialog(QDialog):
    def __init__(self, products_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add/Edit Chemical Product")
        self.products_data = products_data
        layout = QFormLayout(self)

        self.product_combo = QComboBox()
        self.product_combo.setEditable(True)
        self.product_combo.addItems([""] + [p for p in products_data])
        self.product_combo.setInsertPolicy(QComboBox.NoInsert)
        self.product_combo.currentTextChanged.connect(self.prefill_fields)
        layout.addRow("Product Name", self.product_combo)

        self.form_combo = QComboBox()
        self.form_combo.addItems(["LIQUID", "POWDER", "TABLET", "AEROSOL"])
        self.form_combo.currentTextChanged.connect(self.update_unit_and_package)
        layout.addRow("Form", self.form_combo)

        self.unit_combo = QComboBox()
        layout.addRow("Unit", self.unit_combo)

        self.package_type_combo = QComboBox()
        layout.addRow("Package Type", self.package_type_combo)

        self.package_size = QLineEdit()
        self.package_size.setPlaceholderText("Size per package")
        layout.addRow("Package Size", self.package_size)

        self.quantity = QLineEdit()
        self.quantity.setPlaceholderText("Number of packages/tablets/cans")
        layout.addRow("Quantity", self.quantity)

        self.batch_number = QLineEdit()
        layout.addRow("Batch Number", self.batch_number)

        self.price_per_package = QLineEdit()
        self.price_per_package.setPlaceholderText("Price per package")
        layout.addRow("Price per Package", self.price_per_package)

        self.price_per_unit_display = QLabel("-")
        layout.addRow("Calculated Price per Unit", self.price_per_unit_display)

        self.expiry_date = QDateEdit()
        self.expiry_date.setCalendarPopup(True)
        self.expiry_date.setDate(QDate.currentDate())
        layout.addRow("Expiry Date", self.expiry_date)

        self.dom_date = QDateEdit()
        self.dom_date.setCalendarPopup(True)
        self.dom_date.setDate(QDate.currentDate())
        layout.addRow("Date of Manufacture", self.dom_date)

        self.application_type = QComboBox()
        self.application_type.addItems(["INDIVIDUAL", "MOB"])
        layout.addRow("Application Type", self.application_type)

        self.withholding_period = QLineEdit()
        self.withholding_period.setPlaceholderText("Withholding period (days)")
        layout.addRow("Withholding Period (days)", self.withholding_period)

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Notes")
        layout.addRow("Notes", self.notes)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._ok_clicked)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        self.setLayout(layout)

        self.update_unit_and_package()

        # Force uppercase on all QLineEdit fields
        for field in [self.batch_number, self.package_size, self.quantity, self.price_per_package, self.withholding_period, self.notes]:
            field.textChanged.connect(lambda text, fld=field: fld.setText(force_upper(text)))

    def prefill_fields(self, name):
        name = force_upper(name)
        if name in self.products_data:
            d = self.products_data[name]
            self.form_combo.setCurrentText(force_upper(d['form']))
            self.update_unit_and_package()
            self.unit_combo.setCurrentText(force_upper(d['unit']))
            self.package_type_combo.setCurrentText(force_upper(d['package_type']))
            # Liquid: convert package_size to ml for UI if needed
            if force_upper(d['form']) == "LIQUID" and force_upper(d['unit']) == "ML":
                self.package_size.setText(str(float(d['package_size']) * 1000))
            else:
                self.package_size.setText(str(float(d['package_size'])))
            # Powder: convert package_size to g for UI if needed
            if force_upper(d['form']) == "POWDER" and force_upper(d['unit']) == "G":
                self.package_size.setText(str(float(d['package_size']) * 1000))
            self.quantity.setText(str(float(d['quantity'])))
            self.batch_number.setText(force_upper(d['batch_number']))
            self.price_per_package.setText(str(float(d['total_value'])))
            try:
                expiry_dt = datetime.datetime.fromtimestamp(float(d['expiry_date']))
                self.expiry_date.setDate(QDate(expiry_dt.year, expiry_dt.month, expiry_dt.day))
            except Exception:
                self.expiry_date.setDate(QDate.currentDate())
            try:
                dom_dt = datetime.datetime.fromtimestamp(float(d['dom_date']))
                self.dom_date.setDate(QDate(dom_dt.year, dom_dt.month, dom_dt.day))
            except Exception:
                self.dom_date.setDate(QDate.currentDate())
            self.application_type.setCurrentText(force_upper(d['application_type']))
            self.withholding_period.setText(str(float(d['withholding_period'])))
            self.notes.setText(force_upper(d['notes']))
            self.update_price_per_unit()
        else:
            self.clear_fields()

    def clear_fields(self):
        self.form_combo.setCurrentIndex(0)
        self.unit_combo.setCurrentIndex(0)
        self.package_type_combo.setCurrentIndex(0)
        self.package_size.clear()
        self.quantity.clear()
        self.batch_number.clear()
        self.price_per_package.clear()
        self.expiry_date.setDate(QDate.currentDate())
        self.dom_date.setDate(QDate.currentDate())
        self.application_type.setCurrentIndex(0)
        self.withholding_period.clear()
        self.notes.clear()
        self.price_per_unit_display.setText("-")

    def update_unit_and_package(self):
        form = self.form_combo.currentText()
        self.unit_combo.clear()
        self.package_type_combo.clear()
        self.package_size.setEnabled(True)
        if form == "LIQUID":
            self.unit_combo.addItems(["ml", "L"])
            self.package_type_combo.addItems(["DRUM", "BOTTLE", "VIAL"])
        elif form == "POWDER":
            self.unit_combo.addItems(["g", "Kg"])
            self.package_type_combo.addItems(["BAG", "BOX", "BOTTLE"])
        elif form == "TABLET":
            self.unit_combo.addItem("Tablet")
            self.package_type_combo.addItems(["BOX", "BOTTLE"])
        elif form == "AEROSOL":
            self.unit_combo.addItem("ml")
            self.package_type_combo.addItems(["CAN", "BOX"])
        self.update_price_per_unit()

    def update_price_per_unit(self):
        try:
            form = self.form_combo.currentText()
            unit = self.unit_combo.currentText()
            package_type = self.package_type_combo.currentText()
            price_per_package = float(self.price_per_package.text()) if is_positive_number(self.price_per_package.text()) else 0.0
            package_size = float(self.package_size.text()) if is_positive_number(self.package_size.text()) else 0.0
            quantity = float(self.quantity.text()) if is_positive_number(self.quantity.text()) else 0.0
            if form == "AEROSOL" and package_type == "CAN":
                package_size = 1.0
            if form == "LIQUID":
                package_size_l = package_size / 1000.0 if unit == "ml" else package_size
                total_l = package_size_l * quantity
                if unit == "ml":
                    price_per_unit = price_per_package / (total_l * 1000) if total_l > 0 else 0
                    self.price_per_unit_display.setText(f"${price_per_unit:.2f} per ml")
                else:
                    price_per_unit = price_per_package / total_l if total_l > 0 else 0
                    self.price_per_unit_display.setText(f"${price_per_unit:.2f} per L")
            elif form == "POWDER":
                package_size_kg = package_size / 1000.0 if unit == "g" else package_size
                total_kg = package_size_kg * quantity
                if unit == "g":
                    price_per_unit = price_per_package / (total_kg * 1000) if total_kg > 0 else 0
                    self.price_per_unit_display.setText(f"${price_per_unit:.2f} per g")
                else:
                    price_per_unit = price_per_package / total_kg if total_kg > 0 else 0
                    self.price_per_unit_display.setText(f"${price_per_unit:.2f} per Kg")
            elif form == "TABLET":
                total_tablets = package_size * quantity
                price_per_unit = price_per_package / total_tablets if total_tablets > 0 else 0
                self.price_per_unit_display.setText(f"${price_per_unit:.2f} per Tablet")
            elif form == "AEROSOL":
                package_size_l = package_size / 1000.0
                total_l = package_size_l * quantity
                price_per_unit = price_per_package / (total_l * 1000) if total_l > 0 else 0
                self.price_per_unit_display.setText(f"${price_per_unit:.2f} per ml (stored as L)")
        except Exception:
            self.price_per_unit_display.setText("-")

    def _ok_clicked(self):
        errors = []
        if not self.product_combo.currentText().strip():
            errors.append("Product name is required.")
        if not self.batch_number.text().strip():
            errors.append("Batch number is required.")
        if not is_positive_number(self.package_size.text()):
            errors.append("Package size must be a positive number.")
        if not is_positive_number(self.quantity.text()):
            errors.append("Quantity must be a positive number.")
        if not is_positive_number(self.price_per_package.text()):
            errors.append("Price per package must be a positive number.")
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
        self.accept()

    def get_final_values(self):
        form = self.form_combo.currentText()
        unit = self.unit_combo.currentText()
        package_type = self.package_type_combo.currentText()
        price_per_package = float(self.price_per_package.text()) if is_positive_number(self.price_per_package.text()) else 0.0
        package_size = float(self.package_size.text()) if is_positive_number(self.package_size.text()) else 0.0
        quantity = float(self.quantity.text()) if is_positive_number(self.quantity.text()) else 0.0
        if form == "AEROSOL" and package_type == "CAN":
            package_size = 1.0
        product_name = force_upper(self.product_combo.currentText())
        batch_number = force_upper(self.batch_number.text())
        notes = force_upper(self.notes.text())
        withholding_period = float(self.withholding_period.text()) if is_positive_number(self.withholding_period.text()) else 0.0
        expiry_date = self.expiry_date.date().toPyDate()
        expiry_date_int = int(datetime.datetime(expiry_date.year, expiry_date.month, expiry_date.day).timestamp())
        dom_date = self.dom_date.date().toPyDate()
        dom_date_int = int(datetime.datetime(dom_date.year, dom_date.month, dom_date.day).timestamp())
        if form == "LIQUID":
            if unit == "ml":
                package_size_db = package_size / 1000.0
            else:
                package_size_db = package_size
            total_quantity = package_size_db * quantity
            price_per_unit = price_per_package / (total_quantity * 1000) if unit == "ml" and total_quantity > 0 else price_per_package / total_quantity if total_quantity > 0 else 0.0
            unit_db = unit
        elif form == "POWDER":
            if unit == "g":
                package_size_kg = package_size / 1000.0
            else:
                package_size_kg = package_size
            total_quantity = package_size_kg * quantity
            price_per_unit = price_per_package / (total_quantity * 1000) if unit == "g" and total_quantity > 0 else price_per_package / total_quantity if total_quantity > 0 else 0.0
            unit_db = unit
            package_size_db = package_size_kg
        elif form == "TABLET":
            total_quantity = package_size * quantity
            price_per_unit = price_per_package / total_quantity if total_quantity > 0 else 0.0
            unit_db = unit
            package_size_db = package_size
        elif form == "AEROSOL":
            package_size_l = package_size / 1000.0
            total_quantity = package_size_l * quantity
            price_per_unit = price_per_package / (total_quantity * 1000) if total_quantity > 0 else 0.0
            unit_db = unit
            package_size_db = package_size_l
        return {
            "date_received": int(time.time()),
            "product_name": product_name,
            "form": form,
            "unit": unit_db,
            "package_size": package_size_db,
            "package_type": package_type,
            "quantity": quantity,
            "total_quantity": total_quantity,
            "price_per_unit": price_per_unit,
            "total_value": price_per_package,
            "batch_number": batch_number,
            "expiry_date": expiry_date_int,
            "dom_date": dom_date_int,
            "application_type": self.application_type.currentText(),
            "withholding_period": withholding_period,
            "notes": notes,
            "last_updated": int(time.time()),
            "created_at": int(time.time())
        }

class RemoveChemicalDialog(QDialog):
    def __init__(self, products, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remove Chemical Product")
        layout = QFormLayout(self)
        self.product_combo = QComboBox()
        self.product_combo.addItems([force_upper(p) for p in products])
        layout.addRow("Product to Remove", self.product_combo)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        self.setLayout(layout)

    def get_selected_product(self):
        return force_upper(self.product_combo.currentText().strip())

class ChemInventoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()

        header = QLabel("Chemical Inventory")
        header.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 12px;")
        layout.addWidget(header)

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
                    withholding_period REAL,
                    notes TEXT,
                    last_updated INTEGER,
                    created_at INTEGER
                )
            """)
            conn.commit()
            conn.close()

    def get_all_products_data(self):
        self._ensure_table()
        products = {}
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                "SELECT product_name, form, unit, package_size, package_type, quantity, total_quantity, price_per_unit, total_value, batch_number, expiry_date, dom_date, application_type, withholding_period, notes FROM chemical_inventory"
            )
            for row in cur.fetchall():
                products[force_upper(row[0])] = {
                    "product_name": force_upper(row[0]),
                    "form": row[1],
                    "unit": row[2],
                    "package_size": float(row[3]) if row[3] is not None else 0.0,
                    "package_type": row[4],
                    "quantity": float(row[5]) if row[5] is not None else 0.0,
                    "total_quantity": float(row[6]) if row[6] is not None else 0.0,
                    "price_per_unit": float(row[7]) if row[7] is not None else 0.0,
                    "total_value": float(row[8]) if row[8] is not None else 0.0,
                    "batch_number": force_upper(row[9]),
                    "expiry_date": float(row[10]) if row[10] is not None else 0.0,
                    "dom_date": float(row[11]) if row[11] is not None else 0.0,
                    "application_type": row[12],
                    "withholding_period": float(row[13]) if row[13] is not None else 0.0,
                    "notes": force_upper(row[14]) if row[14] else "",
                }
            conn.close()
        return products

    def display_value_with_unit(self, value, unit, for_form, value_type):
        # value_type: "size", "total", "price"
        if for_form == "LIQUID":
            if value_type == "total":
                return f"{value:.2f} L"
            elif value_type == "price":
                if force_upper(unit) == "ML":
                    return f"${value:.2f} /ml"
                else:
                    return f"${value:.2f} /L"
            else:
                if force_upper(unit) == "ML":
                    return f"{value * 1000:.2f} ml"
                else:
                    return f"{value:.2f} L"
        elif for_form == "POWDER":
            if value_type == "total":
                return f"{value:.2f} Kg"
            elif value_type == "price":
                if force_upper(unit) == "G":
                    return f"${value:.2f} /g"
                else:
                    return f"${value:.2f} /Kg"
            else:
                if force_upper(unit) == "G":
                    return f"{value * 1000:.2f} g"
                else:
                    return f"{value:.2f} Kg"
        elif for_form == "TABLET":
            if value_type == "total":
                return f"{value:.0f} Tablets"
            elif value_type == "price":
                return f"${value:.2f} /Tablet"
            else:
                return f"{value:.0f} Tablets"
        elif for_form == "AEROSOL":
            if value_type == "total":
                return f"{value:.2f} L"
            elif value_type == "price":
                return f"${value:.2f} /ml"
            else:
                return f"{value * 1000:.2f} ml"
        else:
            return f"{value:.2f}"

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
            (
                date_received, product_name, form, unit, package_size, package_type, quantity,
                total_quantity, price_per_unit, total_value, batch_number, expiry_date,
                dom_date, application_type, withholding_period, notes
            ) = row
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

            disp_package_size = self.display_value_with_unit(package_size, unit, form, "size")
            disp_total_quantity = self.display_value_with_unit(total_quantity, unit, form, "total")
            disp_price_per_unit = self.display_value_with_unit(price_per_unit, unit, form, "price")
            disp_quantity = f"{float(quantity):.2f}"
            disp_withholding = f"{float(withholding_period):.2f}"

            values = [
                fmt_date(date_received),
                force_upper(product_name),
                form,
                unit,
                disp_package_size,
                package_type,
                disp_quantity,
                disp_total_quantity,
                disp_price_per_unit,
                fmt_currency(total_value),
                force_upper(batch_number),
                fmt_date(expiry_date),
                fmt_date(dom_date),
                application_type,
                disp_withholding,
                force_upper(notes) if notes else ""
            ]
            for col, val in enumerate(values):
                if col in [8, 9]:  # price per unit, total value: right
                    alignment = Qt.AlignRight | Qt.AlignVCenter
                elif col == 10:    # batch number: center
                    alignment = Qt.AlignCenter | Qt.AlignVCenter
                elif col in [1, 2, 5, 13, 15]:
                    alignment = Qt.AlignLeft | Qt.AlignVCenter
                else:
                    alignment = Qt.AlignCenter | Qt.AlignVCenter
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(alignment)
                self.chem_table.setItem(row_num, col, item)
        self.chem_table.resizeColumnsToContents()
        self.chem_table.resizeRowsToContents()
        self.chem_table.setSortingEnabled(True)

    def add_chemical_product(self):
        products_data = self.get_all_products_data()
        dlg = ChemicalDialog(products_data, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            values = dlg.get_final_values()
            unix_ts = int(time.time())
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR)
            filename = f"{unix_ts}_chem_inventory_entry.json"
            filepath = os.path.join(UPLOAD_DIR, filename)
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([values], f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write chemical inventory entry log:\n{e}")
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

    def remove_chemical_product(self):
        products = list(self.get_all_products_data().keys())
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
        from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt5.QtGui import QPainter, QPageLayout
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