import os
import json
import sqlite3
import shutil
import time
from datetime import datetime

DATA_DIR = r"C:\ProgramData\StockLOG"
UPLOAD_DIR = os.path.join(DATA_DIR, "UploadQueue")
CORE_DIR = os.path.join(DATA_DIR, "Core")
MASTER_DB = os.path.join(CORE_DIR, "master.db")
PROCESSED_DIR = os.path.join(UPLOAD_DIR, "processed")

def init_processed_dir():
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

def log_merge_event(conn, filename, entries_imported, error_log):
    timestamp = int(time.time())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO merge_log (id, filename, timestamp, entries_imported, error_log)
        VALUES (?, ?, ?, ?, ?)
    """, (str(timestamp) + filename, filename, datetime.now().isoformat(), entries_imported, error_log))
    conn.commit()

def merge_entry(conn, entry):
    cursor = conn.cursor()
    nlis_id = entry.get("nlis_id")
    if not nlis_id:
        raise ValueError("Entry missing NLIS ID")

    # Check if animal exists already in registry
    cursor.execute("SELECT nlis_id FROM cattle_registry WHERE nlis_id = ?", (nlis_id,))
    exists = cursor.fetchone()

    if exists:
        # Update existing record (now includes nlis_rfid)
        cursor.execute("""
            UPDATE cattle_registry SET
                entry_date = ?,
                nlis_rfid = ?,
                source_pic = ?,
                source_name = ?,
                source_address = ?,
                nvd_in_number = ?,
                breed_description = ?,
                sex = ?,
                mob = ?,
                purchase_price = ?,
                status = 'active',
                last_updated = ?
            WHERE nlis_id = ?
        """, (
            entry.get("entry_date"),
            entry.get("nlis_rfid"),
            entry.get("source_pic"),
            entry.get("source_name"),
            entry.get("source_address"),
            entry.get("nvd_in_number"),
            entry.get("breed_description"),
            entry.get("sex"),
            entry.get("mob"),
            entry.get("purchase_price"),
            datetime.now().isoformat(),
            nlis_id
        ))
    else:
        # Insert new record (now includes nlis_rfid)
        cursor.execute("""
            INSERT INTO cattle_registry (
                nlis_id, nlis_rfid, entry_date, source_pic, source_name, source_address, 
                nvd_in_number, breed_description, sex, mob, purchase_price, status,
                created_at, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (
            nlis_id,
            entry.get("nlis_rfid"),
            entry.get("entry_date"),
            entry.get("source_pic"),
            entry.get("source_name"),
            entry.get("source_address"),
            entry.get("nvd_in_number"),
            entry.get("breed_description"),
            entry.get("sex"),
            entry.get("mob"),
            entry.get("purchase_price"),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
    conn.commit()

def merge_exit(conn, exit_entry):
    cursor = conn.cursor()
    nlis_id = exit_entry.get("nlis_id")
    if not nlis_id:
        raise ValueError("Exit entry missing NLIS ID")

    # Update cattle_registry to mark sold/dead and fill exit fields
    cursor.execute("""
        UPDATE cattle_registry SET
            exit_date = ?,
            destination = ?,
            sale_price = ?,
            nvd_out_number = ?,
            status = 'sold',
            last_updated = ?
        WHERE nlis_id = ?
    """, (
        exit_entry.get("exit_date"),
        exit_entry.get("destination"),
        exit_entry.get("sale_price"),
        exit_entry.get("nvd_out_number"),
        datetime.now().isoformat(),
        nlis_id
    ))
    conn.commit()

def process_file(conn, filepath):
    entries_imported = 0
    errors = []

    with open(filepath, "r") as f:
        try:
            data = json.load(f)
        except Exception as e:
            return 0, f"JSON load error: {e}"

    for record in data:
        try:
            # Decide if entry or exit by keys present
            if "entry_date" in record:
                merge_entry(conn, record)
            elif "exit_date" in record:
                merge_exit(conn, record)
            else:
                errors.append(f"Unknown record type in {filepath}: {record}")
            entries_imported += 1
        except Exception as e:
            errors.append(str(e))

    return entries_imported, "\n".join(errors)

def main():
    init_processed_dir()

    if not os.path.exists(MASTER_DB):
        print("master.db not found!")
        return

    conn = sqlite3.connect(MASTER_DB)

    files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".json")]
    if not files:
        print("No JSON files to process.")
        return

    for file in files:
        filepath = os.path.join(UPLOAD_DIR, file)
        print(f"Processing {file} ...")
        imported, error_log = process_file(conn, filepath)
        log_merge_event(conn, file, imported, error_log)
        print(f"Imported {imported} entries from {file}")
        if error_log:
            print(f"Errors:\n{error_log}")

        # Move processed file
        shutil.move(filepath, os.path.join(PROCESSED_DIR, file))

    conn.close()

if __name__ == "__main__":
    main()