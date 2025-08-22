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

def upsert_cattle_registry(conn, record):
    cursor = conn.cursor()
    now_int = int(time.time())

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

    cursor.execute(f"SELECT * FROM cattle_registry WHERE {id_field} = ?", (id_value,))
    exists = cursor.fetchone()

    update_fields = []
    update_values = []
    for k, v in record.items():
        if k in ["nlis_id", "nlis_rfid"]:
            continue
        update_fields.append(f"{k} = ?")
        update_values.append(v)
    update_fields.append("last_updated = ?")
    update_values.append(now_int)

    if exists:
        sql = f"UPDATE cattle_registry SET {', '.join(update_fields)} WHERE {id_field} = ?"
        update_values.append(id_value)
        cursor.execute(sql, update_values)
    else:
        insert_fields = list(record.keys())
        insert_values = [record[k] for k in insert_fields]
        if "created_at" not in insert_fields:
            insert_fields.append("created_at")
            insert_values.append(now_int)
        if "last_updated" not in insert_fields:
            insert_fields.append("last_updated")
            insert_values.append(now_int)
        sql = f"INSERT INTO cattle_registry ({', '.join(insert_fields)}) VALUES ({', '.join(['?']*len(insert_fields))})"
        cursor.execute(sql, insert_values)
    conn.commit()

def merge_feed_stock(conn, record):
    cursor = conn.cursor()
    # Remove mode
    if record.get("remove") and record.get("commodity"):
        cursor.execute(
            "DELETE FROM feed_stock WHERE UPPER(commodity)=?",
            (record.get("commodity").upper(),)
        )
        conn.commit()
        return

    cursor.execute("""
        SELECT id FROM feed_stock WHERE
        commodity=? AND feed_type=? AND price_per_unit=?
    """, (
        record.get("commodity"),
        record.get("feed_type"),
        record.get("price_per_unit")
    ))
    exists = cursor.fetchone()
    fields = [
        "commodity", "feed_type", "unit_qty", "kg_per_unit", "price_per_unit",
        "total_kg", "feed_price_per_kg", "total_feed_value"
    ]
    values = [record.get(f) for f in fields]
    if exists:
        cursor.execute("""
            UPDATE feed_stock SET
            unit_qty=?, kg_per_unit=?, total_kg=?, feed_price_per_kg=?, total_feed_value=?
            WHERE id=?
        """, [
            record.get("unit_qty"),
            record.get("kg_per_unit"),
            record.get("total_kg"),
            record.get("feed_price_per_kg"),
            record.get("total_feed_value"),
            exists[0]
        ])
    else:
        cursor.execute(f"""
            INSERT INTO feed_stock
            ({', '.join(fields)})
            VALUES ({', '.join(['?']*len(fields))})
        """, values)
    conn.commit()

def merge_treatment(conn, record):
    cursor = conn.cursor()
    now_int = int(time.time())
    insert_fields = []
    insert_values = []
    for field in ["id", "nlis_id", "event_date", "event_type", "product_name", "amount", "unit", "cost_per_unit", "paddock", "notes", "source", "import_batch", "mob"]:
        if field in record:
            insert_fields.append(field)
            insert_values.append(record[field])
    if "event_type" not in insert_fields:
        insert_fields.append("event_type")
        insert_values.append("MEDICATION")
    if "id" not in insert_fields:
        insert_fields.append("id")
        insert_values.append(str(now_int) + "_" + (record.get("nlis_id") or record.get("mob", "")))
    sql = f"INSERT OR REPLACE INTO cattle_log ({', '.join(insert_fields)}) VALUES ({', '.join(['?']*len(insert_fields))})"
    cursor.execute(sql, insert_values)
    conn.commit()

def merge_paddock(conn, record):
    cursor = conn.cursor()
    insert_fields = []
    insert_values = []
    for field in ["id", "mob", "paddock_id", "start_date", "end_date", "estimated_headcount"]:
        if field in record:
            insert_fields.append(field)
            insert_values.append(record[field])
    if "id" not in insert_fields:
        now_int = int(time.time())
        insert_fields.append("id")
        insert_values.append(str(now_int) + "_" + record.get("mob", ""))
    sql = f"INSERT OR REPLACE INTO herd_paddock_assignments ({', '.join(insert_fields)}) VALUES ({', '.join(['?']*len(insert_fields))})"
    cursor.execute(sql, insert_values)
    conn.commit()

