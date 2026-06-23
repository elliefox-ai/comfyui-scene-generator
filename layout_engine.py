"""
Layout engine v3 — three compositional knobs + aspect-aware arrangement.

Knobs:
  scale_hierarchy: equal | dominant | environmental
  arrangement:     opposing | clustered | offset | scattered
  density:         sparse | balanced | dense

Scene types are just presets of these three values.

Aspect ratio (width/height) influences how subjects spread:
  - Landscape (w>h): wider horizontal spread, subjects can breathe horizontally
  - Portrait (h>w):  tighter horizontal spread, subjects stack more vertically
  - Square:          balanced, no axis preference

Boxes are Ideogram 4 format: [ymin, xmin, ymax, xmax] on a 0-1000 grid.
The grid is always 0-1000 regardless of actual pixel dimensions — the model
handles the mapping. But the *composition decisions* adapt to aspect ratio.
"""

import random
import math


# ── Presets ──────────────────────────────────────────────────────

# Scene types describe COMPOSITION, not genre.
# Genre comes from the scenario pack. This separation lets you mix
# any composition with any scenario (e.g. face_off + pirate_ship).
SCENE_PRESETS = {
    "face_off":       {"scale": "equal",        "arrangement": "opposing",  "density": "balanced"},
    "close_group":    {"scale": "equal",        "arrangement": "clustered", "density": "dense"},
    "hero_journey":   {"scale": "dominant",     "arrangement": "offset",    "density": "sparse"},
    "wide_vista":     {"scale": "environmental", "arrangement": "scattered", "density": "sparse"},
    "candid_moment":  {"scale": "equal",        "arrangement": "scattered", "density": "balanced"},
    "gathering":      {"scale": "equal",        "arrangement": "clustered", "density": "balanced"},
    "at_work":        {"scale": "dominant",     "arrangement": "offset",    "density": "balanced"},
    "atmospheric":    {"scale": "environmental", "arrangement": "offset",   "density": "sparse"},
    "spotlight":      {"scale": "dominant",     "arrangement": "offset",    "density": "sparse"},
}


# ── Box helpers ──────────────────────────────────────────────────

def _box(ymin, xmin, ymax, xmax):
    return [
        max(0, min(1000, int(ymin))),
        max(0, min(1000, int(xmin))),
        max(0, min(1000, int(ymax))),
        max(0, min(1000, int(xmax))),
    ]


def _safe_y(y_base, h, margin=0.02):
    """Clamp y_base so the box [y_base, y_base+h] fits within [0, 1].
    Used before multiplying by 1000."""
    y_max = max(0.0, 1.0 - h - margin)
    return min(y_base, y_max)


def _wh(box):
    return box[3] - box[1], box[2] - box[0]


def _area(box):
    w, h = _wh(box)
    return w * h


# ── Aspect ratio helpers ─────────────────────────────────────────

def _classify_aspect(width, height):
    """Return (aspect, orientation) where aspect is width/height and
    orientation is 'landscape', 'portrait', or 'square'."""
    aspect = width / height if height else 1.0
    if aspect > 1.15:
        return aspect, "landscape"
    elif aspect < 0.87:
        return aspect, "portrait"
    else:
        return aspect, "square"


def _horizontal_bias(aspect, orientation):
    """How much to favor horizontal spread (0=vertical bias, 1=horizontal bias)."""
    if orientation == "landscape":
        return min(1.0, aspect * 0.6)  # 1.5 → 0.9, 2.0 → 1.0
    elif orientation == "portrait":
        return max(0.0, 1.0 - (1.0 / aspect) * 0.6)  # 0.66 → 0.1, 0.5 → -0.2→0
    else:
        return 0.5


def _aspect_scale(orientation):
    """Uniform scale factor for box size based on aspect ratio.
    Keeps height/width ratio consistent — only overall scale changes."""
    if orientation == "portrait":
        return 0.85  # uniformly smaller to fit narrow frames
    elif orientation == "landscape":
        return 0.95  # slightly smaller to use horizontal breathing room
    return 1.0  # square: full size



# ── Scale sizes (as fraction of frame) ───────────────────────────

_SCALE_SIZES = {
    "equal": [
        {"w": (0.15, 0.22), "h": (0.48, 0.62)},
    ],
    "dominant": [
        {"w": (0.18, 0.26), "h": (0.62, 0.78)},  # hero
        {"w": (0.07, 0.11), "h": (0.24, 0.34)},  # others
    ],
    "environmental": [
        {"w": (0.08, 0.12), "h": (0.28, 0.38)},
    ],
}


