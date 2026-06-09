from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
from auth.api_utils import get_allowed_imeis, get_current_user
from services.telemetry_service import telemetry_service
from models.database import get_vehicle_by_uid, load_vehicles, load_users
from services.native_report_service import native_report_service
from models.notifications import add_notification_history
from core.cache_utils import get_cache, set_cache, invalidate_cache
from config import Config

router = APIRouter(prefix="/api/mobile/v1", tags=["mobile"])


def _paginate(items, page: int, per_page: int):
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], len(items)


@router.get("/dashboard/summary")
def dashboard_summary(allowed_imeis: List[str] = Depends(get_allowed_imeis)):
    # Return basic live counts and a small fleet summary
    tenant = allowed_imeis[0] if allowed_imeis else 'global'
    cache_key = 'dashboard_summary'
    cached = get_cache(tenant, 'dashboard', cache_key)
    if cached:
        return {"status": "success", "data": cached}

    all_live = telemetry_service.get_all_live(allowed_imeis)
    summary = {
        "total_devices": len(all_live),
        "online": sum(1 for d in all_live if d.get('status') == 'online'),
        "offline": sum(1 for d in all_live if d.get('status') != 'online'),
        "sample": all_live[:50]
    }
    try:
        set_cache(tenant, 'dashboard', cache_key, summary, ttl=30)
    except Exception:
        pass
    return {"status": "success", "data": summary}


@router.get("/vehicles")
def vehicles_list(page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=200),
                  search: Optional[str] = Query(None), sort: Optional[str] = Query(None),
                  allowed_imeis: List[str] = Depends(get_allowed_imeis)):
    tenant = allowed_imeis[0] if allowed_imeis else 'global'
    cache_key = f"vehicles:{page}:{per_page}:{search or ''}:{sort or ''}"
    cached = get_cache(tenant, 'vehicles', cache_key)
    if cached:
        return {"status": "success", "data": cached.get('items'), "meta": cached.get('meta')}

    vehicles = load_vehicles()
    # Filter by tenant allowed devices
    vehicles = [v for v in vehicles if str(v.get('unique_id')) in allowed_imeis]

    if search:
        s = search.lower()
        vehicles = [v for v in vehicles if s in str(v.get('name', '')).lower() or s in str(v.get('unique_id', '')).lower()]

    total = len(vehicles)
    if sort:
        reverse = sort.startswith("-")
        key = sort.lstrip("-")
        vehicles.sort(key=lambda x: x.get(key, ''), reverse=reverse)

    page_items, total_count = _paginate(vehicles, page, per_page)
    meta = {"page": page, "per_page": per_page, "total": total_count}
    try:
        set_cache(tenant, 'vehicles', cache_key, {'items': page_items, 'meta': meta}, ttl=30)
    except Exception:
        pass
    return {"status": "success", "data": page_items, "meta": meta}


@router.get("/vehicles/{imei}")
def vehicle_detail(imei: str, allowed_imeis: List[str] = Depends(get_allowed_imeis)):
    if imei not in allowed_imeis:
        raise HTTPException(status_code=403, detail="access_denied")
    v = get_vehicle_by_uid(imei)
    if not v:
        raise HTTPException(status_code=404, detail="not_found")
    return {"status": "success", "data": v}


@router.get("/drivers")
def drivers_list(page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=200)):
    users = load_users()
    drivers = [u for u in users if u.get('role') == 'driver' or u.get('role') == 'driver_user']
    page_items, total = _paginate(drivers, page, per_page)
    return {"status": "success", "data": page_items, "meta": {"page": page, "per_page": per_page, "total": total}}


@router.get("/drivers/{driver_id}")
def driver_detail(driver_id: str):
    users = load_users()
    for u in users:
        if str(u.get('driver_id') or u.get('email')) == str(driver_id):
            return {"status": "success", "data": u}
    raise HTTPException(status_code=404, detail="not_found")


@router.get("/trips/{imei}")
def trip_history(imei: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = Query(500, le=2000),
                 allowed_imeis: List[str] = Depends(get_allowed_imeis)):
    if imei not in allowed_imeis:
        raise HTTPException(status_code=403, detail="access_denied")
    try:
        from services.native_report_service import native_report_service
        # parse ISO dates optionally; native service will handle None
        trips = native_report_service.get_trip_report(imei, None, None) if (not start and not end) else native_report_service.get_trip_report(imei, start, end)
        return {"status": "success", "data": trips[:limit]}
    except Exception:
        return {"status": "error", "data": []}


@router.get("/geofences")
def geofence_list():
    # Placeholder: no dedicated geofence service discovered — return empty for now
    return {"status": "success", "data": []}


@router.get("/alerts")
def alerts_list(page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=200),
                allowed_imeis: List[str] = Depends(get_allowed_imeis)):
    # Use native analytics events where available
    try:
        from services.native_report_service import native_report_service
        from services.time_service import get_period_dates
        start_dt, end_dt = get_period_dates('Today')
        events = native_report_service.get_analytics_events(None, 'all', start_dt, end_dt, allowed_imeis)
        page_items, total = _paginate(events, page, per_page)
        return {"status": "success", "data": page_items, "meta": {"page": page, "per_page": per_page, "total": total}}
    except Exception:
        return {"status": "success", "data": [], "meta": {"page": page, "per_page": per_page, "total": 0}}


@router.get("/notifications")
def notifications_list(page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=200), user=Depends(get_current_user)):
    # Reuse existing notification queue read logic by querying DB
    from models.database import get_conn
    import psycopg2.extras
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        email = user.get('email')
        cur.execute("SELECT * FROM notification_queue WHERE tenant_id = %s AND archived = FALSE ORDER BY created_at DESC", (email,))
        rows = cur.fetchall()
        page_items, total = _paginate(rows, page, per_page)
        return {"status": "success", "data": page_items, "meta": {"page": page, "per_page": per_page, "total": total}}
    finally:
        cur.close(); conn.close()


@router.get("/profile")
def user_profile(user=Depends(get_current_user)):
    return {"status": "success", "data": user}


@router.get("/settings")
def user_settings(user=Depends(get_current_user)):
    # Return server config and user's module flags
    from models.database import get_user_by_email
    u = get_user_by_email(user.get('email'))
    return {"status": "success", "data": u.get('data') if u else {}}
