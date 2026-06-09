from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from auth.api_utils import get_current_user
from models.database import get_conn
import psycopg2.extras

router = APIRouter(prefix="/api/mobile/v1/sync", tags=["mobile-sync"])


@router.get("/changes")
def get_changes(since_seq: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=5000), user=Depends(get_current_user)):
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT seq, table_name, record_id, operation, payload, created_at FROM sync_changes WHERE seq > %s ORDER BY seq ASC LIMIT %s", (since_seq, limit))
        rows = [dict(r) for r in cur.fetchall()]
        return {"status": "success", "data": rows}
    finally:
        cur.close(); conn.close()


@router.post("/ack")
def ack_changes(last_seq: int, user=Depends(get_current_user)):
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Store last acknowledged seq in sync_state
        cur.execute("INSERT INTO sync_state (user_email, last_sequence, updated_at) VALUES (%s,%s,now()) ON CONFLICT (user_email) DO UPDATE SET last_sequence = EXCLUDED.last_sequence, updated_at = EXCLUDED.updated_at", (user.get('email'), last_seq))
        conn.commit()
        return {"status": "success"}
    finally:
        cur.close(); conn.close()