def _get_size(scale_mode, position, total, rng, orientation, shot_width="medium", frame_w=1024, frame_h=1024,
               framing="eye_level"):
    """Get width/height fractions for a subject.

    Fractions are normalized so the PIXEL aspect ratio of the resulting box
    stays consistent regardless of frame orientation. Without this, portrait
    frames produce tall thin boxes and landscape produces short wide ones.
    """
    sizes = _SCALE_SIZES[scale_mode]

    if scale_mode == "dominant" and position == 0:
        sz = sizes[0]
    elif scale_mode == "dominant":
        sz = sizes[1]
    else:
        sz = sizes[0]

    w = rng.uniform(*sz["w"])
    h = rng.uniform(*sz["h"])

    # ── Pixel-ratio normalization ──
    # Boost the fraction on the shorter frame axis so box pixel shape
    # stays consistent across orientations.
    if frame_h > frame_w:  # portrait
        w *= (frame_h / frame_w)
    elif frame_w > frame_h:  # landscape
        h *= (frame_w / frame_h)

    # Uniform scale for aspect ratio (overall size adjustment)
    scale = _aspect_scale(orientation)
    # Shot width scale — close shots fill more of the frame
    sw_scale = _SHOT_WIDTH_OVERRIDE.get((scale_mode, shot_width),
                                   _SHOT_WIDTH_SCALE.get(shot_width, 1.0))
    # Crowd factor — shrink each subject slightly as total count goes up
    crowd = _CROWD_FACTOR.get(total, 0.62)
    # Framing height scale — foreshorten from above, elongate from below
    fh_scale = _FRAMING_HEIGHT_SCALE.get(framing, 1.0)
    total_scale = scale * sw_scale * crowd
    w *= total_scale
    h *= total_scale * fh_scale

    # Clamp — allow up to 98% coverage for close shots
    max_cov = 0.98 if shot_width == "close" else 0.92
    w = min(w, max_cov)
    h = min(h, max_cov)

    return w, h


# ── Density → frame occupancy targets ────────────────────────────

# Framing modes shift y-position baseline AND height multiplier.
# High angle foreshortens subjects (they appear shorter in frame).
# Low angle elongates them (they loom upward).
_FRAMING_Y_OFFSET = {
    "eye_level":  0.00,   # default — horizon level
    "high_angle": 0.10,   # camera looks down — subjects pushed lower in frame
    "low_angle":  -0.08,  # camera looks up — subjects pushed higher
    "dutch":      0.03,   # slight asymmetry (approximated via y shift)
}

_FRAMING_HEIGHT_SCALE = {
    "eye_level":  1.00,   # default — normal proportions
    "high_angle": 0.82,   # foreshortened from above — subjects appear shorter
    "low_angle":  1.15,   # elongated from below — subjects loom taller
    "dutch":      0.97,   # very slight compression
}

# Text descriptions injected into the prompt for each framing mode.
# These go into the HLD so Ideogram understands the camera angle.
_FRAMING_TEXT = {
    "eye_level":  "",
    "high_angle": " Shot from a high angle, looking downward at the subjects.",
    "low_angle":  " Shot from a low angle, looking upward at the subjects.",
    "dutch":      " Shot with a canted Dutch tilt angle.",
}

# Crowd factor — each subject shrinks slightly as count goes up so they all fit.
# Applied multiplicatively on top of scale + shot_width.
_CROWD_FACTOR = {
    1: 1.00,
    2: 1.00,
    3: 0.92,
    4: 0.82,
    5: 0.72,
    6: 0.62,
}

# Shot width → scale multiplier, PER scale mode.
# Close environmental shouldn't fully override environmental — it should mitigate it.
# So environmental gets a bigger close multiplier to pull subjects nearer without
# making them as large as equal-close.
_SHOT_WIDTH_SCALE = {
    "close":  1.55,   # tight crop — subjects dominate the frame
    "medium": 1.00,   # baseline — balanced character/environment
    "wide":   0.85,   # subjects smaller but still clearly visible
}

# Override multipliers for specific (scale_mode, shot_width) combos.
# These REPLACE the default _SHOT_WIDTH_SCALE value for that combo.
_SHOT_WIDTH_OVERRIDE = {
    ("environmental", "close"):  2.50,  # subjects nearer but still smaller than intimate
    ("environmental", "medium"): 1.15,  # standard establishing — slightly larger
    ("environmental", "wide"):   1.00,  # small figures in vast space, but clearly visible
}

