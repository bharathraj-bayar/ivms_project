import os
import firebase_admin
from firebase_admin import credentials, messaging

_firebase_app = None

def init_firebase():
    global _firebase_app
    if _firebase_app:
        return _firebase_app
    cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT', 'serviceAccountKey.json')
    if not os.path.exists(cred_path):
        raise FileNotFoundError(f"Firebase service account not found at {cred_path}")
    cred = credentials.Certificate(cred_path)
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def send_fcm_multicast(tokens, title, body, data=None):
    init_firebase()
    # Build message
    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=tokens
    )
    response = messaging.send_multicast(message)
    return response


def send_fcm_to_token(token, title, body, data=None):
    init_firebase()
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        token=token
    )
    resp = messaging.send(message)
    return resp
