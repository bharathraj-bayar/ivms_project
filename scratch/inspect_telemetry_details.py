import os
import sys
import json
from datetime import datetime, timezone

# Add project root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_conn
from services.time_service import get_period_dates
from services.native_report_service import native_report_service

def inspect_details():
    conn = get_conn()
    cur = conn.cursor()
    
    start_dt, end_dt = get_period_dates('Today')
    print(f"Oman window: {start_dt} to {end_dt}")
    print(f"UTC window: {start_dt.astimezone(timezone.utc)} to {end_dt.astimezone(timezone.utc)}")
    
    # Let's inspect the target vehicles data structure for get_fleet_summary
    target_imeis = ["864275071330206", "864275071228707", "864275071199007"]
    working_imeis = ["864275071226750", "864275071210218", "864275071217296"]
    all_imeis = target_imeis + working_imeis
    
    vehicles_data = []
    for imei in all_imeis:
        cur.execute("SELECT name, unique_id, company_name FROM vehicles WHERE unique_id = %s", (imei,))
        row = cur.fetchone()
        if row:
            vehicles_data.append({
                "name": row[0],
                "unique_id": row[1],
                "company_name": row[2]
            })
            
    print("\n" + "="*80)
    print("PROGRAMMATIC ANALYTICS AGGREGATION OUTPUT")
    print("="*80)
    summaries = native_report_service.get_fleet_summary(vehicles_data, start_dt, end_dt)
    for s in summaries:
        print(f"IMEI: {s['unique_id']} ({s['name']})")
        print(f"  - Total Distance: {s['total_distance']} km")
        print(f"  - Max Speed: {s['max_speed']} km/h")
        print(f"  - Average Speed: {s['average_speed']} km/h")
        print(f"  - Idle Duration: {s['idle_duration']/1000} s")
        print(f"  - Engine Hours: {s['engine_hours']} hrs")
        print(f"  - Status: {s['status']}")
        print(f"  - Insight: {s['insight']}")
        print(f"  - Fuel Liters: {s['fuel_liters']} L")
        
    print("\n" + "="*80)
    print("TELEMETRY SAMPLES ANALYSIS")
    print("="*80)
    for imei in all_imeis:
        print(f"\n--- IMEI: {imei} ---")
        cur.execute("""
            SELECT timestamp, latitude, longitude, speed, io_elements
            FROM telemetry
            WHERE imei = %s AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp ASC
        """, (imei, start_dt, end_dt))
        rows = cur.fetchall()
        print(f"Total points today: {len(rows)}")
        if not rows:
            print("No telemetry today.")
            continue
            
        # Analyze coordinate variations
        coords = set()
        speeds = []
        ignitions = []
        for r in rows:
            lat, lon = r[1], r[2]
            sp = float(r[3] or 0.0)
            io = r[4]
            if isinstance(io, str):
                try: io = json.loads(io)
                except: io = {}
            ign = str(io.get('239', io.get('1', '0'))) == '1'
            if lat and lon:
                coords.add((round(lat, 5), round(lon, 5)))
            speeds.append(sp)
            ignitions.append(ign)
            
        print(f"Unique GPS coordinates (rounded to 5 decimals): {len(coords)}")
        print(f"Coordinates list (up to 5): {list(coords)[:5]}")
        print(f"Speed stats: Min={min(speeds)}, Max={max(speeds)}, Non-zero speeds={len([s for s in speeds if s > 0])}")
        print(f"Ignition stats: ON={ignitions.count(True)}, OFF={ignitions.count(False)}")
        
        # Let's inspect some of the raw records where speed > 0 or ignition = True
        cur.execute("""
            SELECT timestamp, latitude, longitude, speed, io_elements
            FROM telemetry
            WHERE imei = %s AND timestamp BETWEEN %s AND %s AND (speed > 0 OR (io_elements->>'239' = '1' OR io_elements->>'1' = '1'))
            ORDER BY timestamp ASC LIMIT 5
        """, (imei, start_dt, end_dt))
        active_rows = cur.fetchall()
        print(f"Active telemetry records today (speed > 0 or ignition ON) (up to 5):")
        for r in active_rows:
            io = r[4]
            if isinstance(io, str):
                try: io = json.loads(io)
                except: io = {}
            ign = io.get('239', io.get('1', '0'))
            print(f"  - ts: {r[0]} | lat: {r[1]} | lon: {r[2]} | speed: {r[3]} | ign: {ign}")
            
    cur.close()
    conn.close()

if __name__ == "__main__":
    inspect_details()