_DENSITY_PARAMS = {
    "sparse":   {"y_start": (0.28, 0.40), "spread": 0.85},
    "balanced": {"y_start": (0.22, 0.34), "spread": 0.72},
    "dense":    {"y_start": (0.18, 0.28), "spread": 0.60},
}


# ── Arrangement engines ──────────────────────────────────────────
#
# Each takes (n, sizes, rng, density_params, aspect_info) where
# aspect_info = (aspect_ratio, orientation, h_bias, aspect_scale)

def _arrange_opposing(n, sizes, rng, dp, ai):
    """Mirrored across center axis — subjects face in toward each other."""
    aspect, orient, h_bias, a_scale = ai
    boxes = []
    y_base = rng.uniform(*dp["y_start"])
    # Clamp y so tallest box fits in frame
    max_h = max(s[1] for s in sizes)
    y_base = _safe_y(y_base, max_h)
    
    if orient == "portrait":
        # Narrow frame: tighter horizontal gap, but still side-by-side
        # (avoid vertical stacking — keeps subjects at similar eye level)
        gap = rng.uniform(0.03, 0.08)
    else:
        gap = rng.uniform(0.10, 0.22)
    
    if n == 1:
        side = rng.choice(["left", "right"])
        w, h = sizes[0]
        if side == "left":
            x = rng.uniform(0.04, 0.12)
        else:
            x = rng.uniform(0.88 - w, 0.96 - w)
        boxes.append(_box(y_base * 1000, x * 1000,
                          (y_base + h) * 1000, (x + w) * 1000))
    
    elif n == 2:
        w0, h0 = sizes[0]
        w1, h1 = sizes[1] if len(sizes) > 1 else sizes[0]
        
        # Always side-by-side, same y level — keeps eye lines consistent
        lx = rng.uniform(0.03, 0.08)
        boxes.append(_box(y_base * 1000, lx * 1000,
                          (y_base + h0) * 1000, (lx + w0) * 1000))
        rx = lx + w0 + gap
        boxes.append(_box(y_base * 1000, rx * 1000,
                          (y_base + h1) * 1000, (rx + w1) * 1000))
    
    elif n == 3:
        w0, h0 = sizes[0]
        w1, h1 = sizes[1] if len(sizes) > 1 else sizes[0]
        # Use computed widths, positioned left-center-right
        lx = rng.uniform(0.02, 0.06)
        rx = 0.98 - w1
        cx = (1 - w0) / 2
        boxes.append(_box(y_base * 1000, lx * 1000,
                          (y_base + h0) * 1000, (lx + w0) * 1000))
        boxes.append(_box(y_base * 1000, rx * 1000,
                          (y_base + h1) * 1000, (rx + w1) * 1000))
        # Observer center, slightly offset
        oy = rng.uniform(0.04, 0.12)
        boxes.append(_box(oy * 1000, cx * 1000,
                          (oy + h0) * 1000, (cx + w0) * 1000))
    
    elif n >= 4:
        w0, h0 = sizes[0]
        w1, h1 = sizes[1] if len(sizes) > 1 else sizes[0]
        # Spread across using computed widths
        gap = rng.uniform(0.02, 0.05)
        # Alternate sizes across the row
        row = []
        for i in range(n):
            sz = sizes[min(i, len(sizes) - 1)]
            row.append(sz)
        total_w = sum(s[0] for s in row) + gap * (n - 1)
        start_x = max(0.02, min((1 - total_w) / 2, 1.0 - total_w - 0.02))
        x = start_x
        for i, (wi, hi) in enumerate(row):
            y_off = rng.uniform(-0.02, 0.05)
            y_i = max(0.01, min(y_base + y_off, 1.0 - hi - 0.01))
            boxes.append(_box(y_i * 1000, x * 1000,
                              (y_i + hi) * 1000, (x + wi) * 1000))
            x += wi + gap
    
    return boxes


