import psycopg2.extras
from models.database import get_conn

def register_user_device(email, device_id, platform, fcm_token):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_devices (email, device_id, platform, fcm_token, last_seen)
            VALUES (%s,%s,%s,%s,now())
            ON CONFLICT (device_id) DO UPDATE SET fcm_token = EXCLUDED.fcm_token, updated_at = now(), last_seen = now();
        """, (email, device_id, platform, fcm_token))
        conn.commit()
        return True
    except Exception as e:
        print(f"register_user_device error: {e}")
        return False
    finally:
        cur.close(); conn.close()

def update_user_device(email, device_id, fcm_token=None, platform=None):
    conn = get_conn(); cur = conn.cursor()
    try:
        updates = []
        params = []
        if fcm_token is not None:
            updates.append('fcm_token = %s')
            params.append(fcm_token)
        if platform is not None:
            updates.append('platform = %s')
            params.append(platform)
        updates.append('updated_at = now()')
        params.extend([email, device_id])
        cur.execute(f"UPDATE user_devices SET {', '.join(updates)} WHERE email = %s AND device_id = %s", tuple(params))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"update_user_device error: {e}")
        return False
    finally:
        cur.close(); conn.close()

def remove_user_device(email, device_id):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("DELETE FROM user_devices WHERE email = %s AND device_id = %s", (email, device_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"remove_user_device error: {e}")
        return False
    finally:
        cur.close(); conn.close()

def get_devices_for_email(email):
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT * FROM user_devices WHERE email = %s", (email,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        cur.close(); conn.close()

def add_notification_history(tenant_id, email, device_id, title, body, payload, severity, event_type):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO notification_history (tenant_id, email, device_id, title, body, payload, severity, event_type, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now())
            RETURNING id
            """,
            (tenant_id, email, device_id, title, body, psycopg2.extras.Json(payload) if payload else None, severity, event_type)
        )
        nid = cur.fetchone()[0]
        conn.commit()
        # Add to sync_changes for clients to pick up
        try:
            c2 = get_conn(); cur2 = c2.cursor()
            cur2.execute("INSERT INTO sync_changes (table_name, record_id, operation, payload) VALUES (%s,%s,%s,%s)",
                         ('notification_history', nid, 'insert', psycopg2.extras.Json({'id': nid, 'tenant_id': tenant_id, 'email': email})))
            c2.commit(); cur2.close(); c2.close()
        except Exception:
            pass
        return nid
    except Exception as e:
        print(f"add_notification_history error: {e}")
        return None
    finally:
        cur.close(); conn.close()

def set_notification_delivered(nid, delivered=True):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("UPDATE notification_history SET delivered = %s, delivered_at = now() WHERE id = %s", (delivered, nid))
        conn.commit()
    finally:
        cur.close(); conn.close()
