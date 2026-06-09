from celery_app import celery_app
from models.database import get_conn
from tasks.notifications import send_speed_alert, send_geofence_alert, send_panic_alert, send_maintenance_reminder, send_trip_complete
import psycopg2.extras


@celery_app.task(bind=True)
def dispatch_notifications(self, limit=100):
    """
    Polls `notification_queue` table for pending notifications and dispatches appropriate celery tasks.
    This task is intended to be scheduled (cron/beat) or run as a long-running worker loop.
    """
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT id, tenant_id, title, message, severity, event_type, device_id, payload FROM notification_queue WHERE archived = FALSE AND processed = FALSE ORDER BY created_at ASC LIMIT %s", (limit,))
        rows = cur.fetchall()
        dispatched = 0
        for r in rows:
            nid = r['id']
            tenant = r.get('tenant_id')
            email = tenant
            device_id = r.get('device_id')
            title = r.get('title')
            body = r.get('message')
            etype = r.get('event_type') or 'generic'
            payload = r.get('payload') or {}

            try:
                if etype == 'speed':
                    send_speed_alert.delay(tenant, email, device_id, title, body, payload)
                elif etype in ('geofence_entry', 'geofence_exit'):
                    send_geofence_alert.delay(tenant, email, device_id, title, body, payload, event_type=etype)
                elif etype == 'panic':
                    send_panic_alert.delay(tenant, email, device_id, title, body, payload)
                elif etype == 'maintenance':
                    send_maintenance_reminder.delay(tenant, email, device_id, title, body, payload)
                elif etype == 'trip_complete':
                    send_trip_complete.delay(tenant, email, device_id, title, body, payload)
                else:
                    # fallback to maintenance task for generic informational messages
                    send_maintenance_reminder.delay(tenant, email, device_id, title, body, payload)

                # mark as processed
                cur.execute("UPDATE notification_queue SET processed = TRUE, processed_at = now() WHERE id = %s", (nid,))
                conn.commit()
                dispatched += 1
            except Exception as e:
                # leave unprocessed for retry
                print(f"Failed to dispatch notification {nid}: {e}")
        return {'dispatched': dispatched}
    finally:
        cur.close(); conn.close()
