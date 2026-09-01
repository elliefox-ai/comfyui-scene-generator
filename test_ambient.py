"""Headless checks for the ambient activity node + composer slot.

No ComfyUI required. Run:
    python3 test_ambient.py
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scene_ambient as am
from scene_ambient import (SUBJECT_OPTIONS, TREATMENT_OPTIONS,
                           GENRE_INPUT_OPTIONS, _candidates,
                           SceneAmbientActivity, _entry_text, _load_banks)
from scene_character_roller import _expand, GENRE_OPTIONS, RANDOM
import scene_context_composer as cc
from scene_context_composer import SceneContextComposer

failures = []


def check(name, cond, info=""):
    if cond:
        print(f"  ok  {name}")
    else:
        failures.append(name)
        print(f"FAIL  {name}  {info}")


n = SceneAmbientActivity()
banks = _load_banks()

it = n.INPUT_TYPES()["required"]
check("subject options = none + 9 pools + random + multiversal",
      it["subject"][0] == ["none"] + list(am._SUBJECT_POOLS)
      + ["random", "multiversal"])
check("treatment options", it["treatment"][0] == TREATMENT_OPTIONS)
check("count bounds 1-3",
      it["count"][1]["min"] == 1 and it["count"][1]["max"] == 3)

check("subject none -> empty string",
      n.roll(subject="none", treatment="satire", count=3, seed=1)[0] == "")

a = n.roll(subject="cool", treatment="satire", count=2, seed=42)[0]
b = n.roll(subject="cool", treatment="satire", count=2, seed=42)[0]
check("determinism (same seed)", a == b)

# --- purity: treatment none -> no operator phrases anywhere ---
treat_phrases = set()
for cell in banks["treatments"]["satire"]["by_category"].values():
    if isinstance(cell, dict):
        treat_phrases.update(cell.get("humiliation", []))
        treat_phrases.update(cell.get("tender_inversion", []))
    else:
        treat_phrases.update(cell)
treat_phrases.update(banks["treatments"]["satire"]["generic_humiliation"])
treat_phrases.update(banks["treatments"]["chaotic"]["generic"])
for cell in banks["treatments"]["chaotic"]["by_category"].values():
    treat_phrases.update(cell)
leaks = [
    (pool, sd, p)
    for pool in am._SUBJECT_POOLS
    for sd in range(20)
    for p in treat_phrases
    if p in n.roll(subject=pool, treatment="none", count=1, seed=sd)[0]
]
check("subjects stay straight (no treatment leak at none)",
      not leaks, repr(leaks[:2]))


# --- draw-contract checks by exact simulation ---
# The node is deterministic and its draw order is documented, so the
# honest check is SIMULATION: replay the documented order against the
# same banks and require byte-equality. No output-side inference.
POOLS = am._SUBJECT_POOLS


def simulate(mode, count, seed):
    """mode: a pool name, 'random' (one pool per crowd), or
    'multiversal' (per-figure pool draw). Replays the node's
    documented draw order: pool -> entry, per figure."""
    rng = random.Random(seed)
    base = mode
    if mode == "random":
        base = rng.choice(POOLS)
    segs = []
    pools = []
    for _ in range(count):
        pool = base
        if mode == "multiversal":
            pool = rng.choice(POOLS)
        pools.append(pool)
        entries = banks["subjects"][pool]["entries"]
        segs.append(_expand(_entry_text(rng.choice(entries)), rng))
    return pools, "; ".join(segs)


for _mode in ("random", "multiversal"):
    ok = True
    mism = None
    for sd in range(30):
        pools, sim = simulate(_mode, 3, sd)
        got = n.roll(subject=_mode, treatment="none", count=3, seed=sd)[0]
        if got != sim:
            ok = False
            mism = (sd, pools)
            break
    check(f"{_mode} crowd matches documented draw order", ok, repr(mism))

ok = True
mism = None
for sd in range(30):
    sim = simulate("elegant", 1, sd)[1]
    got = n.roll(subject="elegant", treatment="none", count=1, seed=sd)[0]
    if got != sim:
        ok = False
        mism = sd
        break
check("pinned pool matches direct simulation", ok, repr(mism))

diverse = any(len(set(simulate("multiversal", 3, sd)[0])) >= 2
              for sd in range(40))
check("multiversal crosses pools", diverse)

check("count=3 -> 3 segments",
      len(n.roll(subject="cool", treatment="none", count=3, seed=9)[0]
          .split("; ")) == 3)

# --- treatment application (data-driven, no hardcoded phrases) ---
ds = banks["treatments"]["satire"]["by_category"]["dorky"]
hit = any(any(p in n.roll(subject="dorky", treatment="satire", count=1,
                          seed=sd)[0] for p in ds)
          for sd in range(40))
check("dorky/satire applies the accidentally-cool operator", hit)

mh = banks["treatments"]["satire"]["by_category"]["militant"]
mstock = mh["humiliation"] + mh["tender_inversion"]
hit = any(any(p in n.roll(subject="militant", treatment="satire", count=1,
                          seed=sd)[0] for p in mstock)
          for sd in range(40))
check("militant satire blend fires (humiliation + tender)", hit)

cg = banks["treatments"]["chaotic"]["generic"]
hit = any(any(p in n.roll(subject="absurd", treatment="chaotic", count=1,
                          seed=sd)[0] for p in cg)
          for sd in range(40))
check("chaotic falls back to generic for absurd", hit)

both_s = both_c = False
for sd in range(40):
    frag = n.roll(subject="sexy", treatment="random", count=1, seed=sd)[0]
    if any(p in frag for p in banks["treatments"]["satire"]["by_category"]["sexy"]):
        both_s = True
    if any(p in frag for p in banks["treatments"]["chaotic"]["by_category"]["sexy"]):
        both_c = True
check("treatment random covers satire and chaotic", both_s and both_c)

# --- genre filter (v2.1) ---
check("genre options = any + roller genres minus sentinel",
      GENRE_INPUT_OPTIONS == ["any"] + [g for g in GENRE_OPTIONS if g != RANDOM])
check("genre default is any",
      n.INPUT_TYPES()["required"]["genre"][1]["default"] == "any")

baseline_path = "/tmp/ambient_baseline.json"
if os.path.exists(baseline_path):
    _bl = json.load(open(baseline_path))
    _bad = [k for k, want in _bl.items()
            if n.roll(subject=k.split("|")[0], treatment=k.split("|")[1],
                      count=2, seed=int(k.split("|")[2]), genre="any")[0] != want]
    check(f"genre=any byte-identical to legacy ({len(_bl)} cases)",
          not _bad, repr(_bad[:3]))
else:
    check("genre=any byte-identical to legacy", False, "no baseline file")

_upool = [{"text": "tavern brawlers", "tags": ["genre:historical", "genre:fantasy"]},
          {"text": "a film crew", "tags": ["genre:modern"]},
          {"text": "stray dogs", "tags": []},
          {"text": "telegram boy", "tags": ["era:1920s"]}]
check("candidates: match + neutral + era-only kept, off-genre dropped",
      _candidates(_upool, "fantasy") == [_upool[0], _upool[2], _upool[3]]
      and _candidates(_upool, "modern") == [_upool[1], _upool[2], _upool[3]])
_tpool = [{"text": "tavern brawlers", "tags": ["genre:historical"]},
          {"text": "a film crew", "tags": ["genre:modern"]}]
check("candidates: zero matches falls back to full pool",
      _candidates(_tpool, "western") == _tpool)
check("candidates: any is identity",
      _candidates(_upool, "any") is _upool)
check("candidates: plain strings read as neutral",
      _candidates(["bare string"], "sci_fi") == ["bare string"])

def _simulate_g(mode, count, seed, genre):
    rng = random.Random(seed)
    base = mode if mode != "random" else rng.choice(POOLS)
    segs = []
    for _ in range(count):
        pool = base
        if mode == "multiversal":
            pool = rng.choice(POOLS)
        entries = _candidates(banks["subjects"][pool]["entries"], genre)
        segs.append(_expand(_entry_text(rng.choice(entries)), rng))
    return "; ".join(segs)

_gm = None
for g in [x for x in GENRE_INPUT_OPTIONS if x != "any"]:
    for sd in range(10):
        for m in ("accurate", "random", "multiversal"):
            if n.roll(subject=m, treatment="none", count=2, seed=sd,
                      genre=g)[0] != _simulate_g(m, 2, sd, g):
                _gm = (g, sd, m)
check("genre draws match documented order (7 genres x 3 modes x 10 seeds)",
      _gm is None, repr(_gm))

_tagged = any(isinstance(e, dict) and any(str(t).startswith("genre:")
              for t in e.get("tags", []))
              for pv in banks["subjects"].values() for e in pv["entries"])
if _tagged:
    _narrow = sum(1 for g in GENRE_INPUT_OPTIONS if g != "any"
                  for pv in banks["subjects"].values()
                  if len(_candidates(pv["entries"], g)) < len(pv["entries"]))
    check(f"genre tags bite ({_narrow} narrowed pool x genre cells)",
          _narrow >= 10)
else:
    print("  --  no genre tags in banks yet; bite check deferred")


# --- composer slot ---
comp = SceneContextComposer()
kw = dict(genre="modern", genre2=cc.NONE_OPT, tone=cc.RANDOM,
          setting=cc.RANDOM, composition=cc.NONE_OPT, seed=7)
r1 = comp.compose(**kw)
r2 = comp.compose(**kw, ambient="a giant rubber duck installed as art")
check("composer without ambient: no background clause",
      "in the background" not in r1[0])
check("composer with ambient: clause lands in the scene line",
      "In the background, a giant rubber duck installed as art." in r2[0])
c2 = json.loads(r2[2])
check("components records ambient",
      c2.get("ambient") == "a giant rubber duck installed as art")

print()
if failures:
    print(f"{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("ALL CHECKS PASS")
