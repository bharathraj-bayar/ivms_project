import os
import sys

# Add project root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_conn

def print_schema(table_name):
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    
    rows = cur.fetchall()
    print(f"\nSchema for table: {table_name}")
    print(f"{'Column Name':<40} | {'Data Type':<30} | {'Nullable':<10} | {'Default':<30}")
    print("-"*118)
    for r in rows:
        print(f"{r[0]:<40} | {r[1]:<30} | {r[2]:<10} | {str(r[3]):<30}")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    print_schema("live_vehicle_status")
    print_schema("telemetry")
    print_schema("live_position_updates")
