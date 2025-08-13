import os
import json
import time
import sqlite3
import subprocess
import csv

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtGui import QPainter, QPageLayout, QPageSize

DATA_DIR = r"C:\ProgramData\StockLOG"
DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

class FeedDialog(QDialog):
    def __init__(self, columns, prev_commodities=None, prev_feed_types=None, last_entry_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add/Edit Feed Product")
        self.values = {}
        layout = QFormLayout(self)
        self.widgets = {}

        self.prev_commodities = [str(c) for c in (prev_commodities or [])]
        self.prev_feed_types = [str(f) for f in (prev_feed_types or [])]
        self.last_entry_data = {str(k): {kk: str(vv) for kk, vv in v.items()} for k, v in (last_entry_data or {}).items()}

        # Commodity dropdown, prefill on select
        self.commodity_combo = QComboBox()
        self.commodity_combo.setEditable(True)
        self.commodity_combo.setInsertPolicy(QComboBox.NoInsert)
        self.commodity_combo.addItems([""] + self.prev_commodities)
        self.commodity_combo.lineEdit().textChanged.connect(self._force_uppercase_commodity)
        self.commodity_combo.currentTextChanged.connect(self.prefill_for_selected_commodity)
        layout.addRow("Commodity", self.commodity_combo)
        self.widgets["commodity"] = self.commodity_combo

        # Feed type dropdown from previous entries
        self.feed_type_combo = QComboBox()
        self.feed_type_combo.setEditable(True)
        self.feed_type_combo.addItems([""] + self.prev_feed_types)
        self.feed_type_combo.lineEdit().textChanged.connect(self._force_uppercase_feedtype)
        layout.addRow("Feed Type", self.feed_type_combo)
        self.widgets["feed_type"] = self.feed_type_combo

        # Unit qty
        self.unit_qty_field = QLineEdit()
        self.unit_qty_field.setPlaceholderText("Whole number")
        layout.addRow("Unit Qty", self.unit_qty_field)
        self.widgets["unit_qty"] = self.unit_qty_field

        # Kg per unit
        self.kg_per_unit_field = QLineEdit()
        self.kg_per_unit_field.setPlaceholderText("e.g. 20")
        layout.addRow("Kg per Unit", self.kg_per_unit_field)
        self.widgets["kg_per_unit"] = self.kg_per_unit_field

        # $ per unit
        self.price_per_unit_field = QLineEdit()
        self.price_per_unit_field.setPlaceholderText("e.g. 150")
        layout.addRow("$ per Unit", self.price_per_unit_field)
        self.widgets["price_per_unit"] = self.price_per_unit_field

        # Calculated fields (read only, shown as info)
        self.info_total_kg = QLabel("Total Kg: -")
        self.info_price_per_kg = QLabel("$/Kg: -")
        self.info_total_value = QLabel("Total Feed Value $: -")
        layout.addRow(self.info_total_kg)
        layout.addRow(self.info_price_per_kg)
        layout.addRow(self.info_total_value)

        # Connect fields for live calculation
        self.unit_qty_field.textChanged.connect(self._update_calculated_fields)
        self.kg_per_unit_field.textChanged.connect(self._update_calculated_fields)
        self.price_per_unit_field.textChanged.connect(self._update_calculated_fields)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._ok_clicked)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

        self.setLayout(layout)

        # Prefill with last entry if available
        if self.last_entry_data:
            for k, w in self.widgets.items():
                if k in self.last_entry_data and isinstance(w, QLineEdit):
                    w.setText(self.last_entry_data[k])
            if "feed_type" in self.last_entry_data:
                self.feed_type_combo.setCurrentText(self.last_entry_data["feed_type"])

    def _force_uppercase_commodity(self, text):
        if text != text.upper():
            self.commodity_combo.blockSignals(True)
            self.commodity_combo.setEditText(text.upper())
            self.commodity_combo.blockSignals(False)

    def _force_uppercase_feedtype(self, text):
        if text != text.upper():
            cursor = self.feed_type_combo.lineEdit().cursorPosition()
            self.feed_type_combo.blockSignals(True)
            self.feed_type_combo.setEditText(text.upper())
            self.feed_type_combo.lineEdit().setCursorPosition(cursor)
            self.feed_type_combo.blockSignals(False)

    def prefill_for_selected_commodity(self, text):
        txt = str(text).upper()
        if txt in self.last_entry_data:
            data = self.last_entry_data[txt]
            for k, w in self.widgets.items():
                if k in data and isinstance(w, QLineEdit):
                    w.setText(data[k])
            if "feed_type" in data:
                self.feed_type_combo.setCurrentText(data.get("feed_type", ""))
        self._update_calculated_fields()  # update info fields

    def _update_calculated_fields(self):
        try:
            unit_qty = float(self.unit_qty_field.text())
            kg_per_unit = float(self.kg_per_unit_field.text())
            price_per_unit = float(self.price_per_unit_field.text())
            total_kg = unit_qty * kg_per_unit
            feed_price_per_kg = price_per_unit / kg_per_unit if kg_per_unit else 0
            total_feed_value = unit_qty * price_per_unit
        except Exception:
            total_kg = feed_price_per_kg = total_feed_value = 0

        self.info_total_kg.setText(f"Total Kg: {total_kg:.2f}")
        self.info_price_per_kg.setText(f"$/Kg: ${feed_price_per_kg:,.2f}")
        self.info_total_value.setText(f"Total Feed Value $: ${total_feed_value:,.2f}")

    def _ok_clicked(self):
        # Check for empty fields
        for key, w in self.widgets.items():
            if isinstance(w, QLineEdit):
                if not w.text().strip():
                    QMessageBox.warning(self, "Missing Field", f"{key.replace('_',' ').title()} is required.")
                    return
            elif isinstance(w, QComboBox):
                if not w.currentText().strip():
                    QMessageBox.warning(self, "Missing Field", f"{key.replace('_',' ').title()} is required.")
                    return
        if not self.unit_qty_field.text().strip() or not self.kg_per_unit_field.text().strip() or not self.price_per_unit_field.text().strip():
            QMessageBox.warning(self, "Missing Field", "Unit Qty, Kg per Unit and $ per Unit are required.")
            return
        self.accept()

    def get_final_values(self):
        # Always uppercase strings for commodity and feed_type
        out = {
            "commodity": str(self.commodity_combo.currentText().strip()).upper(),
            "feed_type": str(self.feed_type_combo.currentText().strip()).upper(),
        }
        try:
            out["unit_qty"] = float(self.unit_qty_field.text())
        except Exception:
            out["unit_qty"] = 0
        try:
            out["kg_per_unit"] = float(self.kg_per_unit_field.text())
        except Exception:
            out["kg_per_unit"] = 0
        try:
            out["price_per_unit"] = float(self.price_per_unit_field.text())
        except Exception:
            out["price_per_unit"] = 0

        # Calculated
        out["total_kg"] = out["unit_qty"] * out["kg_per_unit"]
        out["feed_price_per_kg"] = out["price_per_unit"] / out["kg_per_unit"] if out["kg_per_unit"] else 0
        out["total_feed_value"] = out["unit_qty"] * out["price_per_unit"]
        return out

