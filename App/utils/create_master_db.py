import sqlite3
import os

# Use the actual absolute NAS path (not ~)
core_dir = "C:\ProgramData\StockLOG\Core"
os.makedirs(core_dir, exist_ok=True)

# Path to the master database
db_path = os.path.join(core_dir, "master.db")

# Connect and create cursor
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables
cursor.executescript("""

CREATE TABLE IF NOT EXISTS cattle_registry (
    nlis_id TEXT PRIMARY KEY,
    nlis_rfid INTEGER,
    entry_date INTEGER,              
    source_pic TEXT,
    source_name TEXT,
    source_address TEXT,
    nvd_in_number INTEGER,
    breed_description TEXT,
    sex TEXT,
    mob TEXT,
    purchase_price REAL,
    exit_date INTEGER,
    destination TEXT,
    sale_price REAL,
    nvd_out_number INTEGER,
    status TEXT,
    created_at INTEGER,
    last_updated INTEGER
);

CREATE TABLE IF NOT EXISTS cattle_log (
    id TEXT PRIMARY KEY,
    nlis_id TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_type TEXT,
    product_barcode TEXT,
    product_name TEXT,
    amount REAL,
    unit TEXT,
    cost_per_unit REAL,
    paddock TEXT,
    notes TEXT,
    source TEXT,
    import_batch TEXT,
    FOREIGN KEY (nlis_id) REFERENCES cattle_registry(nlis_id)
);

CREATE TABLE IF NOT EXISTS products (
    barcode TEXT PRIMARY KEY,
    name TEXT,
    category TEXT,
    default_unit TEXT,
    default_cost_per_unit REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS paddocks (
    id TEXT PRIMARY KEY,
    name TEXT,
    area_ha REAL,
    daily_cost_per_head REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS herd_paddock_assignments (
    id TEXT PRIMARY KEY,
    mob TEXT,
    paddock_id TEXT,
    start_date TEXT,
    end_date TEXT,
    estimated_headcount INTEGER,
    FOREIGN KEY (paddock_id) REFERENCES paddocks(id)
);

CREATE TABLE IF NOT EXISTS merge_log (
    id TEXT PRIMARY KEY,
    filename TEXT,
    timestamp TEXT,
    entries_imported INTEGER,
    error_log TEXT
);

""")

# Commit and close
conn.commit()
conn.close()

print(f"✅ Database created at {db_path}")
