import os
import json
import time
import sqlite3
import subprocess
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QLabel, QLineEdit, QTextEdit,
    QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDateEdit, QFrame, QCheckBox
)
from PyQt5.QtCore import Qt, QDate

DATA_DIR = r"C:\ProgramData\StockLOG"
CORE_DB_PATH = os.path.join(DATA_DIR, "Core", "master.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
MERGE_SCRIPT_PATH = r"C:\Program Files\StockLOG\App\logic\merge_uploads.py"

class CattleEditPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QHBoxLayout())

        # --------- Animal Edit Section ---------
        animal_edit_layout = QVBoxLayout()

        # Add instruction note above ID/RFID selection
        self.select_note = QLabel("Select an NLIS ID or NLIS RFID number below to edit animal details.")
        animal_edit_layout.addWidget(self.select_note)

        # Animal ID/RFID selection, both start blank and are editable if blank
        self.animal_id_combo = QComboBox()
        self.animal_id_combo.setEditable(True)
        self.animal_id_combo.setFixedWidth(200)
        self.animal_id_combo.setToolTip("Select NLIS ID")
        self.animal_id_combo.addItem("")
        self.animal_rfid_combo = QComboBox()
        self.animal_rfid_combo.setEditable(True)
        self.animal_rfid_combo.setFixedWidth(200)
        self.animal_rfid_combo.setToolTip("Select NLIS RFID")
        self.animal_rfid_combo.addItem("")
        # Set up form for the two fields
        animal_select_form = QFormLayout()
        animal_select_form.addRow("NLIS ID:", self.animal_id_combo)
        animal_select_form.addRow("NLIS RFID:", self.animal_rfid_combo)

        animal_edit_layout.addLayout(animal_select_form)

        # Add a dividing line below first two fields
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        animal_edit_layout.addWidget(divider)

        # Animal detail fields (ID/RFID displayed or editable, others editable)
        self.id_display = QLineEdit()
        self.rfid_display = QLineEdit()
        self.id_display.setReadOnly(False)
        self.rfid_display.setReadOnly(False)
        self.id_display.setFixedWidth(200)
        self.rfid_display.setFixedWidth(200)
        self.source_pic = QLineEdit()
        self.source_pic.setFixedWidth(200)
        self.source_name = QLineEdit()
        self.source_address = QTextEdit()
        self.nvd_in_number = QLineEdit()
        self.nvd_in_number.setFixedWidth(200)
        self.breed_description = QLineEdit()
        self.breed_description.setFixedWidth(200)
        self.sex = QComboBox()
        self.sex.addItems(["M", "F"])
        self.sex.setFixedWidth(200)
        self.mob = QLineEdit()
        self.mob.setFixedWidth(200)
        self.purchase_price = QLineEdit()
        self.purchase_price.setFixedWidth(200)

        # Entry/Exit dates as calendar widgets (QDateEdit, ISO display, unix int save)
        self.entry_date = QDateEdit()
        self.entry_date.setCalendarPopup(True)
        self.entry_date.setDisplayFormat("yyyy-MM-dd")
        self.entry_date.setFixedWidth(200)

        # Exit Date checkbox + calendar combo
        self.exit_date_enable = QCheckBox("Set Exit Date")
        self.exit_date = QDateEdit()
        self.exit_date.setCalendarPopup(True)
        self.exit_date.setDisplayFormat("yyyy-MM-dd")
        self.exit_date.setFixedWidth(200)
        self.exit_date.setEnabled(False)  # Disabled by default
        self.exit_date_enable.toggled.connect(self.exit_date.setEnabled)

        self.destination = QLineEdit()
        self.destination.setFixedWidth(200)
        self.sale_price = QLineEdit()
        self.sale_price.setFixedWidth(200)
        self.nvd_out_number = QLineEdit()
        self.nvd_out_number.setFixedWidth(200)
        self.status_label = QLabel()
        self.created_at_label = QLabel()
        self.last_updated_label = QLabel()

        animal_edit_form = QFormLayout()
        animal_edit_form.addRow("NLIS ID", self.id_display)
        animal_edit_form.addRow("NLIS RFID", self.rfid_display)
        animal_edit_form.addRow("Source PIC", self.source_pic)
        animal_edit_form.addRow("Source Name", self.source_name)
        animal_edit_form.addRow("Source Address", self.source_address)
        animal_edit_form.addRow("NVD IN Number", self.nvd_in_number)
        animal_edit_form.addRow("Breed/Description", self.breed_description)
        animal_edit_form.addRow("Sex", self.sex)
        animal_edit_form.addRow("Mob", self.mob)
        animal_edit_form.addRow("Purchase Price", self.purchase_price)
        animal_edit_form.addRow("Entry Date", self.entry_date)
        # Add exit date with checkbox
        exit_date_layout = QHBoxLayout()
        exit_date_layout.addWidget(self.exit_date)
        exit_date_layout.addWidget(self.exit_date_enable)
        exit_date_layout.addStretch()
        animal_edit_form.addRow("Exit Date", exit_date_layout)
        animal_edit_form.addRow("Destination", self.destination)
        animal_edit_form.addRow("Sale Price", self.sale_price)
        animal_edit_form.addRow("NVD OUT Number", self.nvd_out_number)
        animal_edit_form.addRow("Status", self.status_label)
        animal_edit_form.addRow("Created At", self.created_at_label)
        animal_edit_form.addRow("Last Updated", self.last_updated_label)

        # Make source name and source address full width in the layout
        self.source_name.setMinimumWidth(400)
        self.source_address.setMinimumWidth(400)

        self.save_animal_changes = QPushButton("Save Changes")
        self.save_animal_changes.clicked.connect(self.save_animal_edits)

        animal_edit_layout.addLayout(animal_edit_form)
        animal_edit_layout.addWidget(self.save_animal_changes)
        animal_edit_layout.addStretch()

        # --------- Mob Edit Section ---------
        mob_edit_layout = QVBoxLayout()
        mob_instruction = QLabel("To edit the mob for a group of animals, select a mob below and use the controls.")
        mob_edit_layout.addWidget(mob_instruction)
        self.mob_combo = QComboBox()
        self.mob_combo.setEditable(True)
        self.mob_combo.setFixedWidth(200)
        self.mob_combo.setToolTip("Select Mob Number")
        self.load_mobs_button = QPushButton("Load Mob")
        self.load_mobs_button.clicked.connect(self.load_mob_animals)

        mob_select_form = QFormLayout()
        mob_select_form.addRow("Mob Number:", self.mob_combo)
        mob_select_form.addWidget(self.load_mobs_button)

        self.mob_table = QTableWidget(0, 6)
        self.mob_table.setHorizontalHeaderLabels([
            "Select", "NLIS ID", "NLIS RFID", "Breed", "Sex", "Mob"
        ])
        self.mob_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.mob_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mob_table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.mob_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.new_mob_input = QLineEdit()
        self.new_mob_input.setPlaceholderText("New Mob Number")
        self.new_mob_input.setFixedWidth(200)
        self.change_mob_button = QPushButton("Change Mob For Selected")
        self.change_mob_button.clicked.connect(self.change_mob_for_selected)

        mob_edit_layout.addLayout(mob_select_form)
        mob_edit_layout.addWidget(self.mob_table)
        mob_edit_layout.addWidget(QLabel("To change mob, select animals then enter new mob number:"))
        mob_edit_layout.addWidget(self.new_mob_input)
        mob_edit_layout.addWidget(self.change_mob_button)
        mob_edit_layout.addStretch()

        # Add both layouts to the page
        self.layout().addLayout(animal_edit_layout)
        self.layout().addLayout(mob_edit_layout)

        # Load initial data
        self.load_animal_lists()
        self.load_mobs()

        self.animal_id_combo.currentTextChanged.connect(self.on_select_animal_id)
        self.animal_rfid_combo.currentTextChanged.connect(self.on_select_animal_rfid)

    def refresh_data(self):
        self.load_animal_lists()
        self.load_mobs()
        self.id_display.clear()
        self.id_display.setReadOnly(False)
        self.rfid_display.clear()
        self.rfid_display.setReadOnly(False)
        self.source_pic.clear()
        self.source_name.clear()
        self.source_address.clear()
        self.nvd_in_number.clear()
        self.breed_description.clear()
        self.sex.setCurrentIndex(-1)
        self.mob.clear()
        self.purchase_price.clear()
        self.entry_date.clear()
        self.exit_date_enable.setChecked(False)
        self.exit_date.setEnabled(False)
        self.exit_date.clear()
        self.destination.clear()
        self.sale_price.clear()
        self.nvd_out_number.clear()
        self.status_label.clear()
        self.created_at_label.clear()
        self.last_updated_label.clear()


    def load_animal_lists(self):
        self.id_to_rfid = {}
        self.rfid_to_id = {}
        self.animal_id_combo.blockSignals(True)
        self.animal_rfid_combo.blockSignals(True)
        self.animal_id_combo.clear()
        self.animal_rfid_combo.clear()
        self.animal_id_combo.addItem("")
        self.animal_rfid_combo.addItem("")
        if os.path.exists(CORE_DB_PATH):
            conn = sqlite3.connect(CORE_DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT nlis_id, nlis_rfid FROM cattle_registry")
            rows = cur.fetchall()
            conn.close()
            for nlis_id, nlis_rfid in rows:
                nlis_id = str(nlis_id).upper() if nlis_id else ""
                nlis_rfid = str(nlis_rfid).upper() if nlis_rfid else ""
                if nlis_id:
                    self.animal_id_combo.addItem(nlis_id)
                    self.id_to_rfid[nlis_id] = nlis_rfid
                if nlis_rfid:
                    self.animal_rfid_combo.addItem(nlis_rfid)
                    self.rfid_to_id[nlis_rfid] = nlis_id
        self.animal_id_combo.blockSignals(False)
        self.animal_rfid_combo.blockSignals(False)

    def on_select_animal_id(self, nlis_id):
        nlis_id = nlis_id.strip().upper()
        rfid = self.id_to_rfid.get(nlis_id, "")
        # Set ID/RFID fields
        if nlis_id:
            self.id_display.setText(nlis_id)
            self.id_display.setReadOnly(True)
        else:
            self.id_display.clear()
            self.id_display.setReadOnly(False)
        if rfid:
            self.rfid_display.setText(rfid)
            self.rfid_display.setReadOnly(True)
        else:
            self.rfid_display.clear()
            self.rfid_display.setReadOnly(False)
        self.animal_rfid_combo.blockSignals(True)
        self.animal_rfid_combo.setCurrentText(rfid)
        self.animal_rfid_combo.blockSignals(False)
        self.load_animal_details(nlis_id, rfid)

    def on_select_animal_rfid(self, nlis_rfid):
        nlis_rfid = nlis_rfid.strip().upper()
        nlis_id = self.rfid_to_id.get(nlis_rfid, "")
        if nlis_id:
            self.id_display.setText(nlis_id)
            self.id_display.setReadOnly(True)
        else:
            self.id_display.clear()
            self.id_display.setReadOnly(False)
        if nlis_rfid:
            self.rfid_display.setText(nlis_rfid)
            self.rfid_display.setReadOnly(True)
        else:
            self.rfid_display.clear()
            self.rfid_display.setReadOnly(False)
        self.animal_id_combo.blockSignals(True)
        self.animal_id_combo.setCurrentText(nlis_id)
        self.animal_id_combo.blockSignals(False)
        self.load_animal_details(nlis_id, nlis_rfid)

    def load_animal_details(self, nlis_id, nlis_rfid):
        if not nlis_id and not nlis_rfid:
            return
        if os.path.exists(CORE_DB_PATH):
            conn = sqlite3.connect(CORE_DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                SELECT nlis_id, nlis_rfid, source_pic, source_name, source_address, nvd_in_number, 
                    breed_description, sex, mob, purchase_price,
                    entry_date, exit_date, destination, sale_price, nvd_out_number,
                    status, created_at, last_updated
                FROM cattle_registry
                WHERE (nlis_id = ? AND ? != '') OR (nlis_rfid = ? AND ? != '')
                LIMIT 1
            """, (nlis_id, nlis_id, nlis_rfid, nlis_rfid))
            row = cur.fetchone()
            conn.close()
            if row:
                # Set ID/RFID fields
                if row[0]:
                    self.id_display.setText(str(row[0]))
                    self.id_display.setReadOnly(True)
                else:
                    self.id_display.clear()
                    self.id_display.setReadOnly(False)
                if row[1]:
                    self.rfid_display.setText(str(row[1]))
                    self.rfid_display.setReadOnly(True)
                else:
                    self.rfid_display.clear()
                    self.rfid_display.setReadOnly(False)
                self.source_pic.setText(str(row[2]) if row[2] is not None else "")
                self.source_name.setText(str(row[3]) if row[3] is not None else "")
                self.source_address.setPlainText(str(row[4]) if row[4] is not None else "")
                self.nvd_in_number.setText(str(row[5]) if row[5] is not None else "")
                self.breed_description.setText(str(row[6]) if row[6] is not None else "")
                self.sex.setCurrentText(str(row[7]) if row[7] is not None else "")
                self.mob.setText(str(row[8]) if row[8] is not None else "")
                self.purchase_price.setText("" if row[9] is None else str(row[9]))
                # Populate entry_date widget
                self.entry_date.blockSignals(True)
                if row[10]:
                    try:
                        dt = datetime.datetime.utcfromtimestamp(int(row[10]))
                        self.entry_date.setDate(dt.date())
                    except Exception:
                        self.entry_date.clear()
                else:
                    self.entry_date.clear()
                self.entry_date.blockSignals(False)
                # Populate exit_date widget and checkbox
                self.exit_date.blockSignals(True)
                if row[11]:
                    self.exit_date_enable.setChecked(True)
                    self.exit_date.setEnabled(True)
                    try:
                        dt = datetime.datetime.utcfromtimestamp(int(row[11]))
                        self.exit_date.setDate(dt.date())
                    except Exception:
                        self.exit_date.clear()
                else:
                    self.exit_date_enable.setChecked(False)
                    self.exit_date.setEnabled(False)
                    self.exit_date.clear()
                self.exit_date.blockSignals(False)
                self.destination.setText(str(row[12]) if row[12] is not None else "")
                self.sale_price.setText("" if row[13] is None else str(row[13]))
                self.nvd_out_number.setText(str(row[14]) if row[14] is not None else "")
                self.status_label.setText(str(row[15]) if row[15] is not None else "")
                # Format 'created_at' and 'last_updated' as dd/mm/yyyy
                if row[16]:
                    try:
                        dt = datetime.datetime.utcfromtimestamp(int(row[16]))
                        self.created_at_label.setText(dt.strftime("%d/%m/%Y"))
                    except Exception:
                        self.created_at_label.setText(str(row[16]))
                else:
                    self.created_at_label.setText("")
                if row[17]:
                    try:
                        dt = datetime.datetime.utcfromtimestamp(int(row[17]))
                        self.last_updated_label.setText(dt.strftime("%d/%m/%Y"))
                    except Exception:
                        self.last_updated_label.setText(str(row[17]))
                else:
                    self.last_updated_label.setText("")
            else:
                self.id_display.clear()
                self.id_display.setReadOnly(False)
                self.rfid_display.clear()
                self.rfid_display.setReadOnly(False)
                self.source_pic.clear()
                self.source_name.clear()
                self.source_address.clear()
                self.nvd_in_number.clear()
                self.breed_description.clear()
                self.sex.setCurrentIndex(-1)
                self.mob.clear()
                self.purchase_price.clear()
                self.entry_date.clear()
                self.exit_date_enable.setChecked(False)
                self.exit_date.setEnabled(False)
                self.exit_date.clear()
                self.destination.clear()
                self.sale_price.clear()
                self.nvd_out_number.clear()
                self.status_label.clear()
                self.created_at_label.clear()
                self.last_updated_label.clear()

    def save_animal_edits(self):
        nlis_id = self.id_display.text().strip().upper()
        nlis_rfid = self.rfid_display.text().strip().upper()
        if not nlis_id and not nlis_rfid:
            QMessageBox.warning(self, "No Animal Selected", "Select an animal first.")
            return
        # Only allow editing non-ID fields
        update_fields = {
            "nlis_id": nlis_id,
            "nlis_rfid": nlis_rfid,
            "source_pic": self.source_pic.text().strip(),
            "source_name": self.source_name.text().strip(),
            "source_address": self.source_address.toPlainText().strip(),
            "nvd_in_number": self.nvd_in_number.text().strip(),
            "breed_description": self.breed_description.text().strip(),
            "sex": self.sex.currentText().strip(),
            "mob": self.mob.text().strip(),
            "purchase_price": self.purchase_price.text().strip(),
            "destination": self.destination.text().strip(),
            "sale_price": self.sale_price.text().strip(),
            "nvd_out_number": self.nvd_out_number.text().strip(),
            "status": self.status_label.text().strip(),
            "created_at": self.created_at_label.text().strip(),
            # "last_updated" will be set to the new unix timestamp
        }
        # Save entry_date and exit_date as unix timestamp, allow blank
        if self.entry_date.date().isValid() and self.entry_date.text():
            dt = self.entry_date.date().toPyDate()
            update_fields["entry_date"] = int(datetime.datetime(dt.year, dt.month, dt.day).timestamp())
        else:
            update_fields["entry_date"] = None

        if self.exit_date_enable.isChecked() and self.exit_date.date().isValid() and self.exit_date.text():
            dt = self.exit_date.date().toPyDate()
            update_fields["exit_date"] = int(datetime.datetime(dt.year, dt.month, dt.day).timestamp())
        else:
            update_fields["exit_date"] = None

        # Validate int/float fields
        for fld in ["purchase_price", "sale_price"]:
            try:
                if update_fields[fld]:
                    update_fields[fld] = float(update_fields[fld])
                else:
                    update_fields[fld] = None
            except ValueError:
                QMessageBox.warning(self, "Invalid Value", f"{fld.replace('_',' ').title()} must be a number.")
                return
        for fld in ["nvd_in_number", "nvd_out_number", "created_at"]:
            val = update_fields[fld]
            if val == "":
                update_fields[fld] = None
            else:
                try:
                    update_fields[fld] = int(val)
                except ValueError:
                    update_fields[fld] = val

        # Status check based on exit_date
        now_ts = int(time.time())
        exit_date_val = update_fields.get("exit_date")
        if not exit_date_val:
            update_fields["status"] = "ACTIVE"
        else:
            try:
                exit_ts = int(exit_date_val)
                if exit_ts <= now_ts:
                    update_fields["status"] = "INACTIVE"
                else:
                    update_fields["status"] = "ACTIVE"
            except Exception:
                update_fields["status"] = "ACTIVE"

        unix_ts = int(time.time())
        update_fields["last_updated"] = unix_ts  # Set last_updated to be same as file name

        # Write JSON file for update log as an array
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR)
        filename = f"{unix_ts}_cattle_update_log.json"
        filepath = os.path.join(UPLOAD_DIR, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump([update_fields], f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to write update log:\n{e}")
            return

        # Update the DB with the new data and last_updated
        sets = ", ".join([f"{k}=?" for k in update_fields])
        values = list(update_fields.values())
        if os.path.exists(CORE_DB_PATH):
            conn = sqlite3.connect(CORE_DB_PATH)
            cur = conn.cursor()
            cur.execute(
                f"UPDATE cattle_registry SET {sets} WHERE (nlis_id=? AND ?!='') OR (nlis_rfid=? AND ?!='')",
                values + [nlis_id, nlis_id, nlis_rfid, nlis_rfid]
            )
            conn.commit()
            conn.close()

        # Call merge script after saving
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

        QMessageBox.information(self, "Saved", "Animal update saved to upload queue and merge run.")
        self.load_animal_lists()
        self.load_animal_details(nlis_id, nlis_rfid)
        self.load_mobs()

    def load_mobs(self):
        self.mob_combo.clear()
        mobs = set()
        if os.path.exists(CORE_DB_PATH):
            try:
                conn = sqlite3.connect(CORE_DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT DISTINCT mob FROM cattle_registry WHERE mob IS NOT NULL AND mob != ''")
                mobs = sorted(str(row[0]) for row in cur.fetchall())
                conn.close()
            except Exception:
                pass
        self.mob_combo.addItems(mobs)

    def load_mob_animals(self):
        mob_number = self.mob_combo.currentText().strip()
        self.mob_table.setRowCount(0)
        if not mob_number:
            return
        animals = []
        if os.path.exists(CORE_DB_PATH):
            conn = sqlite3.connect(CORE_DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                SELECT nlis_id, nlis_rfid, breed_description, sex, mob
                FROM cattle_registry
                WHERE mob=?
            """, (mob_number,))
            animals = cur.fetchall()
            conn.close()
        self.mob_table.setRowCount(len(animals))
        for row_idx, row in enumerate(animals):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox.setCheckState(Qt.Unchecked)
            self.mob_table.setItem(row_idx, 0, checkbox)
            for col, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.mob_table.setItem(row_idx, col+1, item)

    def change_mob_for_selected(self):
        new_mob = self.new_mob_input.text().strip().upper()
        if not new_mob:
            QMessageBox.warning(self, "No Mob", "Enter a new mob number.")
            return

        updates = []
        unix_ts = int(time.time())
        changed_count = 0

        for row in range(self.mob_table.rowCount()):
            item = self.mob_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                nlis_id = self.mob_table.item(row, 1).text().strip()
                nlis_rfid = self.mob_table.item(row, 2).text().strip()
                animal_update = {
                    "nlis_id": nlis_id,
                    "nlis_rfid": nlis_rfid,
                    "mob": new_mob,
                    "last_updated": unix_ts
                }
                if os.path.exists(CORE_DB_PATH):
                    conn = sqlite3.connect(CORE_DB_PATH)
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT source_pic, source_name, source_address, nvd_in_number, breed_description, sex, purchase_price, entry_date, exit_date, destination, sale_price, nvd_out_number, status, created_at FROM cattle_registry WHERE (nlis_id=? AND ?!='') OR (nlis_rfid=? AND ?!='') LIMIT 1",
                        (nlis_id, nlis_id, nlis_rfid, nlis_rfid)
                    )
                    rowdata = cur.fetchone()
                    conn.close()
                    if rowdata:
                        (
                            animal_update["source_pic"],
                            animal_update["source_name"],
                            animal_update["source_address"],
                            animal_update["nvd_in_number"],
                            animal_update["breed_description"],
                            animal_update["sex"],
                            animal_update["purchase_price"],
                            animal_update["entry_date"],
                            animal_update["exit_date"],
                            animal_update["destination"],
                            animal_update["sale_price"],
                            animal_update["nvd_out_number"],
                            animal_update["status"],
                            animal_update["created_at"]
                        ) = rowdata
                updates.append(animal_update)
                if os.path.exists(CORE_DB_PATH):
                    conn = sqlite3.connect(CORE_DB_PATH)
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE cattle_registry SET mob=?, last_updated=? WHERE (nlis_id=? AND ?!='') OR (nlis_rfid=? AND ?!='')",
                        (new_mob, unix_ts, nlis_id, nlis_id, nlis_rfid, nlis_rfid)
                    )
                    conn.commit()
                    conn.close()
                changed_count += 1

        if changed_count > 0:
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR)
            filename = f"{unix_ts}_cattle_update_log.json"
            filepath = os.path.join(UPLOAD_DIR, filename)
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(updates, f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write update log:\n{e}")
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

            QMessageBox.information(self, "Mob Updated", f"Mob updated for {changed_count} animal(s), update queued and merged.")
            self.load_mob_animals()
            self.load_mobs()