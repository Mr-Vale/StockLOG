import os
import json
import time
import sqlite3
import subprocess
import csv
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QDateEdit, QHBoxLayout,
    QFileDialog, QDialog, QDialogButtonBox, QGridLayout
)
from PyQt5.QtCore import QDate, Qt

DATA_DIR = r"C:\ProgramData\StockLOG"
DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

class BulkExitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Exit Upload")

        layout = QGridLayout(self)

        self.csv_label = QLabel("CSV file with NLIS RFID numbers:")
        self.csv_path_input = QLineEdit()
        self.csv_path_input.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")

        self.exit_date_label = QLabel("Group Exit Date*:")
        self.exit_date_input = QDateEdit()
        self.exit_date_input.setDisplayFormat("yyyy-MM-dd")
        self.exit_date_input.setCalendarPopup(True)
        self.exit_date_input.setDate(QDate.currentDate())
        self.exit_date_input.setFixedWidth(200)
        if self.exit_date_input.lineEdit() is not None:
            self.exit_date_input.lineEdit().textChanged.connect(
                lambda text: self.exit_date_input.lineEdit().setText(text.upper())
            )

        self.destination_label = QLabel("Group Destination*:")
        self.destination_input = QLineEdit()
        self.destination_input.textChanged.connect(lambda text: self.destination_input.setText(text.upper()))

        self.nvd_label = QLabel("Group NVD OUT Number:")
        self.nvd_input = QLineEdit()
        self.nvd_input.textChanged.connect(lambda text: self.nvd_input.setText(text.upper()))

        self.browse_button.clicked.connect(self.select_csv)

        layout.addWidget(self.csv_label, 0, 0)
        layout.addWidget(self.csv_path_input, 0, 1)
        layout.addWidget(self.browse_button, 0, 2)
        layout.addWidget(self.exit_date_label, 1, 0)
        layout.addWidget(self.exit_date_input, 1, 1)
        layout.addWidget(self.destination_label, 2, 0)
        layout.addWidget(self.destination_input, 2, 1)
        layout.addWidget(self.nvd_label, 3, 0)
        layout.addWidget(self.nvd_input, 3, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons, 4, 0, 1, 3)

    def select_csv(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)")
        if file:
            self.csv_path_input.setText(file)

    def get_values(self):
        return {
            "csv_path": self.csv_path_input.text(),
            "exit_date": self.exit_date_input.date().toString("yyyy-MM-dd"),
            "destination": self.destination_input.text().strip(),
            "nvd_out": self.nvd_input.text().strip(),
        }

class CattleExitPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.presubmit_exits = []

        instruction = QLabel(
            "Enter details for each animal exit below. "
            "Fields marked with * are required. "
            "Use the 'Add Exit' button to queue each exit. "
            "When finished, use 'Submit All' to save to the upload queue and merge to database."
        )
        instruction.setWordWrap(True)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(instruction)

        self.form = QFormLayout()

        # Data mapping for auto-pairing
        self.id_to_rfid = {}
        self.rfid_to_id = {}

        self.nlis_id_combo = QComboBox()
        self.nlis_id_combo.setToolTip("Select NLIS ID of animal to exit (required).")
        self.nlis_id_combo.setEditable(True)
        self.nlis_id_combo.setFixedWidth(200)
        if self.nlis_id_combo.lineEdit() is not None:
            self.nlis_id_combo.lineEdit().textChanged.connect(
                lambda text: self.nlis_id_combo.lineEdit().setText(text.upper())
            )
        self.nlis_id_combo.currentTextChanged.connect(self.sync_rfid_from_id)

        self.nlis_rfid_combo = QComboBox()
        self.nlis_rfid_combo.setToolTip("Select NLIS RFID of animal to exit (required).")
        self.nlis_rfid_combo.setEditable(True)
        self.nlis_rfid_combo.setFixedWidth(200)
        if self.nlis_rfid_combo.lineEdit() is not None:
            self.nlis_rfid_combo.lineEdit().textChanged.connect(
                lambda text: self.nlis_rfid_combo.lineEdit().setText(text.upper())
            )
        self.nlis_rfid_combo.currentTextChanged.connect(self.sync_id_from_rfid)

        self.exit_date_input = QDateEdit()
        self.exit_date_input.setCalendarPopup(True)
        self.exit_date_input.setDisplayFormat("yyyy-MM-dd")
        self.exit_date_input.setDate(QDate.currentDate())
        self.exit_date_input.setToolTip("Select exit date (required).")
        self.exit_date_input.setFixedWidth(200)
        if self.exit_date_input.lineEdit() is not None:
            self.exit_date_input.lineEdit().textChanged.connect(
                lambda text: self.exit_date_input.lineEdit().setText(text.upper())
            )

        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("Destination property or location (required)")
        self.destination_input.setToolTip("Enter the destination property or location (required).")
        self.destination_input.textChanged.connect(
            lambda text: self.destination_input.setText(text.upper())
        )

        self.sale_price_input = QLineEdit()
        self.sale_price_input.setPlaceholderText("Sale price (number, optional)")
        self.sale_price_input.setToolTip("Enter sale price (number, optional).")
        self.sale_price_input.textChanged.connect(
            lambda text: self.sale_price_input.setText(text.upper())
        )

        self.nvd_out_input = QLineEdit()
        self.nvd_out_input.setPlaceholderText("NVD OUT Number (optional)")
        self.nvd_out_input.setToolTip("Enter the NVD OUT Number (optional).")
        self.nvd_out_input.textChanged.connect(
            lambda text: self.nvd_out_input.setText(text.upper())
        )

        self.form.addRow("NLIS ID NO.*", self.nlis_id_combo)
        self.form.addRow("NLIS RFID", self.nlis_rfid_combo)
        self.form.addRow("EXIT DATE*", self.exit_date_input)
        self.form.addRow("DESTINATION*", self.destination_input)
        self.form.addRow("SALE PRICE", self.sale_price_input)
        self.form.addRow("NVD OUT NUMBER", self.nvd_out_input)

        self.add_exit_button = QPushButton("Add Exit")
        self.add_exit_button.clicked.connect(self.add_exit)

        self.bulk_exit_button = QPushButton("Bulk Edit")
        self.bulk_exit_button.clicked.connect(self.bulk_exit_popup)

        self.clear_fields_button = QPushButton("Clear Fields")
        self.clear_fields_button.clicked.connect(self.clear_fields)

        self.clear_queue_button = QPushButton("Clear Queue")
        self.clear_queue_button.clicked.connect(self.clear_queue)

        self.submit_all_button = QPushButton("Submit All")
        self.submit_all_button.clicked.connect(self.submit_all)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_exit_button)
        button_layout.addWidget(self.bulk_exit_button)
        button_layout.addWidget(self.clear_fields_button)
        button_layout.addWidget(self.clear_queue_button)
        button_layout.addWidget(self.submit_all_button)

        self.exit_table = QTableWidget(0, 6)
        self.exit_table.setHorizontalHeaderLabels([
            "NLIS ID", "NLIS RFID", "Exit Date", "Destination", "Sale Price", "NVD OUT Number"
        ])
        self.exit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.exit_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.exit_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.exit_table.setSelectionMode(QTableWidget.SingleSelection)
        self.exit_table.setToolTip("Queued cattle exits. Use 'Submit All' to save and merge.")

        self.layout().addLayout(self.form)
        self.layout().addLayout(button_layout)
        self.layout().addWidget(QLabel("Queued Animal Exits:"))
        self.layout().addWidget(self.exit_table)

        self.load_active_nlis_ids_and_rfids()

    def load_active_nlis_ids_and_rfids(self):
        self.rfid_set = set()
        self.id_set = set()
        self.id_to_rfid = {}
        self.rfid_to_id = {}
        if not os.path.exists(DB_PATH):
            self.nlis_id_combo.clear()
            self.nlis_rfid_combo.clear()
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT nlis_id, nlis_rfid FROM cattle_registry WHERE status = 'active'")
        rows = cur.fetchall()
        conn.close()
        self.nlis_id_combo.blockSignals(True)
        self.nlis_rfid_combo.blockSignals(True)
        self.nlis_id_combo.clear()
        self.nlis_rfid_combo.clear()
        self.id_set = set()
        self.rfid_set = set()
        for row in rows:
            nlis_id, nlis_rfid = row
            if nlis_id:
                nlis_id = str(nlis_id).upper()
                self.id_set.add(nlis_id)
                # Always map, even if RFID is blank
                self.id_to_rfid[nlis_id] = str(nlis_rfid).upper() if nlis_rfid else ""
            if nlis_rfid:
                nlis_rfid = str(nlis_rfid).upper()
                self.rfid_set.add(nlis_rfid)
                if nlis_id:
                    self.rfid_to_id[nlis_rfid] = nlis_id
        self.nlis_id_combo.addItems(sorted(self.id_set))
        self.nlis_rfid_combo.addItems(sorted(self.rfid_set))
        self.nlis_id_combo.blockSignals(False)
        self.nlis_rfid_combo.blockSignals(False)

    def sync_rfid_from_id(self, nlis_id):
        nlis_id = nlis_id.strip().upper()
        rfid = self.id_to_rfid.get(nlis_id, "")
        self.nlis_rfid_combo.blockSignals(True)
        self.nlis_rfid_combo.setCurrentText(rfid)
        self.nlis_rfid_combo.blockSignals(False)

    def sync_id_from_rfid(self, nlis_rfid):
        nlis_rfid = nlis_rfid.strip().upper()
        nlis_id = self.rfid_to_id.get(nlis_rfid, "")
        self.nlis_id_combo.blockSignals(True)
        self.nlis_id_combo.setCurrentText(nlis_id)
        self.nlis_id_combo.blockSignals(False)

    def add_exit(self):
        data = self.collect_data()
        try:
            self.validate_data(data)
            if self.duplicate_in_queue(data["nlis_id"], data["nlis_rfid"]):
                raise ValueError("This NLIS ID or RFID is already queued for exit. Duplicate exits are not allowed.")
            self.presubmit_exits.append(data)
            self.add_exit_to_table(data)
            self.clear_fields()
        except ValueError as ve:
            QMessageBox.warning(self, "Validation Error", str(ve))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error:\n{e}")

    def collect_data(self):
        return {
            "nlis_id": self.nlis_id_combo.currentText().strip().upper(),
            "nlis_rfid": self.nlis_rfid_combo.currentText().strip().upper(),
            "exit_date": self.exit_date_input.date().toString("yyyy-MM-dd"),
            "destination": self.destination_input.text().strip().upper(),
            "sale_price": self.sale_price_input.text().strip().upper(),
            "nvd_out_number": self.nvd_out_input.text().strip().upper()
        }

    def validate_data(self, data):
        if not (data["nlis_id"] or data["nlis_rfid"]):
            raise ValueError("At least one of NLIS ID or RFID must be provided.")

        if data["nlis_id"] and data["nlis_id"] not in self.id_set:
            raise ValueError("NLIS ID not found among active cattle.")
        if data["nlis_rfid"] and data["nlis_rfid"] not in self.rfid_set:
            raise ValueError("NLIS RFID not found among active cattle.")

        try:
            dt = datetime.strptime(data["exit_date"], "%Y-%m-%d")
            data["exit_date"] = int(dt.timestamp())
        except:
            raise ValueError("Exit date must be in YYYY-MM-DD format.")

        if not data["destination"]:
            raise ValueError("Destination is required.")

        try:
            if data["sale_price"]:
                data["sale_price"] = float(data["sale_price"])
            else:
                data["sale_price"] = None
        except:
            raise ValueError("Sale price must be a number.")

    def duplicate_in_queue(self, nlis_id, nlis_rfid):
        for exit in self.presubmit_exits:
            if (nlis_id and exit["nlis_id"] == nlis_id) or (nlis_rfid and exit["nlis_rfid"] == nlis_rfid):
                return True
        return False

    def add_exit_to_table(self, data):
        row = self.exit_table.rowCount()
        self.exit_table.insertRow(row)
        display_date = datetime.fromtimestamp(data["exit_date"]).strftime("%Y-%m-%d")
        values = [
            data["nlis_id"],
            data["nlis_rfid"],
            display_date,
            data["destination"],
            f"{data['sale_price']:.2f}" if data["sale_price"] is not None else "",
            data["nvd_out_number"]
        ]
        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.exit_table.setItem(row, col, item)

    def clear_fields(self):
        self.exit_date_input.setDate(QDate.currentDate())
        self.destination_input.clear()
        self.sale_price_input.clear()
        self.nvd_out_input.clear()
        self.nlis_id_combo.setCurrentText("")
        self.nlis_rfid_combo.setCurrentText("")

    def clear_queue(self):
        self.exit_table.setRowCount(0)
        self.presubmit_exits = []

    def submit_all(self):
        if not self.presubmit_exits:
            QMessageBox.warning(self, "No Exits", "No animal exits to submit. Add exits first.")
            return
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR)
        filename = f"{int(time.time())}_Cattle_Exit_Batch.json"
        filepath = os.path.join(UPLOAD_DIR, filename)
        cleaned = [
            {
                "nlis_id": exit["nlis_id"],
                "nlis_rfid": exit["nlis_rfid"],
                "exit_date": exit["exit_date"],
                "destination": exit["destination"] or None,
                "sale_price": exit["sale_price"],
                "nvd_out_number": exit["nvd_out_number"] or None
            }
            for exit in self.presubmit_exits
        ]
        try:
            with open(filepath, "w") as f:
                json.dump(cleaned, f, indent=2)
            QMessageBox.information(self, "Success", f"{len(cleaned)} exits saved to UploadQueue.")

            # Call merge script after saving
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
            QMessageBox.critical(self, "Error", f"Failed to save or merge:\n{e}")

        self.exit_table.setRowCount(0)
        self.presubmit_exits = []

    def bulk_exit_popup(self):
        dialog = BulkExitDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            csv_path = values['csv_path']
            exit_date = values['exit_date']
            destination = values['destination'].upper()
            nvd_out = values['nvd_out'].upper()
            if not csv_path or not destination or not exit_date:
                QMessageBox.warning(self, "Missing Information", "CSV file, exit date, and destination are required.")
                return
            try:
                with open(csv_path, newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    rfids = [row[0].strip().upper() for row in reader if row and row[0].strip()]
            except Exception as e:
                QMessageBox.critical(self, "File Error", f"Could not load CSV: {e}")
                return
            missing_rfids = []
            added_count = 0
            for rfid in rfids:
                if rfid not in self.rfid_set:
                    missing_rfids.append(rfid)
                    continue
                if self.duplicate_in_queue("", rfid):
                    continue
                nlis_id = self.rfid_to_id.get(rfid, "")
                data = {
                    "nlis_id": nlis_id,
                    "nlis_rfid": rfid,
                    "exit_date": exit_date,
                    "destination": destination,
                    "sale_price": None,
                    "nvd_out_number": nvd_out
                }
                try:
                    dt = datetime.strptime(exit_date, "%Y-%m-%d")
                    data["exit_date"] = int(dt.timestamp())
                except Exception:
                    data["exit_date"] = 0
                self.presubmit_exits.append(data)
                self.add_exit_to_table(data)
                added_count += 1
            msg = f"Bulk exit loaded: {added_count} animals queued."
            if missing_rfids:
                msg += f"\nThe following RFIDs were not found in the active master database and were skipped:\n" + ", ".join(missing_rfids)
            QMessageBox.information(self, "Bulk Exit Complete", msg)