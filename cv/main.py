import cv2
import time
import os
from lib.camera import init_camera
from lib.classifier import detect_and_classify, draw_results, load_reference, save_reference
from lib.dashboard import send_to_dashboard
from lib.debug import save_debug

SCAN_INTERVAL = float(os.getenv("SCAN_INTERVAL", "1.0"))
SHOW_PREVIEW = os.getenv("SHOW_PREVIEW", "true").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def main():
    load_reference()
    get_frame, release = init_camera()

    print("Controls: Q = quit | R = save current tag as reference")
    print(f"Preview: {'on' if SHOW_PREVIEW else 'off'} | Debug: {'on' if DEBUG else 'off'}")

    last_scan = 0
    last_results = []

    try:
        while True:
            frame = get_frame()
            if frame is None:
                continue

            now = time.time()
            if now - last_scan >= SCAN_INTERVAL:
                last_results = detect_and_classify(frame)
                last_scan = now

                if last_results:
                    for r in last_results:
                        msg = f"Tag {r['tag_id']}: {r['status']}"
                        if r["defect_type"]:
                            msg += f" → {r['defect_type']}"
                        print(msg)
                    send_to_dashboard(last_results, frame)
                    if DEBUG:
                        save_debug(frame, last_results)
                else:
                    print("No tags detected")

            if SHOW_PREVIEW:
                display = draw_results(frame.copy(), last_results)
                cv2.imshow("Mini Factory CV", display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("r") and last_results:
                    save_reference(last_results[0]["normalized"])

    finally:
        release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