class RemoveFeedDialog(QDialog):
    def __init__(self, commodities, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remove Feed Commodity")
        layout = QFormLayout(self)
        self.commodity_combo = QComboBox()
        self.commodity_combo.addItems([str(c) for c in commodities])
        layout.addRow("Commodity to Remove", self.commodity_combo)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        self.setLayout(layout)

    def get_selected_commodity(self):
        return str(self.commodity_combo.currentText().strip()).upper()

class FeedAndSuppliesPage(QWidget):
    FEED_COLUMNS = [
        "commodity", "feed_type", "unit_qty", "kg_per_unit", "price_per_unit",
        "total_kg", "feed_price_per_kg", "total_feed_value"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()

        feed_header = QLabel("Feed & Milk Powder Stock")
        feed_header.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 12px;")
        layout.addWidget(feed_header)

        # Main Table (autosize, sortable, zebra)
        self.feed_table = QTableWidget(0, len(self.FEED_COLUMNS))
        self.feed_table.setHorizontalHeaderLabels([
            "Commodity", "Feed Type", "Unit Qty", "Kg/Unit", "$/Unit",
            "Total Kg", "$/Kg", "Total Feed Value $"
        ])
        self.feed_table.setAlternatingRowColors(True)
        self.feed_table.setSortingEnabled(False)
        layout.addWidget(self.feed_table)

        btn_row = QHBoxLayout()
        self.add_feed_btn = QPushButton("Add/Edit")
        self.remove_feed_btn = QPushButton("Remove")
        self.refresh_btn = QPushButton("Refresh")
        self.export_btn = QPushButton("Export Table")
        self.print_btn = QPushButton("Print Table")

        self.add_feed_btn.clicked.connect(self.add_feed_product)
        self.remove_feed_btn.clicked.connect(self.remove_feed_product)
        self.refresh_btn.clicked.connect(self.refresh_feed_table)
        self.export_btn.clicked.connect(self.export_table_csv)
        self.print_btn.clicked.connect(self.print_table)

        btn_row.addWidget(self.add_feed_btn)
        btn_row.addWidget(self.remove_feed_btn)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.print_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.setLayout(layout)
        self.refresh_feed_table()

    def _get_previous_commodities_and_feed_types(self):
        commodities = []
        feed_types = []
        last_entry_data = {}
        if not os.path.exists(DB_PATH):
            return commodities, feed_types, last_entry_data
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(f"SELECT commodity, feed_type, unit_qty, kg_per_unit, price_per_unit FROM feed_stock ORDER BY id DESC")
        rows = cur.fetchall()
        seen_commodities = set()
        seen_feed_types = set()
        for row in rows:
            c = str(row[0] if row[0] is not None else "").upper()
            f = str(row[1] if row[1] is not None else "").upper()
            unit_qty = str(row[2]) if row[2] is not None else ""
            kg_per_unit = str(row[3]) if row[3] is not None else ""
            price_per_unit = str(row[4]) if row[4] is not None else ""
            if c and c not in seen_commodities:
                commodities.append(c)
                last_entry_data[c] = {
                    "commodity": c,
                    "feed_type": f,
                    "unit_qty": unit_qty,
                    "kg_per_unit": kg_per_unit,
                    "price_per_unit": price_per_unit
                }
                seen_commodities.add(c)
            if f and f not in seen_feed_types:
                feed_types.append(f)
                seen_feed_types.add(f)
        conn.close()
        return commodities, feed_types, last_entry_data

    def refresh_feed_table(self):
        # Fetch data once
        rows = []
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(f"SELECT {', '.join(self.FEED_COLUMNS)} FROM feed_stock")
            rows = cur.fetchall()
            conn.close()

        self.feed_table.setSortingEnabled(False)
        self.feed_table.setRowCount(0)
        for row in rows:
            row_num = self.feed_table.rowCount()
            self.feed_table.insertRow(row_num)
            for col, val in enumerate(row):
                col_name = self.FEED_COLUMNS[col]
                # Format logic: left for commodity/feed_type, right for others
                if col_name in ["commodity", "feed_type"]:
                    alignment = Qt.AlignLeft | Qt.AlignVCenter
                else:
                    alignment = Qt.AlignRight | Qt.AlignVCenter

                # Currency columns
                if col_name == "price_per_unit":
                    try:
                        display_val = f"${float(val):,.2f}" if val is not None else ""
                    except Exception:
                        display_val = str(val) if val is not None else ""
                elif col_name == "feed_price_per_kg":
                    try:
                        display_val = f"${float(val):,.2f}" if val is not None else ""
                    except Exception:
                        display_val = str(val) if val is not None else ""
                elif col_name == "total_feed_value":
                    try:
                        display_val = f"${float(val):,.2f}" if val is not None else ""
                    except Exception:
                        display_val = str(val) if val is not None else ""
                # Unit qty, kg per unit, total kg: show decimals only if needed
                elif col_name in ["unit_qty", "kg_per_unit", "total_kg"]:
                    try:
                        fval = float(val)
                        if fval == int(fval):
                            display_val = f"{int(fval)}"
                        else:
                            display_val = f"{fval:,.2f}"
                    except Exception:
                        display_val = str(val) if val is not None else ""
                else:
                    display_val = str(val) if val is not None else ""

                item = QTableWidgetItem(display_val)
                item.setTextAlignment(alignment)
                self.feed_table.setItem(row_num, col, item)
        self.feed_table.resizeColumnsToContents()
        self.feed_table.resizeRowsToContents()
        self.feed_table.setSortingEnabled(True)

    def add_feed_product(self):
        prev_commodities, prev_feed_types, last_entry_data = self._get_previous_commodities_and_feed_types()
        dlg = FeedDialog(
            self.FEED_COLUMNS,
            prev_commodities=prev_commodities,
            prev_feed_types=prev_feed_types,
            last_entry_data=last_entry_data,
            parent=self
        )
        if dlg.exec_() == QDialog.Accepted:
            values = dlg.get_final_values()
            unix_ts = int(time.time())
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR)
            filename = f"{unix_ts}_feed_stock_entry.json"
            filepath = os.path.join(UPLOAD_DIR, filename)
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([values], f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write feed stock entry log:\n{e}")
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

            self.refresh_feed_table()

    def remove_feed_product(self):
        prev_commodities, _, _ = self._get_previous_commodities_and_feed_types()
        if not prev_commodities:
            QMessageBox.information(self, "No Commodities", "No commodities to remove.")
            return
        dlg = RemoveFeedDialog(prev_commodities, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            commodity = dlg.get_selected_commodity()
            unix_ts = int(time.time())
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR)
            filename = f"{unix_ts}_feed_stock_remove.json"
            filepath = os.path.join(UPLOAD_DIR, filename)
            removal_record = {"commodity": commodity, "remove": True}
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([removal_record], f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write feed stock remove log:\n{e}")
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

            self.refresh_feed_table()

    def export_table_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Table CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        headers = [
            "Commodity", "Feed Type", "Unit Qty", "Kg/Unit", "$/Unit",
            "Total Kg", "$/Kg", "Total Feed Value $"
        ]
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in range(self.feed_table.rowCount()):
                row_items = []
                for col in range(self.feed_table.columnCount()):
                    item = self.feed_table.item(row, col)
                    val = item.text() if item else ""
                    row_items.append(val)
                writer.writerow(row_items)

    def print_table(self):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPrinter.A4)
        # Set landscape orientation
        printer.setOrientation(QPrinter.Landscape)
        layout = QPageLayout()
        layout.setOrientation(QPageLayout.Landscape)
        printer.setPageLayout(layout)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Feed & Milk Powder Table")
        if dialog.exec_() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            page_rect = printer.pageRect()
            widget_rect = self.feed_table.rect()

            x_scale = page_rect.width() / widget_rect.width()
            y_scale = page_rect.height() / widget_rect.height()
            scale = min(x_scale, y_scale)

            painter.translate(page_rect.x(), page_rect.y())
            painter.scale(scale, scale)
            self.feed_table.render(painter)
            painter.end()

    def refresh_data(self):
        self.refresh_feed_table()