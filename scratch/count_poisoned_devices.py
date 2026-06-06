import os
import sys

# Add project root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_conn

def count_poisoned():
    conn = get_conn()
    cur = conn.cursor()
    
    # 1. Total devices with NULL last_telemetry_id in live_vehicle_status
    cur.execute("""
        SELECT imei, status, last_timestamp, updated_at 
        FROM live_vehicle_status 
        WHERE last_telemetry_id IS NULL
    """)
    rows = cur.fetchall()
    
    print(f"Total affected devices: {len(rows)}")
    print(f"\nList of affected devices:")
    print(f"{'IMEI':<16} | {'Status':<12} | {'Last Timestamp':<30} | {'Updated At':<30}")
    print("-"*96)
    
    first_occurrence = None
    for r in rows:
        print(f"{r[0]:<16} | {str(r[1]):<12} | {str(r[2]):<30} | {str(r[3]):<30}")
        if r[3]:
            if first_occurrence is None or r[3] < first_occurrence:
                first_occurrence = r[3]
                
    print(f"\nFirst occurrence timestamp (oldest updated_at among affected devices): {first_occurrence}")
    
    # Let's count how many total devices are in live_vehicle_status to check the percentage of affected devices
    cur.execute("SELECT COUNT(*) FROM live_vehicle_status")
    total_devices = cur.fetchone()[0]
    print(f"Total devices in live_vehicle_status: {total_devices}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    count_poisoned()