def _arrange_clustered(n, sizes, rng, dp, ai):
    """Grouped close together, overlapping, with randomized center of mass."""
    aspect, orient, h_bias, a_scale = ai
    boxes = []
    y_start = rng.uniform(*dp["y_start"])
    max_h = max(s[1] for s in sizes)
    y_start = _safe_y(y_start, max_h)
    # Randomize cluster center — not always dead center
    cluster_bias = rng.uniform(-0.15, 0.15)
    
    if n == 1:
        w, h = sizes[0]
        x = (1.0 - w) / 2
        boxes.append(_box(y_start * 1000, x * 1000,
                          (y_start + h) * 1000, (x + w) * 1000))
    
    elif n == 2:
        w0, h0 = sizes[0]
        w1, h1 = sizes[1] if len(sizes) > 1 else sizes[0]
        overlap = rng.uniform(0.04, 0.10)
        
        total_w = w0 + w1 - overlap
        start_x = (1.0 - total_w) / 2 + cluster_bias
        start_x = max(0.03, min(start_x, 1.0 - total_w - 0.03))
        boxes.append(_box(y_start * 1000, start_x * 1000,
                          (y_start + h0) * 1000, (start_x + w0) * 1000))
        boxes.append(_box((y_start - 0.02) * 1000, (start_x + w0 - overlap) * 1000,
                          (y_start - 0.02 + h1) * 1000, (start_x + total_w) * 1000))
    
    elif n == 3:
        w0, h0 = sizes[0]
        w1, h1 = sizes[1] if len(sizes) > 1 else sizes[0]
        overlap = rng.uniform(0.02, 0.05)
        total_w = 2*w0 + w1 - 2*overlap
        start_x = max(0.04, (1.0 - total_w) / 2 + cluster_bias)
        start_x = min(start_x, 1.0 - total_w - 0.03)
        x0 = start_x
        x1 = x0 + w0 - overlap
        x2 = x1 + w1 - overlap
        boxes.append(_box(y_start * 1000, x0 * 1000,
                          (y_start + h0) * 1000, (x0 + w0) * 1000))
        boxes.append(_box((y_start - 0.02) * 1000, x1 * 1000,
                          (y_start - 0.02 + h1) * 1000, (x1 + w1) * 1000))
        boxes.append(_box((y_start + 0.04) * 1000, x2 * 1000,
                          (y_start + 0.04 + h0) * 1000, (x2 + w0) * 1000))
    
    elif n >= 4:
        # Alternate between hero and secondary sizes, with overlap
        overlap = rng.uniform(0.02, 0.04)
        # Build the row left-to-right, alternating size types
        row_sizes = []
        for i in range(n):
            sz = sizes[min(i, len(sizes) - 1)]
            row_sizes.append(sz)
        total_w = sum(s[0] for s in row_sizes) - overlap * (n - 1)
        start_x = max(0.03, (1.0 - total_w) / 2 + cluster_bias)
        start_x = min(start_x, 1.0 - total_w - 0.03)
        
        x = start_x
        for i, (w_i, h_i) in enumerate(row_sizes):
            # Slight vertical stagger for natural feel
            y_stagger = rng.uniform(-0.03, 0.04)
            y_i = y_start + y_stagger
            y_i = max(0.01, min(y_i, 1.0 - h_i - 0.01))
            boxes.append(_box(y_i * 1000, x * 1000,
                              (y_i + h_i) * 1000, (x + w_i) * 1000))
            x += w_i - overlap
    
    return boxes


