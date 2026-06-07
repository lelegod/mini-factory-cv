import cv2
import numpy as np
import os
from pupil_apriltags import Detector

TAG_SIZE = 100
MATCH_MIN_SCORE = 0.45    # below this, no template is a confident match
MATCH_MARGIN = 0.03       # winning template must beat runner-up by this much

detector = Detector(families="tag36h11")

# Template references per defect type, e.g. {"triangle": img, "circle": img}
templates: dict[str, "np.ndarray"] = {}

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
    if templates:
        print(f"Loaded templates: {', '.join(templates)}")
    else:
        print("No templates yet. Show a tag and press 1=triangle, 2=circle to capture.")


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
    Match the normalized tag against each defect template using normalized
    cross-correlation. The best-matching template's label is the defect type.

    Returns (status, defect_type, debug_image)
    """
    if not templates:
        return "defective", "unknown", None

    scores = {}
    for label, tmpl in templates.items():
        res = cv2.matchTemplate(normalized, tmpl, cv2.TM_CCOEFF_NORMED)
        scores[label] = float(res.max())

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_label, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0

    print(f"match — {', '.join(f'{k}:{v:.2f}' for k, v in ranked)}")

    # Need a confident, clearly-winning match
    if best_score < MATCH_MIN_SCORE or (best_score - runner_up) < MATCH_MARGIN:
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