def merge_chemical_inventory(conn, record):
    cursor = conn.cursor()
    now_int = int(time.time())
    # Try to find a product by product_name and batch_number
    cursor.execute("SELECT id FROM chemical_inventory WHERE product_name=? AND batch_number=?", (record.get("product_name", ""), record.get("batch_number", "")))
    exists = cursor.fetchone()
    fields = [
        "date_received", "product_name", "form", "unit", "package_size", "package_type",
        "quantity", "total_quantity", "price_per_unit", "total_value",
        "batch_number", "expiry_date", "dom_date", "application_type", "withholding_period", "notes", "last_updated", "created_at"
    ]
    values = [record.get(f) for f in fields]
    # Set last_updated and created_at if not present
    if not record.get("last_updated"):
        values[fields.index("last_updated")] = now_int
    if not record.get("created_at"):
        values[fields.index("created_at")] = now_int
    if exists:
        set_fields = [f"{f}=?" for f in fields if f not in ["created_at"]]
        set_values = [record.get(f) if record.get(f) is not None else (now_int if f=="last_updated" else None) for f in fields if f != "created_at"]
        set_values.append(exists[0])
        cursor.execute(
            f"UPDATE chemical_inventory SET {', '.join(set_fields)} WHERE id=?",
            set_values)
    else:
        cursor.execute(
            f"INSERT INTO chemical_inventory ({', '.join(fields)}) VALUES ({', '.join(['?']*len(fields))})",
            values)
    conn.commit()

def merge_chemical_log(conn, record):
    cursor = conn.cursor()
    now_int = int(time.time())
    insert_fields = []
    insert_values = []
    for field in [
        "id", "event_date", "product_name", "batch_number", "amount_used", "unit",
        "price_per_unit", "value_applied", "application_type", "mob", "nlis_id", "notes", "last_updated"
    ]:
        if field in record:
            insert_fields.append(field)
            insert_values.append(record[field])
    if "id" not in insert_fields:
        insert_fields.append("id")
        insert_values.append(str(now_int) + "_" + (record.get("mob") or record.get("nlis_id", "")))
    if "event_date" not in insert_fields:
        insert_fields.append("event_date")
        insert_values.append(now_int)
    sql = f"INSERT OR REPLACE INTO chemical_log ({', '.join(insert_fields)}) VALUES ({', '.join(['?']*len(insert_fields))})"
    cursor.execute(sql, insert_values)
    conn.commit()

def process_section(conn, section_name, records):
    entries_imported = 0
    errors = []
    if not isinstance(records, list):
        errors.append(f"Section {section_name} is not a list.")
        return entries_imported, errors
    for record in records:
        try:
            if section_name == "animal_updates":
                upsert_cattle_registry(conn, record)
            elif section_name == "feed_updates":
                merge_feed_stock(conn, record)
            elif section_name == "treatment_update":
                merge_treatment(conn, record)
            elif section_name == "paddock_update":
                merge_paddock(conn, record)
            elif section_name == "chemical_inventory":
                merge_chemical_inventory(conn, record)
            elif section_name == "chemical_log":
                merge_chemical_log(conn, record)
            else:
                errors.append(f"Unknown section: {section_name}")
                continue
            entries_imported += 1
        except Exception as e:
            errors.append(f"{section_name} error: {e}")
    return entries_imported, errors

def process_file(conn, filepath):
    entries_imported = 0
    errors = []
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            return 0, [f"JSON load error: {e}"]

    # Accept both the new dict structure and legacy flat list
    if isinstance(data, dict):
        for section in [
            "animal_updates", "feed_updates", "treatment_update",
            "paddock_update", "chemical_inventory", "chemical_log"
        ]:
            if section in data:
                imported, section_errors = process_section(conn, section, data[section])
                entries_imported += imported
                errors.extend(section_errors)
    elif isinstance(data, list):
        for record in data:
            try:
                chem_keys = set([
                    "date_received", "product_name", "form", "unit", "package_size", "package_type",
                    "quantity", "total_quantity", "price_per_unit", "total_value",
                    "batch_number", "expiry_date", "dom_date", "application_type", "withholding_period", "notes"
                ])
                chemical_log_keys = set([
                    "event_date", "product_name", "batch_number", "amount_used", "unit",
                    "price_per_unit", "value_applied", "application_type", "mob", "nlis_id", "notes"
                ])
                if chem_keys.issubset(set(record.keys())):
                    merge_chemical_inventory(conn, record)
                elif chemical_log_keys & set(record.keys()):
                    merge_chemical_log(conn, record)
                elif "commodity" in record and "feed_type" in record:
                    merge_feed_stock(conn, record)
                elif "nlis_id" in record or "nlis_rfid" in record:
                    upsert_cattle_registry(conn, record)
                elif "event_type" in record and record["event_type"] in ("MEDICATION", "TREATMENT"):
                    merge_treatment(conn, record)
                elif "mob" in record and "paddock_id" in record:
                    merge_paddock(conn, record)
                else:
                    errors.append(f"Unknown record type: {record}")
                    continue
                entries_imported += 1
            except Exception as e:
                errors.append(f"Flat record error: {e}")
    else:
        errors.append("JSON file must contain a list or a dict with update sections.")

    return entries_imported, errors

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
        log_merge_event(conn, file, imported, "\n".join(error_log))
        print(f"Imported {imported} entries from {file}")
        if error_log:
            print(f"Errors:\n{error_log}")
        shutil.move(filepath, os.path.join(PROCESSED_DIR, file))
    conn.close()

if __name__ == "__main__":
    main()