import os
import json
import time
import sqlite3
import subprocess
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QPushButton,
    QVBoxLayout, QFormLayout, QMessageBox, QDateEdit, QComboBox, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import QDate, Qt

DATA_DIR = r"C:\ProgramData\StockLOG"
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
CORE_DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

class CattleEntryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.mob_history = self.load_mob_history()
        self.presubmit_entries = []

        # --- Instruction blurb ---
        instruction = QLabel(
            "Enter details for each animal below. "
            "Fields marked with * are required. "
            "Use the 'Add Animal' button to queue each entry. "
            "When finished, use 'Submit All' to save to the upload queue and merge to database."
        )
        instruction.setWordWrap(True)

        # --- Field widgets ---
        self.entry_date = QDateEdit()
        self.entry_date.setCalendarPopup(True)
        self.entry_date.setDisplayFormat("yyyy-MM-dd")
        self.entry_date.setDate(QDate.currentDate())
        self.entry_date.setToolTip("Select the date the animal was entered (required).")

        self.nlis_id = QLineEdit()
        self.nlis_id.setPlaceholderText("16 characters (leave blank if unknown)")
        self.nlis_id.setToolTip("Enter the NLIS ID (16 characters) if available.")

        self.nlis_rfid = QLineEdit()
        self.nlis_rfid.setPlaceholderText("15 digits (leave blank if unknown)")
        self.nlis_rfid.setMaxLength(15)
        self.nlis_rfid.setToolTip("Enter the NLIS RFID (15 digits) if available.")

        self.source_pic = QLineEdit()
        self.source_pic.setPlaceholderText("8 characters")
        self.source_pic.setToolTip("Enter the PIC of the source (8 characters).")

        self.source_name = QLineEdit()
        self.source_name.setPlaceholderText("Name of source property/vendor")
        self.source_name.setToolTip("Enter the name of the source (optional).")

        self.source_address = QTextEdit()
        self.source_address.setPlaceholderText("Source address")
        self.source_address.setToolTip("Enter the address of the source property/vendor (optional).")
        # Set to 3 lines tall
        self.source_address.setFixedHeight(self.source_address.fontMetrics().height() * 3 + 12)

        self.nvd_in_number = QLineEdit()
        self.nvd_in_number.setPlaceholderText("NVD IN Number (optional)")
        self.nvd_in_number.setToolTip("Enter the NVD IN Number (optional).")

        self.breed_description = QLineEdit()
        self.breed_description.setPlaceholderText("Breed or description (required)")
        self.breed_description.setToolTip("Enter the breed or description of the animal.")

        self.sex = QComboBox()
        self.sex.addItems(["M", "F"])
        self.sex.setCurrentIndex(-1)
        self.sex.setToolTip("Select the sex of the animal: M (Male) or F (Female).")

        self.mob = QComboBox()
        self.mob.setEditable(True)
        self.mob.setToolTip("Select a previously used mob number or type a new one (required).")
        self.mob.addItems(self.mob_history)
        self.mob.setCurrentText("")
        self.mob.setPlaceholderText("Mob number (required)")

        self.purchase_price = QLineEdit()
        self.purchase_price.setPlaceholderText("Purchase price (number, defaults to 0)")
        self.purchase_price.setToolTip("Enter the purchase price (optional, number; defaults to 0 if blank).")

        # --- Layout ---
        form_layout = QFormLayout()
        form_layout.addRow("Entry Date*", self.entry_date)
        form_layout.addRow("NLIS ID", self.nlis_id)
        form_layout.addRow("NLIS RFID", self.nlis_rfid)
        form_layout.addRow("Source PIC", self.source_pic)
        form_layout.addRow("Source Name", self.source_name)
        form_layout.addRow("Source Address", self.source_address)
        form_layout.addRow("NVD IN Number", self.nvd_in_number)
        form_layout.addRow("Breed/Description*", self.breed_description)
        form_layout.addRow("Sex*", self.sex)
        form_layout.addRow("Mob*", self.mob)
        form_layout.addRow("Purchase Price", self.purchase_price)

        # --- Buttons ---
        self.add_button = QPushButton("Add Animal")
        self.add_button.clicked.connect(self.add_entry)

        self.clear_fields_button = QPushButton("Clear Fields")
        self.clear_fields_button.clicked.connect(self.clear_fields)

        self.clear_queue_button = QPushButton("Clear Queue")
        self.clear_queue_button.clicked.connect(self.clear_queue)

        self.submit_all_button = QPushButton("Submit All")
        self.submit_all_button.clicked.connect(self.submit_all)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.clear_fields_button)
        button_layout.addWidget(self.clear_queue_button)
        button_layout.addWidget(self.submit_all_button)

        # --- Table to hold presubmit entries ---
        self.entry_table = QTableWidget(0, 11)
        self.entry_table.setHorizontalHeaderLabels([
            "Entry Date", "NLIS ID", "NLIS RFID", "Source PIC", "Source Name",
            "Source Address", "NVD IN Number", "Breed", "Sex", "Mob", "Price"
        ])
        self.entry_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.entry_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.entry_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.entry_table.setSelectionMode(QTableWidget.SingleSelection)
        self.entry_table.setToolTip("Queued cattle entries. Use 'Submit All' to save and merge.")

        # --- Main layout ---
        main_layout = QVBoxLayout()
        main_layout.addWidget(instruction)
        main_layout.addLayout(form_layout)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(QLabel("Queued Animal Entries:"))
        main_layout.addWidget(self.entry_table)
        self.setLayout(main_layout)

    def load_mob_history(self):
        """Load previously used mobs from master DB (active cattle only)."""
        mobs = set()
        if os.path.exists(CORE_DB_PATH):
            try:
                conn = sqlite3.connect(CORE_DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT mob FROM cattle_registry WHERE mob IS NOT NULL AND mob != ''")
                mobs = set(str(row[0]) for row in cursor.fetchall())
                conn.close()
            except Exception:
                pass
        return sorted(mobs)

    def add_entry(self):
        entry = self.collect_data()
        try:
            self.validate_data(entry)
            # Duplicate check (master.db, active cattle only AND presubmit table)
            if self.duplicate_in_master_or_queue(entry["nlis_id"], entry["nlis_rfid"]):
                raise ValueError("NLIS ID or NLIS RFID already exists in the master database or queued entries.\n"
                                 "This animal entry cannot be queued.")
            self.presubmit_entries.append(entry)
            self.add_entry_to_table(entry)
            self.clear_fields()
        except ValueError as e:
            QMessageBox.warning(self, "Entry Rejected", str(e))

    def collect_data(self):
        entry = {
            'entry_date': self.entry_date.date().toString("yyyy-MM-dd"),
            'nlis_id': self.nlis_id.text().strip(),
            'nlis_rfid': self.nlis_rfid.text().strip(),
            'source_pic': self.source_pic.text().strip(),
            'source_name': self.source_name.text().strip(),
            'source_address': self.source_address.toPlainText().strip(),
            'nvd_in_number': self.nvd_in_number.text().strip(),
            'breed_description': self.breed_description.text().strip(),
            'sex': self.sex.currentText().strip(),
            'mob': self.mob.currentText().strip(),
            'purchase_price': self.purchase_price.text().strip(),
        }
        return entry

    def validate_data(self, entry):
        # Required date
        if not entry["entry_date"]:
            raise ValueError("Entry date is required.")
        try:
            dt = datetime.strptime(entry["entry_date"], "%Y-%m-%d")
            entry["entry_date"] = int(dt.timestamp())
        except:
            raise ValueError("Entry date must be YYYY-MM-DD.")

        if not (entry["nlis_id"] or entry["nlis_rfid"]):
            raise ValueError("At least one of NLIS ID or RFID must be provided.")

        if entry["nlis_id"] and len(entry["nlis_id"]) != 16:
            raise ValueError("NLIS ID must be exactly 16 characters.")

        if entry["nlis_rfid"]:
            if len(entry["nlis_rfid"]) != 15 or not entry["nlis_rfid"].isdigit():
                raise ValueError("NLIS RFID must be exactly 15 digits.")

        if entry["source_pic"] and len(entry["source_pic"]) != 8:
            raise ValueError("Source PIC must be 8 characters.")

        if not entry["breed_description"]:
            raise ValueError("Breed/Description is required.")

        if entry["sex"] not in ["M", "F"]:
            raise ValueError("Sex must be 'M' or 'F'.")

        if not entry["mob"]:
            raise ValueError("Mob number is required.")

        # Confirm purchase price as float or set to 0
        if entry["purchase_price"]:
            try:
                entry["purchase_price"] = float(entry["purchase_price"])
            except:
                raise ValueError("Purchase price must be a number.")
        else:
            entry["purchase_price"] = 0.0

    def duplicate_in_master_or_queue(self, nlis_id, nlis_rfid):
        # Check queued entries first
        for entry in self.presubmit_entries:
            if nlis_id and entry.get("nlis_id") == nlis_id:
                return True
            if nlis_rfid and entry.get("nlis_rfid") == nlis_rfid:
                return True
        # Check master database
        if not os.path.exists(CORE_DB_PATH):
            return False
        try:
            conn = sqlite3.connect(CORE_DB_PATH)
            cursor = conn.cursor()
            query = """
                SELECT COUNT(*) FROM cattle_registry
                WHERE status='active' AND (
                    (nlis_id=? AND ?!='') OR
                    (nlis_rfid=? AND ?!='')
                )
            """
            cursor.execute(query, (nlis_id, nlis_id, nlis_rfid, nlis_rfid))
            exists = cursor.fetchone()[0] > 0
            conn.close()
            return exists
        except Exception:
            return False

    def add_entry_to_table(self, entry):
        row = self.entry_table.rowCount()
        self.entry_table.insertRow(row)
        # Show date as YYYY-MM-DD for table
        display_date = datetime.fromtimestamp(entry['entry_date']).strftime("%Y-%m-%d")
        values = [
            display_date,
            entry['nlis_id'],
            entry['nlis_rfid'],
            entry['source_pic'],
            entry['source_name'],
            entry['source_address'],
            entry['nvd_in_number'],
            entry['breed_description'],
            entry['sex'],
            entry['mob'],
            f"{entry['purchase_price']:.2f}" if entry['purchase_price'] else "0.00"
        ]
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.entry_table.setItem(row, col, item)

    def clear_fields(self):
        self.entry_date.setDate(QDate.currentDate())
        self.nlis_id.clear()
        self.nlis_rfid.clear()
        self.source_pic.clear()
        self.source_name.clear()
        self.source_address.clear()
        self.nvd_in_number.clear()
        self.breed_description.clear()
        self.sex.setCurrentIndex(-1)
        self.mob.setCurrentText("")
        self.purchase_price.clear()

    def clear_queue(self):
        self.entry_table.setRowCount(0)
        self.presubmit_entries = []

    def submit_all(self):
        if not self.presubmit_entries:
            QMessageBox.warning(self, "No Entries", "No animals to submit. Add entries first.")
            return
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR)
        filename = f"{int(time.time())}_Cattle_Entry_Batch.json"
        filepath = os.path.join(UPLOAD_DIR, filename)
        # Clean nulls for each entry
        cleaned = [
            {k: v for k, v in entry.items() if v not in ["", None]}
            for entry in self.presubmit_entries
        ]
        try:
            with open(filepath, "w") as f:
                json.dump(cleaned, f, indent=2)
            QMessageBox.information(self, "Success", f"{len(cleaned)} entries saved to UploadQueue.")

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

        self.entry_table.setRowCount(0)
        self.presubmit_entries = []