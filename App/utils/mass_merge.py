import csv
import json
from datetime import datetime

csv_path = "massupload.csv"
entry_json = "massupload_Cattle_Entry_Batch.json"
exit_json = "massupload_Cattle_Exit_Batch.json"

def parse_date(datestr):
    if not datestr or not datestr.strip():
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return int(datetime.strptime(datestr.strip(), fmt).timestamp())
        except Exception:
            continue
    return None

def parse_price(pricestr):
    if not pricestr or not pricestr.strip():
        return 0.0
    s = pricestr.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except Exception:
        return 0.0

entry_batch = []
exit_batch = []

with open(csv_path, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # ENTRY FORMAT
        entry = {
            "nlis_id": row.get("NLIS ID NO.", "").strip(),
            "nlis_rfid": row.get("NLIS RFID NO.", "").strip(),
            "entry_date": parse_date(row.get("FARM ENTRY DATE", "")),
            "source_pic": row.get("SOURCE PIC", "").strip(),
            "source_name": row.get("SOURCE NAME", "").strip(),
            "source_address": row.get("SOURCE ADRRESS", "").strip(),
            "nvd_in_number": row.get("NVD IN NO.", "").strip(),
            "breed_description": row.get("BREED/DESCRIPTION", "").strip(),
            "sex": row.get("SEX", "").strip(),
            "mob": row.get("MOB NUMBER", "").strip(),
            "purchase_price": parse_price(row.get(" COST (inc GST) ", "")),
            "status": row.get("STATUS", "").strip(),
            "created_at": parse_date(row.get("DATE ADDED", "")),
            "last_updated": parse_date(row.get("LAST UPDATE", "")),
        }
        entry = {k: v for k, v in entry.items() if v not in ["", None]}
        if entry.get("nlis_id"):
            entry_batch.append(entry)

        # EXIT FORMAT (only if exit info is present)
        exit_date = parse_date(row.get("FARM EXIT DATE", ""))
        destination = row.get("DESTINATION", "").strip()
        sale_price = parse_price(row.get("SALE PRICE", ""))
        nvd_out_number = row.get("NVD OUT NO.", "").strip()
        if exit_date or destination or sale_price or nvd_out_number:
            if row.get("NLIS ID NO.", "").strip():
                exit_obj = {
                    "nlis_id": row.get("NLIS ID NO.", "").strip(),
                    "exit_date": exit_date,
                    "destination": destination or None,
                    "sale_price": sale_price,
                    "nvd_out_number": nvd_out_number or None
                }
                # Only include if exit_date or destination or sale_price or nvd_out_number is set
                # (Prevents empty exits)
                exit_batch.append({k: v for k, v in exit_obj.items() if v not in ["", None]})

if entry_batch:
    with open(entry_json, "w", encoding="utf-8") as f:
        json.dump(entry_batch, f, indent=2)
    print(f"✅ Wrote {len(entry_batch)} entries to {entry_json}")
else:
    print("No valid entries for entry batch.")

if exit_batch:
    with open(exit_json, "w", encoding="utf-8") as f:
        json.dump(exit_batch, f, indent=2)
    print(f"✅ Wrote {len(exit_batch)} exits to {exit_json}")
else:
    print("No exit records found.")