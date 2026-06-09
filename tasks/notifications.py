from celery_app import celery_app
from services.firebase_service import send_fcm_multicast, send_fcm_to_token, init_firebase
from models.notifications import get_devices_for_email, add_notification_history, set_notification_delivered
import time


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def send_speed_alert(self, tenant_id, email, device_id, title, body, payload=None):
    try:
        devices = get_devices_for_email(email)
        tokens = [d.get('fcm_token') for d in devices if d.get('fcm_token')]
        if not tokens:
            nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'CRITICAL', 'speed')
            return {'delivered': 0, 'history_id': nid}

        # batch send (multicast)
        resp = send_fcm_multicast(tokens, title, body, data=payload)
        nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'CRITICAL', 'speed')
        # Mark delivered if at least one successful
        if resp.success_count > 0:
            set_notification_delivered(nid, True)
        return {'delivered': resp.success_count, 'failure': resp.failure_count, 'history_id': nid}
    except Exception as e:
        try:
            self.retry(exc=e)
        except Exception:
            nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'CRITICAL', 'speed')
            return {'delivered': 0, 'error': str(e), 'history_id': nid}


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def send_geofence_alert(self, tenant_id, email, device_id, title, body, payload=None, event_type='geofence_entry'):
    try:
        devices = get_devices_for_email(email)
        tokens = [d.get('fcm_token') for d in devices if d.get('fcm_token')]
        if not tokens:
            nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'WARNING', event_type)
            return {'delivered': 0, 'history_id': nid}
        resp = send_fcm_multicast(tokens, title, body, data=payload)
        nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'WARNING', event_type)
        if resp.success_count > 0:
            set_notification_delivered(nid, True)
        return {'delivered': resp.success_count, 'failure': resp.failure_count, 'history_id': nid}
    except Exception as e:
        try:
            self.retry(exc=e)
        except Exception:
            nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'WARNING', event_type)
            return {'delivered': 0, 'error': str(e), 'history_id': nid}


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def send_panic_alert(self, tenant_id, email, device_id, title, body, payload=None):
    # Panic alerts are high priority
    try:
        devices = get_devices_for_email(email)
        tokens = [d.get('fcm_token') for d in devices if d.get('fcm_token')]
        if not tokens:
            nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'CRITICAL', 'panic')
            return {'delivered': 0, 'history_id': nid}
        resp = send_fcm_multicast(tokens, title, body, data=payload)
        nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'CRITICAL', 'panic')
        if resp.success_count > 0:
            set_notification_delivered(nid, True)
        return {'delivered': resp.success_count, 'failure': resp.failure_count, 'history_id': nid}
    except Exception as e:
        try:
            self.retry(exc=e)
        except Exception:
            nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'CRITICAL', 'panic')
            return {'delivered': 0, 'error': str(e), 'history_id': nid}


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def send_maintenance_reminder(self, tenant_id, email, device_id, title, body, payload=None):
    try:
        devices = get_devices_for_email(email)
        tokens = [d.get('fcm_token') for d in devices if d.get('fcm_token')]
        resp = None
        nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'INFO', 'maintenance')
        if tokens:
            resp = send_fcm_multicast(tokens, title, body, data=payload)
            if resp.success_count > 0:
                set_notification_delivered(nid, True)
        return {'delivered': resp.success_count if resp else 0, 'history_id': nid}
    except Exception as e:
        try:
            self.retry(exc=e)
        except Exception:
            nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'INFO', 'maintenance')
            return {'delivered': 0, 'error': str(e), 'history_id': nid}


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def send_trip_complete(self, tenant_id, email, device_id, title, body, payload=None):
    try:
        devices = get_devices_for_email(email)
        tokens = [d.get('fcm_token') for d in devices if d.get('fcm_token')]
        nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'INFO', 'trip_complete')
        if not tokens:
            return {'delivered': 0, 'history_id': nid}
        resp = send_fcm_multicast(tokens, title, body, data=payload)
        if resp.success_count > 0:
            set_notification_delivered(nid, True)
        return {'delivered': resp.success_count, 'failure': resp.failure_count, 'history_id': nid}
    except Exception as e:
        try:
            self.retry(exc=e)
        except Exception:
            nid = add_notification_history(tenant_id, email, device_id, title, body, payload, 'INFO', 'trip_complete')
            return {'delivered': 0, 'error': str(e), 'history_id': nid}
