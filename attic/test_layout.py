#!/usr/bin/env python3
"""
Test harness for layout engine v3.

Usage:
  # Preset mode
  python test_layout.py face_off 2 -s 42
  python test_layout.py -a

  # Explicit knobs
  python test_layout.py --scale dominant --arrangement offset --density sparse -n 2

  # Aspect ratio support
  python test_layout.py hero_journey 2 --width 1024 --height 576
  python test_layout.py close_group 2 --width 576 --height 1024
  python test_layout.py -a --width 1024 --height 576

  # Full knob matrix
  python test_layout.py -m -n 2
"""

import sys
import argparse
sys.path.insert(0, ".")
from layout_engine import compute_layout, resolve_knobs, SCENE_PRESETS

SCENE_TYPES = list(SCENE_PRESETS.keys())
SCALES = ["equal", "dominant", "environmental"]
ARRANGEMENTS = ["opposing", "clustered", "offset", "scattered"]
DENSITIES = ["sparse", "balanced", "dense"]


def _show(scene_type, num_subjects, seed, knobs_override, width, height):
    if num_subjects == 0:
        print("  (no subjects — environmental shot)")
        return
    
    results = compute_layout(
        scene_type=scene_type if scene_type else None,
        num_subjects=num_subjects,
        seed=seed,
        width=width, height=height,
        **knobs_override,
    )
    
    for r in results:
        i = r["position_index"]
        box = r["box"]
        print(f"\n  Subject {i + 1}:")
        print(f"    box:    [{box[0]:>4}, {box[1]:>4}, {box[2]:>4}, {box[3]:>4}]")
        w, h = box[3] - box[1], box[2] - box[0]
        print(f"    size:   {w}×{h} ({w*h:,} px²)")
        print(f"    spatial: {r['spatial']}")
    
    print()
    _ascii_preview(results, width, height)


def _ascii_preview(results, width=1024, height=1024):
    """Render ASCII grid at correct aspect ratio."""
    aspect = width / height
    
    # Target ~44 chars wide, scale height to match aspect
    gw = 44
    gh = max(8, min(30, round(gw / aspect)))
    
    grid = [["." for _ in range(gw)] for _ in range(gh)]
    labels = "ABCDEFGH"
    
    for r in results:
        i = r["position_index"]
        box = r["box"]
        ymin, xmin, ymax, xmax = box
        
        gx1 = int(xmin / 1000 * gw)
        gx2 = max(int(xmax / 1000 * gw), gx1 + 1)
        gy1 = int(ymin / 1000 * gh)
        gy2 = max(int(ymax / 1000 * gh), gy1 + 1)
        
        label = labels[i] if i < len(labels) else "?"
        
        for y in range(gy1, min(gy2, gh)):
            for x in range(gx1, min(gx2, gw)):
                grid[y][x] = label.lower()
        for y in range(gy1, min(gy2, gh)):
            if gx1 < gw: grid[y][gx1] = label
            if gx2 - 1 < gw and gx2 > gx1 + 1: grid[y][gx2 - 1] = label
        for x in range(gx1, min(gx2, gw)):
            if gy1 < gh: grid[gy1][x] = label
            if gy2 - 1 < gh and gy2 > gy1 + 1: grid[gy2 - 1][x] = label
    
    dim_str = f"{width}×{height}"
    orient = "landscape" if width > height else ("portrait" if height > width else "square")
    header = f"  {dim_str} ({orient}, {width/height:.2f}:1)"
    print(header)
    print("  ┌" + "─" * gw + "┐")
    for row in grid:
        print("  │" + "".join(row) + "│")
    print("  └" + "─" * gw + "┘")
    
    legend = "  ".join(f"{labels[r['position_index']]}=Subject{r['position_index']+1}" for r in results)
    if legend:
        print("  " + legend)


def run_all(seed, width, height):
    print("=" * 60)
    dim_str = f"{width}×{height}"
    print(f"ALL PRESETS × SUBJECT COUNTS — {dim_str}")
    print("=" * 60)
    for st in SCENE_TYPES:
        knobs = resolve_knobs(st)
        print(f"\n{'━' * 50}")
        print(f"  {st}  (scale={knobs['scale']}, arrangement={knobs['arrangement']}, density={knobs['density']})")
        print(f"{'━' * 50}")
        for n in range(0, 5):
            print(f"\n  ── {n} subjects (seed={seed}) ──")
            _show(st, n, seed, {}, width, height)


def run_knob_matrix(seed, num_subjects, width, height):
    print("=" * 60)
    dim_str = f"{width}×{height}"
    print(f"KNOB MATRIX — {num_subjects} subjects, {dim_str}, seed={seed}")
    print("=" * 60)
    for scale in SCALES:
        for arr in ARRANGEMENTS:
            for density in DENSITIES:
                print(f"\n{'─' * 50}")
                print(f"  scale={scale}  arrangement={arr}  density={density}")
                print(f"{'─' * 50}")
                _show(None, num_subjects, seed,
                      {"scale": scale, "arrangement": arr, "density": density},
                      width, height)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Test the Scene Generator layout engine v3")
    p.add_argument("scene_type", nargs="?", default=None, choices=SCENE_TYPES + [None])
    p.add_argument("subjects", nargs="?", type=int, default=None)
    p.add_argument("-s", "--seed", type=int, default=42)
    p.add_argument("-n", "--num-subjects", type=int, default=None)
    p.add_argument("-a", "--all", action="store_true")
    p.add_argument("-m", "--matrix", action="store_true")
    p.add_argument("--scale", choices=SCALES, default=None)
    p.add_argument("--arrangement", choices=ARRANGEMENTS, default=None)
    p.add_argument("--density", choices=DENSITIES, default=None)
    p.add_argument("--width", type=int, default=1024, help="Canvas width in pixels")
    p.add_argument("--height", type=int, default=1024, help="Canvas height in pixels")
    
    args = p.parse_args()
    
    knob_overrides = {}
    if args.scale: knob_overrides["scale"] = args.scale
    if args.arrangement: knob_overrides["arrangement"] = args.arrangement
    if args.density: knob_overrides["density"] = args.density
    
    if args.matrix:
        n = args.num_subjects or args.subjects or 2
        run_knob_matrix(args.seed, n, args.width, args.height)
    elif args.all:
        run_all(args.seed, args.width, args.height)
    else:
        st = args.scene_type
        n = args.num_subjects or args.subjects or 2
        knobs = resolve_knobs(st, **knob_overrides)
        header = f"Scene: {st}" if st else "Custom"
        header += f" | Subjects: {n} | Seed: {args.seed} | {args.width}×{args.height}"
        header += f"\n  scale={knobs['scale']}  arrangement={knobs['arrangement']}  density={knobs['density']}"
        print(f"\n{header}\n")
        _show(st, n, args.seed, knob_overrides, args.width, args.height)
