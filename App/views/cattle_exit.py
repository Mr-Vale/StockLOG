import os
import json
import time
import sqlite3
import subprocess
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QDateEdit, QHBoxLayout
)
from PyQt5.QtCore import QDate, Qt

DATA_DIR = r"C:\ProgramData\StockLOG"
DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

class CattleExitPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.presubmit_exits = []

        # Instruction blurb
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

        self.nlis_id_combo = QComboBox()
        self.nlis_id_combo.setToolTip("Select NLIS ID of animal to exit (required).")
        self.exit_date_input = QDateEdit()
        self.exit_date_input.setCalendarPopup(True)
        self.exit_date_input.setDisplayFormat("yyyy-MM-dd")
        self.exit_date_input.setDate(QDate.currentDate())
        self.exit_date_input.setToolTip("Select exit date (required).")
        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("Destination property or location (required)")
        self.destination_input.setToolTip("Enter the destination property or location (required).")
        self.sale_price_input = QLineEdit()
        self.sale_price_input.setPlaceholderText("Sale price (number, optional)")
        self.sale_price_input.setToolTip("Enter sale price (number, optional).")
        self.nvd_out_input = QLineEdit()
        self.nvd_out_input.setPlaceholderText("NVD OUT Number (optional)")
        self.nvd_out_input.setToolTip("Enter the NVD OUT Number (optional).")

        self.form.addRow("NLIS ID NO.*", self.nlis_id_combo)
        self.form.addRow("EXIT DATE*", self.exit_date_input)
        self.form.addRow("DESTINATION*", self.destination_input)
        self.form.addRow("SALE PRICE", self.sale_price_input)
        self.form.addRow("NVD OUT NUMBER", self.nvd_out_input)

        # --- Buttons ---
        self.add_exit_button = QPushButton("Add Exit")
        self.add_exit_button.clicked.connect(self.add_exit)

        self.clear_fields_button = QPushButton("Clear Fields")
        self.clear_fields_button.clicked.connect(self.clear_fields)

        self.clear_queue_button = QPushButton("Clear Queue")
        self.clear_queue_button.clicked.connect(self.clear_queue)

        self.submit_all_button = QPushButton("Submit All")
        self.submit_all_button.clicked.connect(self.submit_all)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_exit_button)
        button_layout.addWidget(self.clear_fields_button)
        button_layout.addWidget(self.clear_queue_button)
        button_layout.addWidget(self.submit_all_button)

        # --- Table for queued exits ---
        self.exit_table = QTableWidget(0, 5)
        self.exit_table.setHorizontalHeaderLabels([
            "NLIS ID", "Exit Date", "Destination", "Sale Price", "NVD OUT Number"
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

        self.load_active_nlis_ids()

    def load_active_nlis_ids(self):
        if not os.path.exists(DB_PATH):
            self.nlis_id_combo.clear()
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT nlis_id FROM cattle_registry WHERE status = 'active'")
        rows = cur.fetchall()
        conn.close()
        self.nlis_id_combo.clear()
        self.nlis_id_combo.addItems([row[0] for row in rows])

    def add_exit(self):
        data = self.collect_data()
        try:
            self.validate_data(data)
            if self.duplicate_in_queue(data["nlis_id"]):
                raise ValueError("This NLIS ID is already queued for exit. Duplicate exits are not allowed.")
            self.presubmit_exits.append(data)
            self.add_exit_to_table(data)
            self.clear_fields()
        except ValueError as ve:
            QMessageBox.warning(self, "Validation Error", str(ve))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error:\n{e}")

    def collect_data(self):
        return {
            "nlis_id": self.nlis_id_combo.currentText().strip(),
            "exit_date": self.exit_date_input.date().toString("yyyy-MM-dd"),
            "destination": self.destination_input.text().strip(),
            "sale_price": self.sale_price_input.text().strip(),
            "nvd_out_number": self.nvd_out_input.text().strip()
        }

    def validate_data(self, data):
        if not data["nlis_id"]:
            raise ValueError("NLIS ID must be selected.")

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

    def duplicate_in_queue(self, nlis_id):
        for exit in self.presubmit_exits:
            if exit["nlis_id"] == nlis_id:
                return True
        return False

    def add_exit_to_table(self, data):
        row = self.exit_table.rowCount()
        self.exit_table.insertRow(row)
        display_date = datetime.fromtimestamp(data["exit_date"]).strftime("%Y-%m-%d")
        values = [
            data["nlis_id"],
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
        self.load_active_nlis_ids()  # Refresh dropdown

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