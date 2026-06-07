import cv2
import numpy as np
import os
from pupil_apriltags import Detector

TAG_SIZE = 100
DIFF_MASK_THRESH = 35     # how different two templates must be to count as "discriminating"

detector = Detector(families="tag36h11")

# Multiple sample images per defect type, e.g. {"triangle": [img, ...], "circle": [img, ...]}
templates: dict[str, list] = {}
# Mask of pixels where the shape regions differ between classes. Built on load.
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
    """Load template_<label>_<n>.jpg files, grouped by label into sample lists."""
    templates.clear()
    ref_dir = _ref_dir()
    if not os.path.isdir(ref_dir):
        print("No references directory.")
        return
    for fname in sorted(os.listdir(ref_dir)):
        if fname.startswith("template_") and fname.endswith(".jpg"):
            stem = fname[len("template_"):-len(".jpg")]
            label = stem.rsplit("_", 1)[0] if "_" in stem else stem  # strip trailing index
            img = cv2.imread(os.path.join(ref_dir, fname), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            templates.setdefault(label, []).append(cv2.resize(img, (TAG_SIZE, TAG_SIZE)))
    _build_diff_mask()
    if templates:
        counts = ", ".join(f"{k}×{len(v)}" for k, v in templates.items())
        print(f"Loaded templates: {counts}")
    else:
        print("No templates yet. Show a tag and press 1=triangle, 2=circle to capture.")


def _mean_template(label: str):
    """Average of all samples for a label."""
    stack = np.stack([t.astype(np.float32) for t in templates[label]])
    return stack.mean(axis=0)


def _build_diff_mask():
    """Mask of pixels where class mean-templates differ — i.e. where the shapes are."""
    global diff_mask
    diff_mask = None
    if len(templates) < 2:
        return
    means = [_mean_template(label).astype("uint8") for label in templates]
    acc = None
    for i in range(len(means)):
        for j in range(i + 1, len(means)):
            d = cv2.absdiff(means[i], means[j])
            acc = d if acc is None else cv2.max(acc, d)
    _, m = cv2.threshold(acc, DIFF_MASK_THRESH, 255, cv2.THRESH_BINARY)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
    if cv2.countNonZero(m) > 20:
        diff_mask = m
        print(f"Diff mask built: {cv2.countNonZero(m)} discriminating pixels")
    else:
        print("WARNING: diff mask nearly empty — templates too similar. Recapture distinct shapes.")


def save_template(crop, label: str):
    ref_dir = _ref_dir()
    os.makedirs(ref_dir, exist_ok=True)
    # Auto-increment sample index for this label
    existing = [f for f in os.listdir(ref_dir) if f.startswith(f"template_{label}_") and f.endswith(".jpg")]
    idx = len(existing)
    path = os.path.join(ref_dir, f"template_{label}_{idx}.jpg")
    cv2.imwrite(path, cv2.resize(crop, (TAG_SIZE, TAG_SIZE)))
    print(f"Saved sample '{label}' #{idx} -> {path}")
    load_reference()


def clear_templates():
    """Delete all template files."""
    ref_dir = _ref_dir()
    if os.path.isdir(ref_dir):
        for f in os.listdir(ref_dir):
            if f.startswith("template_") and f.endswith(".jpg"):
                os.remove(os.path.join(ref_dir, f))
    templates.clear()
    print("Cleared all templates.")


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

    # For each label, take the BEST (lowest) MSE across all its samples,
    # measured only within the discriminating region.
    errors = {}
    for label, samples in templates.items():
        errors[label] = min(
            float(((norm_f - s.astype(np.float32)) ** 2)[mask].mean())
            for s in samples
        )

    ranked = sorted(errors.items(), key=lambda kv: kv[1])  # ascending
    best_label, best_err = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else best_err

    gap = (runner_up - best_err) / runner_up * 100 if runner_up > 0 else 0
    print(f"err — {', '.join(f'{k}:{v:.0f}' for k, v in ranked)}  (gap {gap:.0f}%)")

    # Always commit to the lower-error label; the 7-frame vote smooths out
    # the occasional noisy frame. No "unknown" so the label stays consistent.
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
