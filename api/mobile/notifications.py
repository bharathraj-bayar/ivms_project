from fastapi import APIRouter, Depends, HTTPException
+from pydantic import BaseModel
+from auth.api_utils import get_current_user
+from models.notifications import register_user_device, update_user_device, remove_user_device, get_devices_for_email, add_notification_history, set_notification_delivered
+from services.firebase_service import send_fcm_multicast, send_fcm_to_token
+
+router = APIRouter(prefix="/api/mobile/v1/notifications", tags=["mobile-notifications"])
+
+
+class RegisterDeviceRequest(BaseModel):
+    device_id: str
+    platform: str
+    fcm_token: str
+
+
+class UpdateDeviceRequest(BaseModel):
+    device_id: str
+    fcm_token: str | None = None
+    platform: str | None = None
+
+
+class RemoveDeviceRequest(BaseModel):
+    device_id: str
+
+
+@router.post("/register-device")
+def register_device(req: RegisterDeviceRequest, user=Depends(get_current_user)):
+    email = user.get('email')
+    ok = register_user_device(email, req.device_id, req.platform, req.fcm_token)
+    if not ok:
+        raise HTTPException(status_code=500, detail="failed")
+    return {"status": "success"}
+
+
+@router.put("/update-device")
+def update_device(req: UpdateDeviceRequest, user=Depends(get_current_user)):
+    email = user.get('email')
+    ok = update_user_device(email, req.device_id, fcm_token=req.fcm_token, platform=req.platform)
+    if not ok:
+        raise HTTPException(status_code=404, detail="not_found")
+    return {"status": "success"}
+
+
+@router.delete("/remove-device")
+def remove_device(req: RemoveDeviceRequest, user=Depends(get_current_user)):
+    email = user.get('email')
+    ok = remove_user_device(email, req.device_id)
+    if not ok:
+        raise HTTPException(status_code=404, detail="not_found")
+    return {"status": "success"}
+
+
+@router.post("/send-test/{device_id}")
+def send_test(device_id: str, user=Depends(get_current_user)):
+    # Utility: send a test message to a specific device for debugging
+    devices = get_devices_for_email(user.get('email'))
+    token = None
+    for d in devices:
+        if d.get('device_id') == device_id:
+            token = d.get('fcm_token')
+            break
+    if not token:
+        raise HTTPException(status_code=404, detail="device_not_found")
+    resp = send_fcm_to_token(token, "IVMS Test", "This is a test push from IVMS")
+    return {"status": "success", "response": str(resp)}
+
*** End Patch