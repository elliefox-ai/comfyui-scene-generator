"""Headless checks for the wardrobe heat bank + roller integration.

No ComfyUI required. Run:
    python3 test_wardrobe_heat.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scene_wardrobe_heat as wh
from scene_wardrobe_heat import (HEAT_OPTIONS, archetype_for, heat_pool,
                                 posture_pool, validate_heat_bank)
from scene_character_roller import RANDOM, SceneCharacterRoller

failures = []


def check(name, cond, info=""):
    if cond:
        print(f"  ok  {name}")
    else:
        failures.append(name)
        print(f"FAIL  {name}  {info}")


print("== bank hygiene ==")
problems, cov = validate_heat_bank()
check("bank validates clean", not problems, problems[:5])
check("coverage >= 95%", cov["tagged"] / max(cov["total"], 1) >= 0.95, cov)
print(f"  tagged {cov['tagged']}/{cov['total']}; never-tagged archetypes: "
      f"{cov['untagged_archetypes']}")

print("== lookups ==")
for item, want in [
        ("carpenter jeans", "trousers"),
        ("a satin camisole", "top"),
        ("a patched flight suit", "coverall"),
        ("a station coverall, badge-taped", "coverall"),
        ("{a pencil|a pleated midi} skirt", "skirt"),
        ("a bartender's apron cut from old tarp", "apron"),
        ("a kilted wrap with tool loops", "skirt")]:
    check(f"tag {item[:30]!r}", archetype_for(item) == want,
          f"got {archetype_for(item)!r}")
    for lvl in ("suggestive", "flirty", "smoldering"):
        if not heat_pool(item, lvl):
            check(f"pool {item[:24]!r}@{lvl}", False, "empty pool")
check("variant-grammar items have pools",
      all(heat_pool("a {flannel|thermal} {|with a hi-vis vest over}", l)
          for l in ("suggestive", "flirty", "smoldering")))
check("off/unknown level silent",
      heat_pool("carpenter jeans", "off") == []
      and heat_pool("carpenter jeans", "bogus") == []
      and posture_pool("nope") == [])
check("headwear unheated", heat_pool("a hard hat", "smoldering") == [])
check("footwear unheated", heat_pool("steel-toed boots", "smoldering") == [])
check("posture pools nonempty",
      all(posture_pool(l) for l in ("suggestive", "flirty", "smoldering")))

print("== roller integration ==")
r = SceneCharacterRoller()
bank = wh.load_heat_bank()
ALL_PHRASES = {p for spec in bank["archetypes"].values()
               for pool in spec.get("heat", {}).values() for p in pool}
KW = dict(genre="modern", consistency=0.8, face_detail="low",
          body_detail="high", body_type="random", role="any", name="",
          pose=True, positioning=False, age=RANDOM, sex=RANDOM,
          race=RANDOM)

off_texts, off_comps = [], []
for seed in range(24):
    t, c, _ = r.roll(**KW, seed=seed, heat="off")
    off_texts.append(t)
    off_comps.append(c)
check("off register: zero heat phrases",
      not any(p in t for t in off_texts for p in ALL_PHRASES))
check("off register: heat block level=off",
      all(json.loads(c)["heat"]["level"] == "off" for c in off_comps))
check("off register: nothing applied",
      all(json.loads(c)["heat"]["applied"] == {} for c in off_comps))

t1, c1, _ = r.roll(**KW, seed=123, heat="off")
t2, c2, _ = r.roll(**KW, seed=123)  # default param path
check("default heat == explicit off", t1 == t2 and c1 == c2)

POOL3 = set(posture_pool("smoldering"))
hits = 0
posture_ok = True
for seed in range(30):
    t, c, _ = r.roll(**KW, seed=seed, heat="smoldering")
    comp = json.loads(c)
    applied = comp["heat"]["applied"]
    if applied:
        hits += 1
    for note in applied.values():
        if note["phrase"] not in t:
            check(f"phrase in text (seed {seed})", False, note)
    if comp["pose"] and comp["pose"] not in POOL3:
        posture_ok = False
check("smoldering applies in most rolls", hits >= 25, f"hits={hits}/30")
check("pose + heat -> heat posture register", posture_ok)

ta, _, _ = r.roll(**KW, seed=11, heat="flirty")
tb, _, _ = r.roll(**KW, seed=11, heat="flirty")
check("heat deterministic (same seed)", ta == tb)

# --- v1.1: hem-gated legwear + occupation costumes ---
lw = {"off": 0, "suggestive": 0, "flirty": 0}
for level in lw:
    for seed in range(120):
        _t, _c, _ = r.roll(**KW, seed=seed + 500, heat=level)
        if '"legwear"' in _c:
            lw[level] += 1
check("legwear never at off", lw["off"] == 0)
check("legwear fires over an exposed hem at flirty", lw["flirty"] > 0)
# --- v2: persona uniform looks (nurse via healer@documentary) ---
_fired = None
for _sd in range(30):
    _t, _cj, _ = r.roll(**dict(KW, role="healer"), seed=_sd,
                        heat="off", authenticity="documentary")
    _u = ((json.loads(_cj).get("authenticity") or {}).get("uniform")) or {}
    if _u.get("fired"):
        _fired = (_t, _u)
        break
check("uniform look: nurse renders via healer@documentary",
      _fired is not None and "nurse" in _fired[0], repr(_fired and _fired[1]))
check("uniform look: documentary reads flat (no stethoscope)",
      _fired is not None and "stethoscope" not in _fired[0])
_roles_expected = ["any"] + sorted(json.load(open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "scene_context",
    "personas.json")))["personas"])
check("role list is the closed persona set (no sommelier)",
      r.INPUT_TYPES()["required"]["role"][0] == _roles_expected)
check("authenticity deterministic (same seed)",
      r.roll(**KW, seed=5, heat="off", authenticity="documentary")[0]
      == r.roll(**KW, seed=5, heat="off", authenticity="documentary")[0])
_diff = sum(
    r.roll(**dict(KW, seed=_sd), heat="off", authenticity="stylized")[0]
    != r.roll(**dict(KW, seed=_sd), heat="off", authenticity="documentary")[0]
    for _sd in range(40))
check("authenticity registers diverge across seeds", _diff > 0,
      f"diff={_diff}/40")
check("same seed, same string at flirty",
      r.roll(**KW, seed=9, heat="flirty")[0]
      == r.roll(**KW, seed=9, heat="flirty")[0])

print()
if failures:
    print(f"{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("ALL CHECKS PASS")
