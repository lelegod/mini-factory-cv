import requests
import threading
import os

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:3000/api/defect")


def _post(payload):
    try:
        requests.post(DASHBOARD_URL, json=payload, timeout=3)
    except requests.exceptions.RequestException:
        pass


def send_to_dashboard(results):
    for r in results:
        payload = {
            "tag_id": r["tag_id"],
            "status": r["status"],
            "defect_type": r["defect_type"],
        }
        threading.Thread(target=_post, args=(payload,), daemon=True).start()
