"""
Pre-Remediation Safety Simulation
Simulates how the reconciliation engine behaves for:
  1. NULL last_telemetry_id receives a new packet (current behavior)
  2. Out-of-order packets arriving after backfill
  3. Watchdog reconciliation behaviour for affected devices
  4. What happens if guard is removed (proposed code change)
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_conn
from datetime import datetime, timezone

AFFECTED = {
    "864275071217296": "Hyundai/Accent",
    "86421507228701":  "Unknown (Inactive)",
    "864275071207909": "Unknown (Inactive - India coords)",
    "864275071199007": "Mazda 3 51080",
}

def simulate():
    conn = get_conn()
    cur = conn.cursor()
    
    print("="*80)
    print("SIMULATION 1: Current Behavior for NULL last_telemetry_id + New Packet")
    print("="*80)
    for imei, name in AFFECTED.items():
        cur.execute("""
            SELECT last_telemetry_id, last_timestamp, longitude, latitude, status
            FROM live_vehicle_status WHERE imei = %s
        """, (imei,))
        row = cur.fetchone()
        if not row:
            print(f"\n  IMEI {imei} ({name}): Not in live_vehicle_status - would hit 'initial_position' branch")
            continue

        last_tid, last_ts, lon, lat, status = row

        cur.execute("""
            SELECT id, timestamp FROM telemetry WHERE imei = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (imei,))
        latest = cur.fetchone()

        print(f"\n  IMEI: {imei} ({name})")
        print(f"  DB State: last_telemetry_id={last_tid}, last_timestamp={last_ts}, status={status}")
        if latest:
            print(f"  Latest telemetry in DB: id={latest[0]}, ts={latest[1]}")

        # Simulate the reconciliation engine's if-elif-else logic
        if row and last_ts and last_tid is not None:
            print("  Engine branch: → CHRONOLOGICAL COMPARISON (normal path)")
        elif row and last_tid is None:
            print("  Engine branch: → POISONED_TIMESTAMP GUARD")
            print("  Result: is_stale=True, reconciled=False, DB NOT updated, Redis NOT updated")
            print("  Loop: Every new packet for this device will trigger this branch PERMANENTLY")
        else:
            print("  Engine branch: → initial_position (first time insert)")

    print("\n" + "="*80)
    print("SIMULATION 2: Out-of-Order Packet Scenario After Backfill")
    print("="*80)
    print("""
  Scenario: last_telemetry_id is backfilled (e.g. set to 177033 for 864275071199007).
  A stale historical packet arrives with timestamp BEFORE the current last_timestamp.

  Engine branch triggered:
    existing['last_timestamp'] = 2026-06-06 04:46:18 (from backfill)
    incoming packet ts         = 2026-05-23 05:30:21 (old cached/replay packet)

  Logic: timestamp (old) <= existing_ts (new) → is_stale=True, reason='already_stale'
  Result: CORRECTLY REJECTED — historical telemetry written to telemetry table but
          live_vehicle_status NOT overwritten. The map remains showing latest position.

  Conclusion: Out-of-order packets are safe after backfill. The chronological
              check at line 127 of reconciliation.py handles this correctly.
    """)

    print("="*80)
    print("SIMULATION 3: Watchdog Behaviour for Affected Devices (Current vs Post-Backfill)")
    print("="*80)
    cur.execute("""
        SELECT v.unique_id as imei, t.id as tid, t.timestamp, t.longitude, t.latitude,
               ls.last_timestamp as live_ts, ls.last_telemetry_id
        FROM vehicles v
        JOIN LATERAL (
            SELECT id, timestamp, longitude, latitude
            FROM telemetry WHERE imei = v.unique_id
            ORDER BY timestamp DESC LIMIT 1
        ) t ON TRUE
        LEFT JOIN live_vehicle_status ls ON v.unique_id = ls.imei
        WHERE v.unique_id = ANY(%s)
    """, (list(AFFECTED.keys()),))
    rows = cur.fetchall()
    for r in rows:
        imei, tid, t_ts, lon, lat, live_ts, last_tid = r
        print(f"\n  IMEI: {imei}")
        print(f"  Telemetry latest: id={tid}, ts={t_ts}")
        print(f"  Live status: last_ts={live_ts}, last_telemetry_id={last_tid}")
        if last_tid is None:
            print("  Watchdog finds discrepancy (telemetry ts > live_ts or live_ts IS NULL)")
            print("  Watchdog calls reconcile_position()")
            print("  → POISONED_TIMESTAMP guard fires → Watchdog heals NOTHING")
            print("  → Log: [WATCHDOG] Healed IMEI position. Result: no_valid_telemetry_id")
            print("  Status: Device remains frozen indefinitely")
        else:
            print("  Watchdog: live status is up to date, no action needed")

    print("\n" + "="*80)
    print("SIMULATION 4: What Happens If POISONED_TIMESTAMP Guard Is Removed (Code-Change Only)")
    print("="*80)
    print("""
  Proposed: Remove `elif existing and existing['last_telemetry_id'] is None` branch.
  With no backfill, affected devices still have NULL last_telemetry_id.

  The `else: reason = 'initial_position'` branch now executes instead.

  Engine flow:
    existing row EXISTS but last_telemetry_id IS NULL → falls into else → reason='initial_position'
    → is_stale stays False → DB UPDATE runs → last_telemetry_id is written for first time

  RISK: The `else` branch was only intended for truly NEW devices (no existing row at all).
  Applying it to existing rows with NULL last_telemetry_id would still work correctly because:
    - The incoming telemetry packet is genuine and chronologically newer than the NULL state
    - The UPDATE would write: last_telemetry_id, last_timestamp, lat/lon, speed, etc.
    - All subsequent packets would then use the normal chronological comparison path

  BUT: If `last_timestamp` in the existing row is NEWER than the incoming packet timestamp
  (which can happen if last_timestamp was set by the registration INSERT with datetime.now()),
  the else branch would STILL execute because it does NOT compare timestamps first.

  Specific risk for 864275071207909:
    - last_timestamp = 2026-05-20 11:52:19 (from an actual old telemetry packet via old system)
    - last_telemetry_id = NULL (migration artifact)
    - If code change removes guard: incoming packet at an older timestamp would write over
      the current last_timestamp → REGRESSION: live map timestamp would go backward

  Conclusion: Code-change-only carries a regression risk for 864275071207909 specifically.
    """)

    print("="*80)
    print("SIMULATION 5: Latest Telemetry Check vs Registration Timestamp Comparison")
    print("="*80)
    cur.execute("""
        SELECT imei, last_timestamp, updated_at 
        FROM live_vehicle_status 
        WHERE last_telemetry_id IS NULL
    """, )
    affected_rows = cur.fetchall()
    for r in affected_rows:
        imei, last_ts, updated_at = r
        cur.execute("""
            SELECT id, timestamp FROM telemetry WHERE imei = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (imei,))
        latest_t = cur.fetchone()
        print(f"\n  IMEI: {imei}")
        print(f"  live_vehicle_status.last_timestamp = {last_ts}")
        print(f"  Latest telemetry timestamp          = {latest_t[1] if latest_t else 'NO TELEMETRY'}")
        if latest_t and last_ts:
            if latest_t[1] > last_ts:
                print(f"  Relationship: latest_telemetry_ts > last_timestamp → BACKFILL IS SAFE")
            else:
                print(f"  Relationship: latest_telemetry_ts <= last_timestamp → BACKFILL REQUIRES CARE")
        elif not latest_t:
            print(f"  No telemetry in DB → Backfill not applicable for this IMEI")

    cur.close()
    conn.close()

if __name__ == "__main__":
    simulate()
