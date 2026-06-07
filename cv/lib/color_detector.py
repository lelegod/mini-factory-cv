import cv2
import numpy as np


def find_red_box(frame):
    """
    Find the red/orange tape box in a color frame using HSV masking.
    Returns the cropped region inside it, or (full frame, None) if not found.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Red/orange wraps around 0 and 180 in HSV
    low1 = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([15, 255, 255]))
    low2 = cv2.inRange(hsv, np.array([160, 80, 80]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(low1, low2)

    # Close gaps in the tape outline so it forms a solid blob
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return frame, None

    # Largest red contour = the box
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 5000:
        return frame, None

    x, y, w, h = cv2.boundingRect(largest)

    # Crop slightly inside the tape so we get the contents, not the tape itself
    pad = int(min(w, h) * 0.05)
    x1, y1 = x + pad, y + pad
    x2, y2 = x + w - pad, y + h - pad
    crop = frame[y1:y2, x1:x2]

    if crop.size == 0:
        return frame, None

    return crop, (x, y, w, h)
