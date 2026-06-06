import cv2
import time
import os
from lib.classifier import draw_results

DEBUG_DIR = "debug_output"


def save_debug(frame, results):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    ts = int(time.time())
    annotated = draw_results(frame.copy(), results)
    cv2.imwrite(f"{DEBUG_DIR}/frame_{ts}.jpg", annotated)
    for r in results:
        cv2.imwrite(f"{DEBUG_DIR}/crop_{ts}_tag{r['tag_id']}_{r['status']}.jpg", r["normalized"])
        if r["diff"] is not None:
            cv2.imwrite(f"{DEBUG_DIR}/diff_{ts}_tag{r['tag_id']}.jpg", r["diff"])
