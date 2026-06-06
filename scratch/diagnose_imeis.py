import os
import sys
import json
from datetime import datetime, timezone

# Add project root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_conn
from services.time_service import get_period_dates

TARGET_IMEIS = ["864275071330206", "864275071228707", "864275071199007"]
WORKING_IMEIS = ["864275071226750", "864275071210218", "864275071217296"]
ALL_IMEIS = TARGET_IMEIS + WORKING_IMEIS

def run_diagnostics():
    conn = get_conn()
    cur = conn.cursor()
    
    start_dt, end_dt = get_period_dates('Today')
    print(f"Diagnostics window (Oman local): {start_dt} to {end_dt}")
    print(f"Diagnostics window (UTC): {start_dt.astimezone(timezone.utc)} to {end_dt.astimezone(timezone.utc)}")
    
    print("\n" + "="*80)
    print("PHASE 1: VERIFY DEVICE EXISTENCE")
    print("="*80)
    
    for imei in ALL_IMEIS:
        print(f"\n--- IMEI: {imei} ---")
        
        # 1. devices table
        cur.execute("SELECT * FROM devices WHERE imei = %s", (imei,))
        dev_row = cur.fetchone()
        if dev_row:
            # Let's get column names
            colnames = [desc[0] for desc in cur.description]
            dev_dict = dict(zip(colnames, dev_row))
            print(f"devices table: EXISTS")
            print(f"  - id: {dev_dict.get('id') or dev_dict.get('device_id')}")
            print(f"  - model: {dev_dict.get('device_model') or dev_dict.get('model')}")
            print(f"  - status: {dev_dict.get('status')}")
            print(f"  - company_id/name: {dev_dict.get('company_id')} / {dev_dict.get('company_name')}")
        else:
            print(f"devices table: NOT FOUND")
            
        # 2. vehicles table
        cur.execute("SELECT * FROM vehicles WHERE unique_id = %s", (imei,))
        veh_row = cur.fetchone()
        if veh_row:
            colnames = [desc[0] for desc in cur.description]
            veh_dict = dict(zip(colnames, veh_row))
            print(f"vehicles table: EXISTS")
            print(f"  - name: {veh_dict.get('name')}")
            print(f"  - company_name: {veh_dict.get('company_name')}")
            print(f"  - driver_name: {veh_dict.get('driver_name')}")
            print(f"  - status: {veh_dict.get('status')}")
            print(f"  - device_model: {veh_dict.get('device_model')}")
        else:
            print(f"vehicles table: NOT FOUND")
            
        # 3. live_vehicle_status table
        cur.execute("SELECT * FROM live_vehicle_status WHERE imei = %s", (imei,))
        lvs_row = cur.fetchone()
        if lvs_row:
            colnames = [desc[0] for desc in cur.description]
            lvs_dict = dict(zip(colnames, lvs_row))
            print(f"live_vehicle_status table: EXISTS")
            print(f"  - status: {lvs_dict.get('status')}")
            print(f"  - last_timestamp: {lvs_dict.get('last_timestamp')}")
            print(f"  - updated_at: {lvs_dict.get('updated_at')}")
            print(f"  - current_driver_name: {lvs_dict.get('current_driver_name')}")
        else:
            print(f"live_vehicle_status table: NOT FOUND")

        # 4. live_position_updates table
        cur.execute("SELECT * FROM live_position_updates WHERE imei = %s ORDER BY new_timestamp DESC LIMIT 1", (imei,))
        lpu_row = cur.fetchone()
        if lpu_row:
            colnames = [desc[0] for desc in cur.description]
            lpu_dict = dict(zip(colnames, lpu_row))
            print(f"live_position_updates: EXISTS (latest)")
            print(f"  - new_timestamp: {lpu_dict.get('new_timestamp')}")
            print(f"  - new_latitude: {lpu_dict.get('new_latitude')}")
            print(f"  - new_longitude: {lpu_dict.get('new_longitude')}")
            print(f"  - updated_at: {lpu_dict.get('updated_at')}")
        else:
            print(f"live_position_updates: NOT FOUND")
            
    print("\n" + "="*80)
    print("PHASE 2: CHECK RAW TELEMETRY RECEPTION")
    print("="*80)
    
    for imei in ALL_IMEIS:
        print(f"\n--- IMEI: {imei} ---")
        
        # Get count of today's telemetry
        cur.execute("SELECT COUNT(*) FROM telemetry WHERE imei = %s AND timestamp BETWEEN %s AND %s", (imei, start_dt, end_dt))
        today_cnt = cur.fetchone()[0]
        
        # Get count of today's GPS telemetry (where lat/lon are not 0 and not null)
        cur.execute("""
            SELECT COUNT(*) FROM telemetry 
            WHERE imei = %s AND timestamp BETWEEN %s AND %s 
            AND latitude IS NOT NULL AND longitude IS NOT NULL 
            AND latitude != 0 AND longitude != 0
        """, (imei, start_dt, end_dt))
        today_gps_cnt = cur.fetchone()[0]
        
        print(f"Telemetry count today: {today_cnt}")
        print(f"GPS records count today: {today_gps_cnt}")
        
        # Get most recent telemetry record
        cur.execute("SELECT * FROM telemetry WHERE imei = %s ORDER BY timestamp DESC LIMIT 1", (imei,))
        tel_row = cur.fetchone()
        if tel_row:
            colnames = [desc[0] for desc in cur.description]
            tel_dict = dict(zip(colnames, tel_row))
            print(f"Most recent telemetry:")
            print(f"  - timestamp: {tel_dict.get('timestamp')}")
            print(f"  - speed: {tel_dict.get('speed')}")
            print(f"  - lat/lon: {tel_dict.get('latitude')}, {tel_dict.get('longitude')}")
            io = tel_dict.get('io_elements')
            if isinstance(io, str):
                try: io = json.loads(io)
                except: pass
            ign = io.get('239', io.get('1', 'N/A')) if isinstance(io, dict) else 'N/A'
            print(f"  - ignition (io 239/1): {ign}")
        else:
            print("No telemetry found in DB at all.")
            
        # Get most recent telemetry record with valid GPS fix
        cur.execute("""
            SELECT * FROM telemetry 
            WHERE imei = %s AND latitude IS NOT NULL AND longitude IS NOT NULL 
            AND latitude != 0 AND longitude != 0
            ORDER BY timestamp DESC LIMIT 1
        """, (imei,))
        gps_row = cur.fetchone()
        if gps_row:
            colnames = [desc[0] for desc in cur.description]
            gps_dict = dict(zip(colnames, gps_row))
            print(f"Most recent GPS fix:")
            print(f"  - timestamp: {gps_dict.get('timestamp')}")
            print(f"  - lat/lon: {gps_dict.get('latitude')}, {gps_dict.get('longitude')}")
            print(f"  - speed: {gps_dict.get('speed')}")
        else:
            print("No valid GPS fix found in DB at all.")
            
    print("\n" + "="*80)
    print("PHASE 3: COMPLETED TRIPS & EVENTS TODAY")
    print("="*80)
    for imei in ALL_IMEIS:
        print(f"\n--- IMEI: {imei} ---")
        cur.execute("SELECT COUNT(*), SUM(distance_km) FROM trip_summary WHERE imei = %s AND start_time BETWEEN %s AND %s", (imei, start_dt, end_dt))
        trip_cnt, trip_dist = cur.fetchone()
        print(f"Completed trips today: {trip_cnt} (Total Distance: {trip_dist} km)")
        
        cur.execute("SELECT event_type, COUNT(*) FROM analytics_events WHERE imei = %s AND timestamp BETWEEN %s AND %s GROUP BY event_type", (imei, start_dt, end_dt))
        events = cur.fetchall()
        print(f"Analytics events today:")
        for ev in events:
            print(f"  - {ev[0]}: {ev[1]}")
            
    cur.close()
    conn.close()

if __name__ == "__main__":
    run_diagnostics()
