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

def merge_general(conn, record):
    cursor = conn.cursor()
    now_int = int(time.time())

    # Try to identify the record
    id_field = None
    id_value = None
    if "nlis_id" in record and record["nlis_id"]:
        id_field = "nlis_id"
        id_value = record["nlis_id"]
    elif "nlis_rfid" in record and record["nlis_rfid"]:
        id_field = "nlis_rfid"
        id_value = record["nlis_rfid"]
    else:
        raise ValueError("No identifier (nlis_id or nlis_rfid) present in record.")

    # Check if record exists
    cursor.execute(f"SELECT * FROM cattle_registry WHERE {id_field} = ?", (id_value,))
    exists = cursor.fetchone()

    # Build the SET clause or columns/values for update/insert
    update_fields = []
    update_values = []
    for k, v in record.items():
        # Don't update the identifier field itself
        if k in ["nlis_id", "nlis_rfid"]:
            continue
        update_fields.append(f"{k} = ?")
        update_values.append(v)
    update_fields.append("last_updated = ?")
    update_values.append(now_int)

    if exists:
        # Update only specified fields
        sql = f"UPDATE cattle_registry SET {', '.join(update_fields)} WHERE {id_field} = ?"
        update_values.append(id_value)
        cursor.execute(sql, update_values)
    else:
        # Insert new record with all provided fields + id fields
        insert_fields = list(record.keys())
        insert_values = [record[k] for k in insert_fields]
        # Make sure last_updated and created_at are present
        if "created_at" not in insert_fields:
            insert_fields.append("created_at")
            insert_values.append(now_int)
        if "last_updated" not in insert_fields:
            insert_fields.append("last_updated")
            insert_values.append(now_int)
        sql = f"INSERT INTO cattle_registry ({', '.join(insert_fields)}) VALUES ({', '.join(['?']*len(insert_fields))})"
        cursor.execute(sql, insert_values)
    conn.commit()

def process_file(conn, filepath):
    entries_imported = 0
    errors = []

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            return 0, f"JSON load error: {e}"

    # Accept both single-dict and list-of-dicts input for flexibility
    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        return 0, "JSON file must contain a list or a single object."

    for record in data:
        try:
            merge_general(conn, record)
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