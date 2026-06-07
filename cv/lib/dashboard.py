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
        res = requests.post(DASHBOARD_URL, json=payload, timeout=5)
        print(f"POST {DASHBOARD_URL} -> {res.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"POST failed: {e}")


def send_to_dashboard(results, frame):
    camera_b64 = encode_image(frame)

    defective_images = []
    for r in results:
        tag_b64 = encode_image(r["normalized"]) if r.get("normalized") is not None else ""
        defective_images.append({
            "tag_id": r["tag_id"],
            "defect_type": r.get("defect_type") or "unknown",
            "image_base64": tag_b64,
            "timestamp": "",
        })

    payload = {
        "approved_count": 0,
        "defective_count": len(defective_images),
        "approved_images": [],
        "defective_images": defective_images,
        "camera_image_base64": camera_b64,
    }

    threading.Thread(target=_post, args=(payload,), daemon=True).start()
