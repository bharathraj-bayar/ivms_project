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
    
    imeis = ["864275071330206", "864275071228707", "864275071199007", "864275071226750", "864275071210218", "864275071217296"]
    
    print(f"{'IMEI':<16} | {'status':<12} | {'last_telemetry_id':<18} | {'last_timestamp':<30} | {'latitude':<10} | {'longitude':<10}")
    print("-"*110)
    for imei in imeis:
        cur.execute("SELECT status, last_telemetry_id, last_timestamp, latitude, longitude FROM live_vehicle_status WHERE imei = %s", (imei,))
        row = cur.fetchone()
        if row:
            print(f"{imei:<16} | {str(row[0]):<12} | {str(row[1]):<18} | {str(row[2]):<30} | {str(row[3]):<10} | {str(row[4]):<10}")
        else:
            print(f"{imei:<16} | NOT FOUND")
            
    print("\n--- Count of live_position_updates per IMEI ---")
    for imei in imeis:
        cur.execute("SELECT COUNT(*) FROM live_position_updates WHERE imei = %s", (imei,))
        cnt = cur.fetchone()[0]
        print(f"IMEI {imei}: {cnt} updates in log")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    inspect()
