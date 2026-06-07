import cv2
import numpy as np
import os
from pupil_apriltags import Detector

TAG_SIZE = 100
DIFF_MASK_THRESH = 35     # how different two templates must be to count as "discriminating"

detector = Detector(families="tag36h11")

# Template references per defect type, e.g. {"triangle": img, "circle": img}
templates: dict[str, "np.ndarray"] = {}
# Mask of pixels where templates disagree (the shape regions). Built on load.
diff_mask = None

# Temporal smoothing: recent defect_type votes per tag_id
VOTE_HISTORY = 7
_vote_buffers: dict[int, list[str]] = {}


def _ref_dir():
    return os.path.join(os.path.dirname(__file__), "..", "references")


def _smooth_defect_type(tag_id: int, defect_type: str) -> str:
    """Majority vote over recent frames so a single bad frame doesn't flip the label."""
    buf = _vote_buffers.setdefault(tag_id, [])
    buf.append(defect_type)
    if len(buf) > VOTE_HISTORY:
        buf.pop(0)
    votes = [v for v in buf if v != "unknown"] or buf
    return max(set(votes), key=votes.count)


def load_reference():
    """Load all template_<type>.jpg files from references/ as defect templates."""
    templates.clear()
    ref_dir = _ref_dir()
    if not os.path.isdir(ref_dir):
        print("No references directory.")
        return
    for fname in os.listdir(ref_dir):
        if fname.startswith("template_") and fname.endswith(".jpg"):
            label = fname[len("template_"):-len(".jpg")]
            img = cv2.imread(os.path.join(ref_dir, fname), cv2.IMREAD_GRAYSCALE)
            templates[label] = cv2.resize(img, (TAG_SIZE, TAG_SIZE))
    _build_diff_mask()
    if templates:
        print(f"Loaded templates: {', '.join(templates)}")
    else:
        print("No templates yet. Show a tag and press 1=triangle, 2=circle to capture.")


def _build_diff_mask():
    """Mask of pixels where the templates differ — i.e. where the shapes are."""
    global diff_mask
    diff_mask = None
    if len(templates) < 2:
        return
    imgs = list(templates.values())
    acc = None
    for i in range(len(imgs)):
        for j in range(i + 1, len(imgs)):
            d = cv2.absdiff(imgs[i], imgs[j])
            acc = d if acc is None else cv2.max(acc, d)
    _, m = cv2.threshold(acc, DIFF_MASK_THRESH, 255, cv2.THRESH_BINARY)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
    if cv2.countNonZero(m) > 20:
        diff_mask = m
        print(f"Diff mask built: {cv2.countNonZero(m)} discriminating pixels")


def save_template(crop, label: str):
    ref_dir = _ref_dir()
    os.makedirs(ref_dir, exist_ok=True)
    path = os.path.join(ref_dir, f"template_{label}.jpg")
    cv2.imwrite(path, cv2.resize(crop, (TAG_SIZE, TAG_SIZE)))
    print(f"Saved template '{label}' -> {path}")
    load_reference()


# Backwards-compat alias used by main.py's R key
def save_reference(crop):
    save_template(crop, "triangle")


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


def classify_tag(normalized):
    """
    Compare the normalized tag against each template ONLY within the diff mask
    (the region where templates differ — i.e. the drawn shapes). Lowest mean
    squared error in that region wins. This ignores the identical 90% of the
    tag and focuses on the discriminating shape.

    Returns (status, defect_type, debug_image)
    """
    if not templates:
        return "defective", "unknown", None

    if diff_mask is None:
        return "defective", "unknown", None

    mask = diff_mask > 0
    norm_f = normalized.astype(np.float32)

    # Mean squared error within the discriminating region (lower = better match)
    errors = {}
    for label, tmpl in templates.items():
        sq = (norm_f - tmpl.astype(np.float32)) ** 2
        errors[label] = float(sq[mask].mean())

    ranked = sorted(errors.items(), key=lambda kv: kv[1])  # ascending
    best_label, best_err = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else best_err

    print(f"err — {', '.join(f'{k}:{v:.0f}' for k, v in ranked)}")

    # Best must be clearly lower error than runner-up (>15% relative gap)
    if runner_up > 0 and (runner_up - best_err) / runner_up < 0.15:
        return "defective", "unknown", None

    return "defective", best_label, None


def detect_and_classify(frame):
    """
    Run full pipeline on a frame.
    Returns list of dicts: {tag_id, corners, center, status, defect_type, diff}
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Remove IR dot pattern noise with median blur
    gray = cv2.medianBlur(gray, 3)

    # Improve local contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    gray = clahe.apply(gray)

    tags = detector.detect(gray)

    results = []
    for tag in tags:
        normalized = normalize_tag(frame, tag)
        status, defect_type, diff = classify_tag(normalized)

        # Smooth the defect type across recent frames for this tag
        if defect_type is not None:
            defect_type = _smooth_defect_type(tag.tag_id, defect_type)

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
