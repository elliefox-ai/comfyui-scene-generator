# EXPANSION-BRIEF-6 — Native Wardrobe Families (Subgenre Depth)

**For:** Claude drafts candidate wardrobe JSON → Ellie rules on judgment calls → Alexander adjudicates the creative voice → Ellie commits.
**Read first:** `EXPANSION-BRIEF-3.md` (house style + the tag law), `EXPANSION-BRIEF-5.md` (subgenres, parents, breadth law), `scene_context/character_wardrobe.json` (the exemplar families), `CO-AUTHORS.md` (provenance boundary).
**This batch is wardrobe families only** — no cards, no code, no `settings/` changes.

---

## The directive (top of the page, on purpose)

> **The key is breadth of results — finding the point on the arc between versatility and specificity.**

That's Alexander's law for this batch, and it outranks everything below when they disagree. For wardrobe, the arc reads like this:

- **Versatile pole:** clothing so era-neutral it could belong to any genre — useless, the genre vanishes from the figure.
- **Specific pole:** clothing so fully authored it dictates the scene — a gambler's brocade suit that only works in one saloon card, in one pose, in one light. Also useless: it collapses breadth.
- **The point on the arc:** a figure dressed from the family reads *instantly* as the genre, in *any* venue the genre's pool can produce, in *any* role the roll can name. If an outfit only makes sense in one card, it's too specific. If you can't tell the genre from the outfit, it's too versatile.

And within a family: **breadth of distinct silhouettes beats depth on one.** Two different layer combinations should render visibly different figures. "Duster / sheepskin vest / shirtsleeves" is three images. "Duster, dustier duster, duster with more dust" is one image three times.

## Why this batch

The wardrobe parent-ladder is live: a genre resolves to itself ∪ its parents (`genre_with_parents`), so subgenres borrow their parents' families. It works — western no longer falls to era-neutral basics — but borrowing is a bridge, not a destination:

| subgenre         | families drawn (via ladder)            | native voice |
|------------------|----------------------------------------|--------------|
| western          | frontier, age_of_sail (both `historical`)| partial — frontier *is* western workwear, but one register only |
| age_of_sail      | age_of_sail, frontier (both `historical`) | partial — shipboard register only |
| post_apocalyptic | flightline, colony, workwear, streetwear | **none** — borrowed clothes read "spaceport" and "day off", not "collapse" |

Post-apocalyptic is the headline: four borrowed families, zero native texture. Western and age_of_sail each have one honest register covered and are missing the other half of their world (town/shore vs. work).

## Current inventory (what exists — do not duplicate)

`character_wardrobe.json` → `families`, 9 total: 2 per base genre + `_neutral`:
- `historical`: **frontier** (ranch/west workwear — duster, duck trousers, riding boots), **age_of_sail** (shipboard — oilskin, pea coat, slops, tricorne)
- `modern`: workwear, streetwear · `sci_fi`: flightline, colony · `fantasy`: wanderer, guild
- `_neutral`: era-neutral basics (the fallback of last resort)

## Family schema (match `frontier` exactly)

```json
"family_name": {
  "genre": "<one registry genre id — a subgenre id is legal>",
  "layers": {
    "outer":  ["2-3 options"],
    "torso":  ["2-3 options"],
    "legs":   ["2-3 options"],
    "feet":   ["2-3 options"],
    "head":   ["2-3 options"]
  },
  "palettes": ["2-3 paired color phrases"],
  "wear": ["3+ wear states"],
  "concepts": [
    {"text": "a <archetype>", "roles": ["<role ids>"]}
  ]
}
```

