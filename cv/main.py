import cv2
import time
import os
from dotenv import load_dotenv

# Load env BEFORE importing lib modules that read env vars at import time
load_dotenv(dotenv_path="../.env")

from lib.camera import init_camera
from lib.classifier import detect_and_classify, load_reference, save_template, clear_templates
from lib.color_detector import find_red_box
from lib.dashboard import send_to_dashboard

SCAN_INTERVAL = float(os.getenv("SCAN_INTERVAL", "1.0"))
SHOW_PREVIEW = os.getenv("SHOW_PREVIEW", "true").lower() == "true"


def main():
    load_reference()
    get_frame, release = init_camera()

    print(f"Running. Sending to dashboard every {SCAN_INTERVAL}s.")
    print("Controls (preview window): Q = quit | C = clear all templates")
    print("  Show the TRIANGLE tag, press 1 repeatedly to add samples (angles/distances)")
    print("  Show the CIRCLE tag,   press 2 repeatedly to add samples")
    print("  Capture 5-8 samples of each for best results.")

    last_scan = 0
    bbox = None
    results = []

    try:
        while True:
            frame = get_frame()
            if frame is None:
                continue

            now = time.time()
            if now - last_scan >= SCAN_INTERVAL:
                last_scan = now

                # Crop to red box region
                crop, bbox = find_red_box(frame)

                # Detect AprilTags inside the crop
                results = detect_and_classify(crop)

                print(f"Red box: {'found' if bbox else 'not found'} | Tags detected: {len(results)}")

                send_to_dashboard(results, crop)

            if SHOW_PREVIEW:
                display = frame.copy()
                if bbox:
                    x, y, w, h = bbox
                    cv2.rectangle(display, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.imshow("Mini Factory CV", display)  # noqa: F821

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("1") and results:
                    save_template(results[0]["normalized"], "triangle")
                elif key == ord("2") and results:
                    save_template(results[0]["normalized"], "circle")
                elif key == ord("c"):
                    clear_templates()

    finally:
        release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
