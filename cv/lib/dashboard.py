import requests
import threading
import os
import base64
import cv2

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:3000/api/scan")


def encode_image(img) -> str:
    _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


def _post(payload):
    try:
        requests.post(DASHBOARD_URL, json=payload, timeout=3)
    except requests.exceptions.RequestException:
        pass


def send_to_dashboard(results, frame):
    camera_b64 = encode_image(frame)
    for r in results:
        tag_b64 = encode_image(r["normalized"]) if r.get("normalized") is not None else ""
        payload = {
            "tag_id": r["tag_id"],
            "status": "approved" if r["status"] == "normal" else "defective",
            "image_base64": tag_b64,
            "camera_image_base64": camera_b64,
        }
        threading.Thread(target=_post, args=(payload,), daemon=True).start()
