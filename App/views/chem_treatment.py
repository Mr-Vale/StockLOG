import os
import json
import time
import sqlite3
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QFormLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QMessageBox, QDialog, QDialogButtonBox, QFileDialog
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

DATA_DIR = r"C:\ProgramData\StockLOG"
DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

class ChemTreatmentPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Medical Treatments")
        self.setLayout(QVBoxLayout())
        self.treatment_queue = []

        header = QLabel("Medical Treatment Entry (Queue for Merge)")
        header.setStyleSheet("font-weight: bold; font-size: 16px; margin-top: 10px;")
        self.layout().addWidget(header)

        # --- Treatment Entry Form ---
        form = QFormLayout()
        self.chem_combo = QComboBox()
        self.chem_combo.setMaximumWidth(400)
        self._populate_chem_combo()
        form.addRow("Chemical Product:", self.chem_combo)

        self.dose_amount = QLineEdit()
        self.dose_amount.setMaximumWidth(400)
        form.addRow("Dose Amount:", self.dose_amount)

        self.dose_unit = QLineEdit()
        self.dose_unit.setMaximumWidth(400)
        form.addRow("Dose Unit:", self.dose_unit)

        self.mob_combo = QComboBox()
        self.mob_combo.setMaximumWidth(400)
        self._populate_mob_combo()
        form.addRow("Mob (Group):", self.mob_combo)

        self.indiv_combo = QComboBox()
        self.indiv_combo.setMaximumWidth(400)
        self._populate_indiv_combo()
        form.addRow("Individual Animal:", self.indiv_combo)

        self.notes = QLineEdit()
        self.notes.setMaximumWidth(400)
        form.addRow("Notes:", self.notes)

        self.add_btn = QPushButton("Add Treatment to Queue")
        self.add_btn.setMaximumWidth(400)
        self.add_btn.clicked.connect(self.add_to_queue)
        form.addRow(self.add_btn)

        self.clear_btn = QPushButton("Clear Queue")
        self.clear_btn.setMaximumWidth(400)
        self.clear_btn.clicked.connect(self.clear_queue)
        form.addRow(self.clear_btn)

        self.layout().addLayout(form)

        # --- Queue Table ---
        self.queue_table = QTableWidget(0, 8)
        self.queue_table.setMaximumWidth(1000)
        self.queue_table.setHorizontalHeaderLabels([
            "Chemical", "Dose", "Unit", "Mob", "Individual", "Notes", "Total Cost", "Queue Time"
        ])
        self.queue_table.setAlternatingRowColors(True)
        self.layout().addWidget(self.queue_table)

        # --- Submit Row ---
        submit_row = QHBoxLayout()
        self.submit_btn = QPushButton("Submit All Treatments")
        self.submit_btn.setMaximumWidth(400)
        self.submit_btn.clicked.connect(self.submit_queue)
        self.refresh_btn = QPushButton("Global Refresh All")
        self.refresh_btn.setMaximumWidth(400)
        self.refresh_btn.clicked.connect(self.refresh_data)
        submit_row.addWidget(self.submit_btn)
        submit_row.addWidget(self.refresh_btn)
        submit_row.addStretch()
        self.layout().addLayout(submit_row)

        self.refresh_data()

    def _populate_chem_combo(self):
        self.chem_combo.clear()
        self.chem_info = {}
        if not os.path.exists(DB_PATH):
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT product_name, batch_number, total_quantity, price_per_unit FROM chemical_inventory"
        )
        for row in cur.fetchall():
            pname, batch, qty, price = row
            display = f"{pname} (Batch: {batch})"
            self.chem_info[display] = {
                "product_name": pname,
                "batch_number": batch,
                "total_quantity": qty,
                "price_per_unit": price
            }
            self.chem_combo.addItem(display)
        conn.close()

    def _populate_mob_combo(self):
        self.mob_combo.clear()
        self.mob_list = []
        if not os.path.exists(DB_PATH):
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT mob FROM cattle_registry WHERE mob IS NOT NULL AND mob != '' AND LOWER(status)='active'")
        mobs = [str(row[0]).upper() for row in cur.fetchall()]
        self.mob_list = mobs
        self.mob_combo.addItems(mobs)
        conn.close()

    def _populate_indiv_combo(self):
        self.indiv_combo.clear()
        self.indiv_list = []
        if not os.path.exists(DB_PATH):
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT nlis_id FROM cattle_registry WHERE nlis_id IS NOT NULL AND nlis_id != '' AND LOWER(status)='active'")
        ids = [str(row[0]).upper() for row in cur.fetchall()]
        self.indiv_list = ids
        self.indiv_combo.addItems(ids)
        conn.close()

    def add_to_queue(self):
        chem_display = self.chem_combo.currentText()
        chem_info = self.chem_info.get(chem_display)
        if not chem_info:
            QMessageBox.warning(self, "Missing Field", "Chemical Product is required.")
            return
        try:
            dose = float(self.dose_amount.text())
        except Exception:
            QMessageBox.warning(self, "Invalid Dose", "Dose amount must be a number.")
            return
        unit = self.dose_unit.text().strip()
        if not unit:
            QMessageBox.warning(self, "Missing Field", "Dose Unit is required.")
            return
        mob = self.mob_combo.currentText().strip()
        indiv = self.indiv_combo.currentText().strip()
        notes = self.notes.text().strip()
        queue_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Must specify either mob or individual (not both blank)
        if not mob and not indiv:
            QMessageBox.warning(self, "Missing Target", "Must select either Mob or Individual animal.")
            return

        # Check enough chemical stock
        total_needed = dose
        num_animals = 0
        animal_ids = []
        if mob:
            # Get number of animals in mob
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT nlis_id FROM cattle_registry WHERE mob=? AND LOWER(status)='active'", (mob,))
            animals = cur.fetchall()
            conn.close()
            num_animals = len(animals)
            animal_ids = [row[0] for row in animals]
            total_needed = dose * num_animals
        elif indiv:
            animal_ids = [indiv]
            num_animals = 1

        available_qty = chem_info["total_quantity"]
        if total_needed > available_qty:
            QMessageBox.warning(self, "Insufficient Stock", f"Not enough chemical stock. Needed: {total_needed}, Available: {available_qty}")
            return

        # Calculate cost per animal
        price_per_unit = chem_info["price_per_unit"]
        total_cost = total_needed * price_per_unit

        # Add to queue
        self.treatment_queue.append({
            "chemical": chem_info["product_name"],
            "batch_number": chem_info["batch_number"],
            "dose": dose,
            "unit": unit,
            "mob": mob,
            "individual": indiv,
            "animal_ids": animal_ids,
            "notes": notes,
            "total_cost": total_cost,
            "queue_time": queue_time,
        })
        self._refresh_queue_table()

    def clear_queue(self):
        self.treatment_queue.clear()
        self._refresh_queue_table()

    def _refresh_queue_table(self):
        self.queue_table.setRowCount(0)
        for entry in self.treatment_queue:
            row_num = self.queue_table.rowCount()
            self.queue_table.insertRow(row_num)
            self.queue_table.setItem(row_num, 0, QTableWidgetItem(entry["chemical"]))
            self.queue_table.setItem(row_num, 1, QTableWidgetItem(str(entry["dose"])))
            self.queue_table.setItem(row_num, 2, QTableWidgetItem(entry["unit"]))
            self.queue_table.setItem(row_num, 3, QTableWidgetItem(str(entry["mob"])))
            self.queue_table.setItem(row_num, 4, QTableWidgetItem(str(entry["individual"])))
            self.queue_table.setItem(row_num, 5, QTableWidgetItem(entry["notes"]))
            self.queue_table.setItem(row_num, 6, QTableWidgetItem(f"${entry['total_cost']:.2f}"))
            self.queue_table.setItem(row_num, 7, QTableWidgetItem(entry["queue_time"]))

    def submit_queue(self):
        if not self.treatment_queue:
            QMessageBox.information(self, "Nothing to Submit", "No treatments in queue.")
            return

        unix_ts = int(time.time())
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR)
        filename = f"{unix_ts}_treatment_events.json"
        filepath = os.path.join(UPLOAD_DIR, filename)

        # Prepare records for merging: update chemical stock, update animal value, log treatment
        merge_records = []
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for entry in self.treatment_queue:
            chem = entry["chemical"]
            batch = entry["batch_number"]
            dose = entry["dose"]
            unit = entry["unit"]
            mob = entry["mob"]
            indiv = entry["individual"]
            notes = entry["notes"]
            total_cost = entry["total_cost"]
            animal_ids = entry["animal_ids"]

            # Update chemical_inventory (reduce total_quantity)
            cur.execute("SELECT total_quantity FROM chemical_inventory WHERE product_name=? AND batch_number=?", (chem, batch))
            cur_qty = cur.fetchone()
            if cur_qty:
                new_qty = float(cur_qty[0]) - (dose*len(animal_ids))
                merge_records.append({
                    "product_name": chem,
                    "batch_number": batch,
                    "total_quantity": new_qty,
                    "last_updated": unix_ts
                })

            # Update animal_value for each treated animal
            for aid in animal_ids:
                cur.execute("SELECT animal_value FROM cattle_registry WHERE nlis_id=?", (aid,))
                cur_val = cur.fetchone()
                new_val = (cur_val[0] if cur_val and cur_val[0] else 0.0) + (dose * entry["total_cost"]/len(animal_ids) if len(animal_ids) else 0)
                merge_records.append({
                    "nlis_id": aid,
                    "animal_value": new_val,
                    "last_updated": unix_ts
                })

            # Treatment log entry (for cattle_log table)
            for aid in animal_ids:
                merge_records.append({
                    "event_type": "TREATMENT",
                    "event_date": unix_ts,
                    "product_name": chem,
                    "batch_number": batch,
                    "amount": dose,
                    "unit": unit,
                    "mob": mob if mob else None,
                    "nlis_id": aid,
                    "notes": notes,
                    "last_updated": unix_ts
                })

        conn.close()
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(merge_records, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to write treatment events JSON:\n{e}")
            return

        # Call merge script
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

        self.treatment_queue.clear()
        self._refresh_queue_table()

    def refresh_data(self):
        self._populate_chem_combo()
        self._populate_mob_combo()
        self._populate_indiv_combo()
        self._refresh_queue_table()