Authoring law, same spine as BRIEF-3/5:
1. **Noun phrases, sensory, concrete.** "a duster coat gone stiff with rain-salt", not "weatherproof outerwear".
2. **Era lives in the wardrobe.** Unlike situations (era-neutral by law), wardrobe is *where the genre gets dressed*. Period-true materials and cuts — but rendered as texture and wear, not costume-shop labels.
3. **Layer options must mix.** Any outer × torso × legs × feet × head combo should be plausible for the family's world. If `head` option A only pairs with `torso` option B, one of them is too specific.
4. **Palettes are pairs** ("dust brown and faded indigo") — two colors that coexist in one image.
5. **Wear states attach anywhere** — write them so any garment can carry them.
6. **6–8 concepts, spread across roles.** Use the seven established roles (`warrior, official, leader, worker, drifter, healer, scholar`-set as seen in existing families — read the file for the live ids). Social spread > one archetype deep: a western town family needs the banker AND the beggar-kid, not three lawmen.
7. **Off = no output.** Absent layers simply don't draw — a family may skip `head` entirely if honest.

## Scope (the batch)

Lead with post_apocalyptic, then western, then age_of_sail.

### 1. `post_apocalyptic` — +2 native (the headline)
- `scavenger` — repurposed everything: mismatched layers, salvage-grade outerwear, self-mended. Roles across the board — a salvage runner, a fence-trader, a filter-tech who's basically a healer.
- `enclave` — improvised order: quasi-uniforms from scrounged cloth, armbands, patched faction colors. Official/leader/warrior heavy.
- (stretch) `roadhouse` — whoever the road still feeds: cook, mechanic-wright, watch-sitter. A third silhouette if the two above land clean.

### 2. `western` — +1 native (the missing register)
- `frontier_town` — the dressed-up half of the west: town clothes, Sunday best, shopkeeper's apron, gambler's vest. Existing `frontier` covers work; this covers town. Distinct silhouettes from `frontier` — do not echo duster/riding boots.

### 3. `age_of_sail` — +1 native (the shore register)
- `portside` — shore clothes: shore leave flash, slop-shop cheap, chandler respectable. Shipboard exists; this is the world the ship docks into.

**Swap freely with justification** — candidates are proposals, not orders. The counts are floors, not targets; add a family if the genre's read genuinely needs it (see the directive: it needs *distinct images*, not more entries).

## Tagging — one judgment call, flagged

Families carry **one** `genre` id. The ladder runs upward only (child ∪ parents), so:
- A family tagged `post_apocalyptic` draws **only** for post-apoc picks — the specificity holds, and modern/sci_fi draws stay clean. This is what we want for native voice: **tag native families with their subgenre id.**
- The existing `age_of_sail`-named family stays `historical` (it currently feeds historical draws; re-tagging would remove it there). Flag in delivery notes if you think that's wrong — don't re-tag in this batch.

## Authorship — no ceremony, Claude's our buddy

Same as BRIEF-5: draft naturally, Alexander gives it voice and will tweak whatever renders oddly. **Note which families you drafted whole-cloth** in the delivery notes. No author fields.

## Acceptance — numbers arbitrate (Ellie runs these)

- `python3 analyze_bank_balance.py --lint` — every genre ≥2 wardrobe families (subgenres now counted through the ladder), enum↔registry parity, role ids valid.
- Draw-frequency sanity on the three subgenres: native families must actually surface (post-apoc especially — expect the read to shift from "spaceport day off" to collapse texture).
- A proof roll per subgenre in the delivery notes, the way the cantina proof worked.

## Examples to study, in order

1. `scene_context/character_wardrobe.json` — `frontier` (the exemplar: layers/palettes/wear/concepts), then the other families for register spread.
2. `EXPANSION-BRIEF-5.md` — subgenre law, parents, the breadth-over-depth section this batch inherits.
3. `scene_context/tags.json` — the genre registry, now with subgenre ids.
4. `scene_context/settings/cantina.json` + the western cards (`frontier_saloon`, `railhead_town`) — the venues your families will dress. **A family that can't stand in any of its genre's venues is too specific** (the arc, again).

**Deliver JSON only — the families block.** We'll take it from there.