def _arrange_offset(n, sizes, rng, dp, ai):
    """One side weighted (hero foreground), other side lighter (distant)."""
    aspect, orient, h_bias, a_scale = ai
    boxes = []
    y_start = rng.uniform(*dp["y_start"])
    max_h = max(s[1] for s in sizes)
    y_start = _safe_y(y_start, max_h)
    
    if n == 1:
        w, h = sizes[0]
        side = rng.choice(["left", "right", "center"])
        if side == "left":
            x = rng.uniform(0.05, 0.15)
        elif side == "right":
            x = rng.uniform(0.85 - w, 0.95 - w)
        else:
            x = (1.0 - w) / 2
        boxes.append(_box(y_start * 1000, x * 1000,
                          (y_start + h) * 1000, (x + w) * 1000))
    
    elif n == 2:
        w0, h0 = sizes[0]
        w1, h1 = sizes[1]
        hero_side = rng.choice(["left", "right"])
        
        if hero_side == "left":
            hx = rng.uniform(0.04, 0.10)
            dx = rng.uniform(0.60, 0.75)
        else:
            hx = rng.uniform(0.90 - w0, 0.96 - w0)
            dx = rng.uniform(0.10, 0.25)
        
        hy = y_start
        dy = rng.uniform(0.12, 0.22)
        
        boxes.append(_box(hy * 1000, hx * 1000,
                          (hy + h0) * 1000, (hx + w0) * 1000))
        boxes.append(_box(dy * 1000, dx * 1000,
                          (dy + h1) * 1000, (dx + w1) * 1000))
    
    elif n == 3:
        w0, h0 = sizes[0]
        w1, h1 = sizes[1]
        
        hero_side = rng.choice(["left", "right"])
        if hero_side == "left":
            hx = rng.uniform(0.03, 0.08)
            boxes.append(_box(y_start * 1000, hx * 1000,
                              (y_start + h0) * 1000, (hx + w0) * 1000))
            x1 = rng.uniform(0.50, 0.60)
            y1 = rng.uniform(0.25, 0.35)
            boxes.append(_box(y1 * 1000, x1 * 1000,
                              (y1 + h1) * 1000, (x1 + w1) * 1000))
            x2 = rng.uniform(0.65, 0.75)
            y2 = rng.uniform(0.08, 0.15)
            boxes.append(_box(y2 * 1000, x2 * 1000,
                              (y2 + h1) * 1000, (x2 + w1) * 1000))
        else:
            hx = 0.97 - w0
            boxes.append(_box(y_start * 1000, hx * 1000,
                              (y_start + h0) * 1000, (hx + w0) * 1000))
            x1 = rng.uniform(0.10, 0.20)
            y1 = rng.uniform(0.25, 0.35)
            boxes.append(_box(y1 * 1000, x1 * 1000,
                              (y1 + h1) * 1000, (x1 + w1) * 1000))
            x2 = rng.uniform(0.05, 0.15)
            y2 = rng.uniform(0.08, 0.15)
            boxes.append(_box(y2 * 1000, x2 * 1000,
                              (y2 + h1) * 1000, (x2 + w1) * 1000))
    
    elif n >= 4:
        w0, h0 = sizes[0]
        w1, h1 = sizes[1] if len(sizes) > 1 else sizes[0]
        hero_side = rng.choice(["left", "right"])
        if hero_side == "left":
            hx = rng.uniform(0.02, 0.07)
            boxes.append(_box(y_start * 1000, hx * 1000,
                              (y_start + h0) * 1000, (hx + w0) * 1000))
            # Scatter remaining subjects across the right side
            for i in range(1, n):
                # Spread x across right portion, y varies for depth
                t = i / max(n - 1, 1)
                sx = rng.uniform(0.25 + t * 0.35, 0.45 + t * 0.40)
                sy = rng.uniform(0.05, 0.35)
                boxes.append(_box(sy * 1000, sx * 1000,
                                  (sy + h1) * 1000, (sx + w1) * 1000))
        else:
            hx = 0.97 - w0
            boxes.append(_box(y_start * 1000, hx * 1000,
                              (y_start + h0) * 1000, (hx + w0) * 1000))
            for i in range(1, n):
                t = i / max(n - 1, 1)
                sx = rng.uniform(0.05 + (1-t) * 0.10, 0.15 + (1-t) * 0.20)
                sy = rng.uniform(0.05, 0.35)
                boxes.append(_box(sy * 1000, sx * 1000,
                                  (sy + h1) * 1000, (sx + w1) * 1000))
    
    return boxes


def _arrange_scattered(n, sizes, rng, dp, ai):
    """Natural spread, adapts spread axis to aspect ratio."""
    aspect, orient, h_bias, a_scale = ai
    boxes = []
    y_start = rng.uniform(*dp["y_start"])
    max_h = max(s[1] for s in sizes)
    y_start = _safe_y(y_start, max_h)
    
    if n == 0:
        return []
    
    if n == 1:
        w, h = sizes[0]
        x = rng.uniform(0.25, 0.60)
        y = y_start + rng.uniform(-0.03, 0.05)
        boxes.append(_box(y * 1000, x * 1000,
                          (y + h) * 1000, (x + w) * 1000))
    
    elif n >= 2:
        spacing = 1.0 / n
        for i in range(n):
            w, h = sizes[min(i, len(sizes) - 1)]
            
            x_center = spacing * (i + 0.5)
            
            # Jitter amount adapts to aspect — more horizontal room in landscape
            x_jitter = 0.06 + h_bias * 0.04
            y_jitter = 0.04 + (1.0 - h_bias) * 0.04
            
            x_center += rng.uniform(-x_jitter, x_jitter)
            x_center = max(w / 2 + 0.02, min(1.0 - w / 2 - 0.02, x_center))
            
            y = y_start + rng.uniform(-y_jitter, y_jitter)
            
            boxes.append(_box(y * 1000, (x_center - w/2) * 1000,
                              (y + h) * 1000, (x_center + w/2) * 1000))
    
    return boxes


