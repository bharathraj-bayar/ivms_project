from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from auth.api_utils import get_current_user
from models.database import get_conn
import psycopg2.extras

router = APIRouter(prefix="/api/mobile/v1", tags=["mobile-sync"])


@router.get("/sync")
def sync(since: Optional[str] = Query(None), user=Depends(get_current_user)):
    # Simple delta sync: return changed vehicles, notifications, and settings since timestamp
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        email = user.get('email')
        params = [email]
        q = "SELECT id, unique_id, data FROM vehicles WHERE parent_email = %s"
        if since:
            q += " AND updated_at > %s"
            params.append(since)
        cur.execute(q, tuple(params))
        vehicles = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM notification_history WHERE email = %s ORDER BY created_at DESC LIMIT 100", (email,))
        notifications = [dict(r) for r in cur.fetchall()]

        # return latest sync_changes sequence for delta sync
        cur.execute("SELECT COALESCE(MAX(seq),0) as max_seq FROM sync_changes")
        max_seq = cur.fetchone()['max_seq'] if cur.rowcount else 0

        return {"status": "success", "data": {"vehicles": vehicles, "notifications": notifications, "server_seq": max_seq}}
    finally:
        cur.close(); conn.close()


@router.post("/offline/events")
def offline_events(events: list, user=Depends(get_current_user)):
    # Store offline events for later processing
    conn = get_conn(); cur = conn.cursor()
    try:
        for e in events:
            cur.execute("INSERT INTO offline_events (event_data, user_email, created_at) VALUES (%s,%s,now())", (psycopg2.extras.Json(e), user.get('email')))
        conn.commit()
        return {"status": "success"}
    finally:
        cur.close(); conn.close()


@router.post("/offline/locations")
def offline_locations(locations: list, user=Depends(get_current_user)):
    conn = get_conn(); cur = conn.cursor()
    try:
        for l in locations:
            cur.execute("INSERT INTO offline_locations (location_data, user_email, created_at) VALUES (%s,%s,now())", (psycopg2.extras.Json(l), user.get('email')))
        conn.commit()
        return {"status": "success"}
    finally:
        cur.close(); conn.close()
