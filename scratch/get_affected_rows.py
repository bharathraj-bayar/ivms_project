import os
import sys
import json
from datetime import datetime

# Add project root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_conn

import decimal

def datetime_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def dump_affected():
    conn = get_conn()
    cur = conn.cursor()
    
    imeis = ["864275071217296", "86421507228701", "864275071207909", "864275071199007"]
    
    for imei in imeis:
        cur.execute("SELECT * FROM live_vehicle_status WHERE imei = %s", (imei,))
        row = cur.fetchone()
        if row:
            colnames = [desc[0] for desc in cur.description]
            row_dict = dict(zip(colnames, row))
            print(f"\nIMEI: {imei}")
            print(json.dumps(row_dict, default=datetime_serializer, indent=2))
        else:
            print(f"\nIMEI: {imei} - NOT FOUND in live_vehicle_status")
            
    cur.close()
    conn.close()

if __name__ == "__main__":
    dump_affected()