_ARRANGEMENTS = {
    "opposing":  _arrange_opposing,
    "clustered": _arrange_clustered,
    "offset":    _arrange_offset,
    "scattered": _arrange_scattered,
}


# ── Spatial language ─────────────────────────────────────────────

def _scale_desc(box):
    w, h = _wh(box)
    area = w * h
    if area > 250_000:
        return "close foreground, dominating the frame"
    elif area > 120_000:
        return "foreground, prominent in frame"
    elif area > 60_000:
        return "mid-distance, clearly visible"
    elif area > 25_000:
        return "at a distance, smaller in frame"
    else:
        return "far background, small in frame"


def _position_desc(box):
    ymin, xmin, ymax, xmax = box
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    
    if cx < 250:   h = "left side"
    elif cx < 400: h = "left-of-center"
    elif cx < 600: h = "center"
    elif cx < 750: h = "right-of-center"
    else:          h = "right side"
    
    if cy < 250:   v = "upper frame"
    elif cy < 450: v = "mid-upper frame"
    elif cy < 600: v = "center frame"
    elif cy < 800: v = "lower frame"
    else:          v = "bottom of frame"
    
    return f"{h}, {v}"


def _facing_desc(arrangement, position, total):
    if total < 2:
        return ""
    if arrangement == "opposing":
        if position == 0: return "facing right toward the other figure"
        if position == 1: return "facing left toward the other figure"
        return "observing from a distance"
    if arrangement == "clustered":
        return "facing toward the others"
    if arrangement == "offset":
        if position == 0: return "facing away, toward the distance"
        return "facing toward the viewer"
    return ""


def spatial_desc(box, arrangement, position, total):
    parts = [_scale_desc(box), _position_desc(box)]
    facing = _facing_desc(arrangement, position, total)
    if facing:
        parts.append(facing)
    return ", ".join(parts)


# ── Main entry point ─────────────────────────────────────────────

def compute_layout(scene_type=None, num_subjects=2, seed=42,
                   scale=None, arrangement=None, density=None,
                   framing="eye_level", shot_width="medium",
                   width=1024, height=1024):
    """
    Compute bounding boxes for subjects.
    
    Can be called with a scene_type preset, or with explicit knobs.
    Explicit knobs override the preset.
    
    width/height influence how subjects spread across the frame.
    Boxes are always in 0-1000 normalized grid.
    
    Returns list of {box, spatial, position_index}.
    """
    rng = random.Random(seed)
    
    # Resolve knobs
    preset = SCENE_PRESETS.get(scene_type, {}) if scene_type else {}
    
    scale_mode = scale or preset.get("scale", "equal")
    arr_mode = arrangement or preset.get("arrangement", "scattered")
    density_mode = density or preset.get("density", "balanced")
    
    if num_subjects <= 0:
        return []
    
    # Compute aspect info
    aspect, orient = _classify_aspect(width, height)
    h_bias = _horizontal_bias(aspect, orient)
    a_scale = _aspect_scale(orient)
    aspect_info = (aspect, orient, h_bias, a_scale)
    
    # Compute sizes for each subject (pixel-ratio-normalized + shot-width-scaled)
    sizes = []
    for i in range(num_subjects):
        sizes.append(_get_size(scale_mode, i, num_subjects, rng, orient, shot_width, width, height,
                                 framing=framing))
    
    # Get density parameters (with framing y-offset applied)
    density_params = dict(_DENSITY_PARAMS[density_mode])
    y_offset = _FRAMING_Y_OFFSET.get(framing, 0.0)
    density_params["y_start"] = tuple(y + y_offset for y in density_params["y_start"])
    
    # Arrange
    arrange_fn = _ARRANGEMENTS[arr_mode]
    boxes = arrange_fn(num_subjects, sizes, rng, density_params, aspect_info)
    
    # Build results
    results = []
    for i, box in enumerate(boxes):
        results.append({
            "box": box,
            "spatial": spatial_desc(box, arr_mode, i, num_subjects),
            "position_index": i,
        })
    
    return results


def resolve_knobs(scene_type=None, scale=None, arrangement=None, density=None):
    """Returns the effective knob values given overrides."""
    preset = SCENE_PRESETS.get(scene_type, {}) if scene_type else {}
    return {
        "scale": scale or preset.get("scale", "equal"),
        "arrangement": arrangement or preset.get("arrangement", "scattered"),
        "density": density or preset.get("density", "balanced"),
    }
