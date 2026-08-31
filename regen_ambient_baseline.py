#!/usr/bin/env python3
"""Regenerate /tmp/ambient_baseline.json — the byte-identical draw guard.

test_ambient.py compares current rolls against this snapshot, so it must
be REGENERATED after any deliberate change to the ambient banks or pool
list (content waves, pool additions). It exists to catch ACCIDENTAL
draw-order drift in between — regenerating is part of landing a wave,
not a way to silence a failure you don't understand.

Usage: python3 regen_ambient_baseline.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scene_ambient as am
from scene_ambient import SceneAmbientActivity

OUT = "/tmp/ambient_baseline.json"
SEEDS = 10  # per pool x treatment


def main():
    n = SceneAmbientActivity()
    out = {}
    for pool in am._SUBJECT_POOLS:
        for t in ("none", "satire", "chaotic"):
            for sd in range(SEEDS):
                out[f"{pool}|{t}|{sd}"] = n.roll(
                    subject=pool, treatment=t, count=2, seed=sd,
                    genre="any")[0]
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {len(out)} baseline cases -> {OUT}")


if __name__ == "__main__":
    main()
