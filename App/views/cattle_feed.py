import os
import json
import time
import sqlite3

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFormLayout, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt, QDate

DATA_DIR = r"C:\ProgramData\StockLOG"
DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

FEED_TYPE_CONFIG = {
    "HAY":  {"qty_label": "Quantity (bales)", "qty_unit": "bales", "input_type": "int", "stock_field": "unit_qty"},
    "GRAIN": {"qty_label": "Quantity (kg)", "qty_unit": "kg", "input_type": "float", "stock_field": "total_kg"},
    "MILK POWDER": {"qty_label": "Quantity (kg/head)", "qty_unit": "kg/head", "input_type": "float", "stock_field": "total_kg"},
    "SUPPLEMENT": {"qty_label": "Quantity (kg)", "qty_unit": "kg", "input_type": "float", "stock_field": "total_kg"},
}

class CattleFeedPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cattle Feed Entry")
        self.feed_products = []
        self.feed_info = {}
        self.mob_list = []
        self.queue = []

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        header = QLabel("Feed Mob Entry (Queue for Merge)")
        header.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 8px;")
        self.layout.addWidget(header)

        self.form = QFormLayout()

        self.feed_combo = QComboBox()
        self.feed_combo.setMaximumWidth(400)
        self._populate_feed_combo()
        self.feed_combo.currentTextChanged.connect(self._update_form_fields)
        self.form.addRow("Feed Product:", self.feed_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMaximumWidth(400)
        self.form.addRow("Feed Date:", self.date_edit)

        self.qty_spin = QSpinBox()
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(100000)
        self.qty_spin.setMaximumWidth(400)
        self.qty_spin.setVisible(False)
        self.qty_dspin = QDoubleSpinBox()
        self.qty_dspin.setMinimum(0.01)
        self.qty_dspin.setMaximum(100000)
        self.qty_dspin.setDecimals(2)
        self.qty_dspin.setMaximumWidth(400)
        self.qty_dspin.setVisible(False)

        self.qty_label = QLabel("")
        self.form.addRow(self.qty_label, self.qty_spin)
        self.form.addRow("", self.qty_dspin)

        self.mob_combo = QComboBox()
        self.mob_combo.setMaximumWidth(400)
        self._populate_mob_combo()
        self.form.addRow("Mob Number:", self.mob_combo)

        self.add_btn = QPushButton("Add Entry to Queue")
        self.add_btn.setMaximumWidth(400)
        self.add_btn.clicked.connect(self.add_to_queue)
        self.form.addRow(self.add_btn)

        self.clear_btn = QPushButton("Clear Queue")
        self.clear_btn.setMaximumWidth(400)
        self.clear_btn.clicked.connect(self.clear_queue)
        self.form.addRow(self.clear_btn)

        self.layout.addLayout(self.form)

        self.queue_table = QTableWidget(0, 6)
        self.queue_table.setMaximumWidth(900)
        self.queue_table.setHorizontalHeaderLabels(
            ["Feed Product", "Feed Date", "Qty", "Unit", "Mob Number", "Total Value"]
        )
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setSortingEnabled(False)
        self.layout.addWidget(self.queue_table)

        submit_row = QHBoxLayout()
        self.submit_btn = QPushButton("Submit All Entries")
        self.submit_btn.setMaximumWidth(400)
        self.submit_btn.clicked.connect(self.submit_queue)
        self.refresh_btn = QPushButton("Global Refresh All")
        self.refresh_btn.setMaximumWidth(400)
        self.refresh_btn.clicked.connect(self.refresh_data)
        submit_row.addWidget(self.submit_btn)
        submit_row.addWidget(self.refresh_btn)
        submit_row.addStretch()
        self.layout.addLayout(submit_row)

        self._update_form_fields()

    def _populate_feed_combo(self):
        self.feed_combo.clear()
        self.feed_products = []
        self.feed_info = {}
        if not os.path.exists(DB_PATH):
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, commodity, feed_type, price_per_unit, unit_qty, total_kg, kg_per_unit, total_feed_value FROM feed_stock")
        rows = cur.fetchall()
        for row in rows:
            feed_id = row[0]
            commodity = str(row[1]).upper()
            feed_type = str(row[2]).upper()
            price_per_unit = float(row[3])
            unit_qty = float(row[4])
            total_kg = float(row[5])
            kg_per_unit = float(row[6]) if row[6] is not None else 0.0
            total_feed_value = float(row[7]) if row[7] is not None else 0.0
            display = f"{commodity} ({feed_type})"
            self.feed_products.append(display)
            self.feed_info[display] = {
                "id": feed_id,
                "commodity": commodity,
                "feed_type": feed_type,
                "price_per_unit": price_per_unit,
                "unit_qty": unit_qty,
                "total_kg": total_kg,
                "kg_per_unit": kg_per_unit,
                "total_feed_value": total_feed_value
            }
            self.feed_combo.addItem(display)
        conn.close()

    def _populate_mob_combo(self):
        self.mob_combo.clear()
        self.mob_list = []
        if not os.path.exists(DB_PATH):
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT mob FROM cattle_registry WHERE mob IS NOT NULL AND mob != ''")
        mobs = [str(row[0]).upper() for row in cur.fetchall()]
        self.mob_list = mobs
        self.mob_combo.addItems(mobs)
        conn.close()

    def _update_form_fields(self):
        feed_display = self.feed_combo.currentText()
        feed_info = self.feed_info.get(feed_display)
        if not feed_info:
            self.qty_label.setText("")
            self.qty_spin.setVisible(False)
            self.qty_dspin.setVisible(False)
            return
        feed_type = feed_info["feed_type"]
        config = FEED_TYPE_CONFIG.get(feed_type)
        if not config:
            self.qty_label.setText("")
            self.qty_spin.setVisible(False)
            self.qty_dspin.setVisible(False)
            return
        self.qty_label.setText(config["qty_label"])
        max_qty = feed_info.get(config["stock_field"], 1)
        if config["input_type"] == "int":
            self.qty_spin.setMaximum(int(max_qty))
            self.qty_spin.setVisible(True)
            self.qty_dspin.setVisible(False)
        else:
            self.qty_dspin.setMaximum(float(max_qty))
            self.qty_dspin.setVisible(True)
            self.qty_spin.setVisible(False)

    def add_to_queue(self):
        feed_display = self.feed_combo.currentText()
        feed_info = self.feed_info.get(feed_display)
        if not feed_info:
            QMessageBox.warning(self, "Missing Field", "Feed Product is required.")
            return
        feed_type = feed_info["feed_type"]
        config = FEED_TYPE_CONFIG.get(feed_type)
        if not config:
            QMessageBox.warning(self, "Missing Field", "Feed Type is not valid.")
            return
        feed_date = self.date_edit.date()
        unix_date = int(time.mktime(feed_date.toPyDate().timetuple()))
        date_str = feed_date.toString("dd/MM/yyyy")
        mob = self.mob_combo.currentText()
        if not mob:
            QMessageBox.warning(self, "Missing Field", "Mob Number is required.")
            return

        num_animals = self._get_num_animals_in_mob(mob)
        if num_animals == 0:
            QMessageBox.warning(self, "No Animals", f"Mob '{mob}' has no animals.")
            return

        # Get quantity according to type and calculate total usage for milk powder
        if feed_type == "MILK POWDER":
            qty_per_head = self.qty_dspin.value()
            if qty_per_head <= 0:
                QMessageBox.warning(self, "Invalid Quantity", "Quantity must be greater than zero.")
                return
            total_kg_used = qty_per_head * num_animals
            display_qty = qty_per_head
            display_qty_unit = "kg/head"
            qty_for_validation = total_kg_used
            available_qty = feed_info.get("total_kg", 0)
            if total_kg_used > available_qty:
                QMessageBox.warning(self, "Insufficient Stock", f"Not enough stock for this commodity. Maximum available: {available_qty}kg.")
                return
        elif config["input_type"] == "int":
            qty = self.qty_spin.value()
            if qty <= 0:
                QMessageBox.warning(self, "Invalid Quantity", "Quantity must be greater than zero.")
                return
            display_qty = qty
            display_qty_unit = config["qty_unit"]
            qty_for_validation = qty
            available_qty = feed_info.get(config["stock_field"], 0)
            if qty > available_qty:
                QMessageBox.warning(self, "Insufficient Stock", f"Not enough stock for this commodity. Maximum available: {available_qty}.")
                return
        else:
            qty = self.qty_dspin.value()
            if qty <= 0:
                QMessageBox.warning(self, "Invalid Quantity", "Quantity must be greater than zero.")
                return
            display_qty = qty
            display_qty_unit = config["qty_unit"]
            qty_for_validation = qty
            available_qty = feed_info.get(config["stock_field"], 0)
            if qty > available_qty:
                QMessageBox.warning(self, "Insufficient Stock", f"Not enough stock for this commodity. Maximum available: {available_qty}.")
                return

        # Prevent duplicate entries (same commodity, feed_type, mob, feed_date)
        for entry in self.queue:
            if (entry["commodity"] == feed_info["commodity"] and
                entry["feed_type"] == feed_type and
                entry["mob"] == mob and
                entry["feed_date"] == unix_date):
                QMessageBox.warning(self, "Duplicate Entry", "This feed entry already exists in the queue.")
                return

        # Calculate total value
        if feed_type == "HAY":
            total_value = display_qty * feed_info["price_per_unit"]
        else:
            feed_price_per_kg = feed_info["price_per_unit"] / feed_info["kg_per_unit"] if feed_info["kg_per_unit"] else 0
            if feed_type == "MILK POWDER":
                total_value = total_kg_used * feed_price_per_kg
            else:
                total_value = display_qty * feed_price_per_kg

        per_head_cost = total_value / num_animals if num_animals else 0

        entry = {
            "feed_type": feed_type,
            "commodity": feed_info["commodity"],
            "feed_product": feed_display,
            "feed_date": unix_date,
            "date_str": date_str,
            "qty": display_qty,
            "qty_unit": display_qty_unit,
            "mob": mob,
            "total_value": total_value,
            "num_animals": num_animals,
            "per_head_cost": per_head_cost,
            "stock_field": config["stock_field"],
            "feed_id": feed_info["id"],
            "price_per_unit": feed_info["price_per_unit"],
            "unit_qty": feed_info["unit_qty"],
            "kg_per_unit": feed_info["kg_per_unit"],
            "total_kg": feed_info["total_kg"],
            "total_feed_value": feed_info["total_feed_value"],
            "total_kg_used": total_kg_used if feed_type == "MILK POWDER" else None
        }
        self.queue.append(entry)
        self._refresh_queue_table()

    def clear_queue(self):
        self.queue.clear()
        self._refresh_queue_table()

    def _get_num_animals_in_mob(self, mob):
        if not os.path.exists(DB_PATH):
            return 0
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cattle_registry WHERE mob=? AND LOWER(status)='active'", (mob,))
        result = cur.fetchone()
        conn.close()
        return result[0] if result else 0

    def _refresh_queue_table(self):
        self.queue_table.setRowCount(0)
        for entry in self.queue:
            row_num = self.queue_table.rowCount()
            self.queue_table.insertRow(row_num)
            self.queue_table.setItem(row_num, 0, QTableWidgetItem(entry['feed_product']))
            self.queue_table.setItem(row_num, 1, QTableWidgetItem(entry['date_str']))
            self.queue_table.setItem(row_num, 2, QTableWidgetItem(str(entry['qty'])))
            self.queue_table.setItem(row_num, 3, QTableWidgetItem(entry['qty_unit']))
            self.queue_table.setItem(row_num, 4, QTableWidgetItem(str(entry['mob'])))
            self.queue_table.setItem(row_num, 5, QTableWidgetItem(f"${entry['total_value']:,.2f}"))

    def submit_queue(self):
        if not self.queue:
            QMessageBox.information(self, "Nothing to Submit", "No entries in queue.")
            return

        # --- Aggregate total usage per commodity/feed_type/stock_field ---
        usage_map = {}
        for entry in self.queue:
            key = (entry["commodity"], entry["feed_type"], entry["stock_field"])
            used_qty = entry["total_kg_used"] if entry["feed_type"] == "MILK POWDER" else entry["qty"]
            usage_map.setdefault(key, 0)
            usage_map[key] += used_qty

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        errors = []

        # --- Check against stock ---
        for (commodity, feed_type, stock_field), total_used in usage_map.items():
            cur.execute(f"SELECT {stock_field} FROM feed_stock WHERE commodity=? AND feed_type=?", (commodity, feed_type))
            row = cur.fetchone()
            available = row[0] if row else 0
            if total_used > available:
                errors.append(f"Not enough {commodity} ({feed_type}) in stock. Requested: {total_used}, Available: {available}")

        if errors:
            QMessageBox.warning(self, "Commodity Stock Error", "\n".join(errors))
            conn.close()
            return

        feed_updates = []
        animal_updates = []
        feed_events = []

        feed_update_map = {}  # feed_id -> feed_update dict
        for entry in self.queue:
            feed_id = entry["feed_id"]
            feed_type = entry["feed_type"]
            commodity = entry["commodity"]
            mob = entry["mob"]
            price_per_unit = entry["price_per_unit"]
            unit_qty = entry["unit_qty"]
            kg_per_unit = entry["kg_per_unit"]
            total_kg = entry["total_kg"]
            total_feed_value = entry["total_feed_value"]

            # If not already fetched, get full feed_stock record
            if feed_id not in feed_update_map:
                cur.execute("SELECT * FROM feed_stock WHERE id=?", (feed_id,))
                feed_row = cur.fetchone()
                feed_desc = [desc[0] for desc in cur.description]
                feed_update_map[feed_id] = dict(zip(feed_desc, feed_row)) if feed_row else {}

            update = feed_update_map[feed_id]
            if feed_type == "HAY":
                qty = entry["qty"]
                update["unit_qty"] = max(0, update["unit_qty"] - qty)
                update["total_kg"] = max(0, update["total_kg"] - qty * kg_per_unit)
                update["total_feed_value"] = max(0, update["total_feed_value"] - qty * price_per_unit)
            elif feed_type in ("GRAIN", "SUPPLEMENT"):
                qty = entry["qty"]
                update["total_kg"] = max(0, update["total_kg"] - qty)
                units_used = qty / kg_per_unit if kg_per_unit else 0
                update["unit_qty"] = max(0, update["unit_qty"] - units_used)
                update["total_feed_value"] = max(0, update["total_feed_value"] - qty * (price_per_unit / kg_per_unit if kg_per_unit else 0))
            elif feed_type == "MILK POWDER":
                # qty = kg/head, total_kg_used = kg/head * num_animals
                total_kg_used = entry["total_kg_used"]
                update["total_kg"] = max(0, update["total_kg"] - total_kg_used)
                units_used = total_kg_used / kg_per_unit if kg_per_unit else 0
                update["unit_qty"] = max(0, update["unit_qty"] - units_used)
                update["total_feed_value"] = max(0, update["total_feed_value"] - total_kg_used * (price_per_unit / kg_per_unit if kg_per_unit else 0))

            cur.execute("SELECT nlis_id, animal_value FROM cattle_registry WHERE mob=? AND LOWER(status)='active'", (mob,))
            animals = cur.fetchall()
            for nlis_id, animal_value in animals:
                new_value = (animal_value if animal_value is not None else 0.0) + entry["per_head_cost"]
                animal_updates.append({"nlis_id": nlis_id, "animal_value": new_value})

            feed_events.append({
                "feed_type": entry["feed_type"],
                "commodity": entry["commodity"],
                "feed_date": entry["feed_date"],
                "qty": entry["qty"],
                "qty_unit": entry["qty_unit"],
                "mob": entry["mob"],
                "total_value": entry["total_value"],
                "num_animals": entry["num_animals"],
                "per_head_cost": entry["per_head_cost"]
            })

        feed_updates = list(feed_update_map.values())

        unix_ts = int(time.time())
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR)
        filename = f"{unix_ts}_feed_events.json"
        filepath = os.path.join(UPLOAD_DIR, filename)
        update_payload = {
            "feed_updates": feed_updates,
            "animal_updates": animal_updates,
            "feed_events": feed_events,
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(update_payload, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to write feed events JSON:\n{e}")
            conn.close()
            return

        try:
            import subprocess
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

        conn.close()
        self.queue.clear()
        self._refresh_queue_table()

    def refresh_data(self):
        self._populate_feed_combo()
        self._populate_mob_combo()
        self._update_form_fields()
        self._refresh_queue_table()