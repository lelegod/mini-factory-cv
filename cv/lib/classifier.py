import cv2
import numpy as np
import os
from pupil_apriltags import Detector

TAG_SIZE = 100
DIFF_THRESHOLD = 30       # pixel diff threshold for shape detection
DEFECT_MIN_AREA = 50      # minimum contour area to consider a defect shape
NORMAL_THRESHOLD = 5     # mean diff below this = normal

detector = Detector(families="tag36h11")
reference_img = None


def load_reference():
    global reference_img
    path = os.path.join(os.path.dirname(__file__), "..", "references", "reference.jpg")
    if os.path.exists(path):
        reference_img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        reference_img = cv2.resize(reference_img, (TAG_SIZE, TAG_SIZE))
        print(f"Reference loaded from {path}")
    else:
        print("No reference found. Point camera at a clean tag and press R to save one.")


def save_reference(crop):
    ref_dir = os.path.join(os.path.dirname(__file__), "..", "references")
    os.makedirs(ref_dir, exist_ok=True)
    path = os.path.join(ref_dir, "reference.jpg")
    cv2.imwrite(path, crop)
    print(f"Reference saved to {path}")
    load_reference()


def normalize_tag(frame, tag):
    """Warp detected tag region into a flat TAG_SIZE x TAG_SIZE grayscale image."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    src = tag.corners.astype(np.float32)
    dst = np.array([
        [0, TAG_SIZE - 1],
        [TAG_SIZE - 1, TAG_SIZE - 1],
        [TAG_SIZE - 1, 0],
        [0, 0],
    ], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(gray, M, (TAG_SIZE, TAG_SIZE))


def classify_diff_shape(diff):
    """Given a diff image, classify the shape of the defect region."""
    _, thresh = cv2.threshold(diff, DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)

    # clean up noise with morphological closing
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return "unknown", thresh

    # filter out tiny noise contours, take the largest
    significant = [c for c in contours if cv2.contourArea(c) >= DEFECT_MIN_AREA]
    if not significant:
        return "unknown", thresh

    largest = max(significant, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    perimeter = cv2.arcLength(largest, True)

    if perimeter == 0:
        return "unknown", thresh

    # circularity: 1.0 = perfect circle
    circularity = 4 * np.pi * area / (perimeter ** 2)

    # polygon approximation with tighter epsilon for cleaner shapes
    approx = cv2.approxPolyDP(largest, 0.03 * perimeter, True)
    sides = len(approx)

    print(f"shape — circularity: {circularity:.2f}, sides: {sides}, area: {area:.0f}")

    if circularity > 0.60:
        return "circle", thresh

    if sides == 3:
        return "triangle", thresh

    # looser fallback — elongated/irregular but low sides = triangle-ish
    if sides <= 4 and circularity < 0.4:
        return "triangle", thresh

    return "unknown", thresh


def classify_tag(normalized):
    """
    Compare normalized tag against reference.
    Returns (status, defect_type, diff_image)
      status: "normal" | "defective"
      defect_type: None | "circle" | "triangle" | "unknown"
    """
    if reference_img is None:
        return "no_reference", None, None

    diff = cv2.absdiff(normalized, reference_img)
    diff = cv2.GaussianBlur(diff, (5, 5), 0)

    print(f"diff mean: {diff.mean():.2f} ({'normal' if diff.mean() < NORMAL_THRESHOLD else 'defective'})")

    if diff.mean() < NORMAL_THRESHOLD:
        return "normal", None, diff

    defect_type, thresh = classify_diff_shape(diff)
    return "defective", defect_type, thresh


def detect_and_classify(frame):
    """
    Run full pipeline on a frame.
    Returns list of dicts: {tag_id, corners, center, status, defect_type, diff}
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tags = detector.detect(gray)

    results = []
    for tag in tags:
        normalized = normalize_tag(frame, tag)
        status, defect_type, diff = classify_tag(normalized)
        results.append({
            "tag_id": tag.tag_id,
            "corners": tag.corners.astype(np.int32),
            "center": tag.center.astype(np.int32),
            "normalized": normalized,
            "status": status,
            "defect_type": defect_type,
            "diff": diff,
        })

    return results


def draw_results(frame, results):
    """Draw tag outlines, fill overlays, and labels onto frame."""
    colors = {
        "normal": (0, 255, 0),
        "defective": (0, 0, 255),
        "no_reference": (128, 128, 128),
    }

    for r in results:
        color = colors.get(r["status"], (128, 128, 128))
        pts = r["corners"].reshape((-1, 1, 2))

        # semi-transparent fill
        overlay = frame.copy()
        cv2.fillPoly(overlay, [r["corners"]], color)
        cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

        # outline
        cv2.polylines(frame, [pts], True, color, 2)

        # label
        cx, cy = r["center"]
        label = r["status"]
        if r["defect_type"]:
            label += f" ({r['defect_type']})"
        cv2.putText(frame, label, (cx - 50, cy - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        cv2.putText(frame, f"ID:{r['tag_id']}", (cx - 20, cy + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    return frame
