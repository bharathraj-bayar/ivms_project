import os
import sys
import json
from datetime import datetime, timezone

# Add project root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_conn

def inspect():
    conn = get_conn()
    cur = conn.cursor()
    
    imei = "864275071199007"
    
    # 1. Fetch live_vehicle_status row
    cur.execute("SELECT * FROM live_vehicle_status WHERE imei = %s", (imei,))
    lvs_row = cur.fetchone()
    if lvs_row:
        colnames = [desc[0] for desc in cur.description]
        lvs_dict = dict(zip(colnames, lvs_row))
        print("--- live_vehicle_status Row ---")
        for k, v in lvs_dict.items():
            print(f"{k}: {v}")
            
    # 2. Fetch all telemetry records today
    cur.execute("""
        SELECT id, device_id, timestamp, priority, longitude, latitude, speed, io_elements
        FROM telemetry
        WHERE imei = %s
        ORDER BY timestamp DESC LIMIT 20
    """, (imei,))
    tel_rows = cur.fetchall()
    print("\n--- Telemetry Records (Latest 20) ---")
    for row in tel_rows:
        colnames = [desc[0] for desc in cur.description]
        d = dict(zip(colnames, row))
        io = d['io_elements']
        if isinstance(io, str):
            io = json.loads(io)
        ign = io.get('239', io.get('1', '0'))
        print(f"id: {d['id']} | ts: {d['timestamp']} | lat: {d['latitude']} | lon: {d['longitude']} | speed: {d['speed']} | ign: {ign}")
        
    # 3. Check if there are entries in live_position_updates for this IMEI
    cur.execute("""
        SELECT * FROM live_position_updates
        WHERE imei = %s
        ORDER BY new_timestamp DESC LIMIT 10
    """, (imei,))
    lpu_rows = cur.fetchall()
    print("\n--- live_position_updates (Latest 10) ---")
    for row in lpu_rows:
        colnames = [desc[0] for desc in cur.description]
        d = dict(zip(colnames, row))
        print(d)

    # 4. Check if there are any devices table entries for this IMEI
    cur.execute("SELECT * FROM devices WHERE imei = %s", (imei,))
    dev_row = cur.fetchone()
    if dev_row:
        colnames = [desc[0] for desc in cur.description]
        print(f"\n--- devices entry: {dict(zip(colnames, dev_row))} ---")

    cur.close()
    conn.close()

if __name__ == "__main__":
    inspect()
