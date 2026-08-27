# EXPANSION-BRIEF-5 — Subgenre Venue Cards (Content Pass)

**For:** Claude drafts candidate venue JSON → Ellie rules on judgment calls → Alexander adjudicates the creative voice → Ellie commits.
**Read first:** `EXPANSION-BRIEF-3.md` (house style + the tag law), `scene_context/tags.json` (the law, now with subgenres), `scene_context/settings/cantina.json` (the exemplar card), `CO-AUTHORS.md` (provenance boundary).
**This batch is subgenre venue cards — not characters, not code.** New venue JSON only; no `scene_character_roller.py` / node / lint changes.

---

## Why this batch

The venue census is lopsided across the **subgenres** (measured 2026-08-24 against the live node pack):

| subgenre        | venues | state |
|-----------------|--------|-------|
| western         | 0      | **starving — highest priority** (pool yields only the backstop "a western setting") |
| age_of_sail     | 2      | thin (naval_frigate, pirate_ship) |
| post_apocalyptic| 1      | thin (salvage_yard) |

`western` at zero is the clear headline: a whole family of venue cards exists in the reference-style register but no venue carries the tag, so a western scene collapses to a generic fallback phrase. The subgenre content pass fills the real gaps so each subgenre reads as a place, not a placeholder.

## The tag law (read `scene_context/tags.json`)

Tags are **registry ids, not free strings** — same law as BRIEF-3. Now the `genre` namespace carries **subgenres as first-class genres with `parents`**:

```json
"western":         {"parents": ["historical"]},
"age_of_sail":     {"parents": ["historical"]},
"post_apocalyptic":{"parents": ["sci_fi", "modern"]}
```

- **Subgenre = child of its parent(s).** A venue tagged `western` is welcome in the `historical` pool (parent draws own + children). `post_apocalyptic` sits under both `sci_fi` and `modern`.
- **Never invent a genre id.** Only the six in the registry: `historical`, `modern`, `sci_fi`, `fantasy`, `western`, `age_of_sail`, `post_apocalyptic`. (That's seven — base four + three subgenres.)
- **Cross-tag honesty (unchanged):** a venue carries genre G only if genuinely welcome in every pool built from G. A western venue is a *subtype* of historical; exclude it from `modern`/`sci_fi` pools unless it's honestly welcome there.
- **`venue_archetype` closed vocabulary** (from live `tags.json`) — exactly one per card: `interior_social`, `interior_domestic`, `interior_industrial`, `exterior_natural`, `exterior_built`.

## Venue card schema (matches `cantina.json`)

```json
{
  "name": "snake_case_id",
  "subject_label": "plural noun phrase",
  "tags": ["<one or more genre ids; subgenre + its parent(s) as honest>"],
  "facet_tags": ["<from the facet namespace>"],
  "venue_archetype": "<one of the five>",
  "features": {
    "default": ["...", "..."],
    "<genre-group>": ["...", "..."]
  },
  "situations": [
    {"id": "snake_case", "text": "...", "tags": ["<situation namespace>"],
     "scene_type_bias": "<gathering|close_group|candid_moment|face_off|work_line|...>",
     "indoor": true}
  ]
}
```

### `features` — decor groups
- **`default`** always draws once (persistent set dressing: walls, floors, fixtures).
- **Genre-keyed groups** add genre flavor on the resolved genre slot. Key the group to the venue's **own genre** (`"western"`), or a comma-list of genres the venue serves (`"modern,sci_fi"`, `"dieselpunk,steampunk"`). A new western venue should carry a `"western"` group so the western pool reads western.
- Decor is **noun-phrase, sensory, concrete** — "a player piano against one wall", not "music". No period props that contradict an era-neutral situation read (the *venue*, not the situation, carries the genre).

### `situations` — authoring law (unchanged from BRIEF-3)
1. **Actions anchor.** Name what people are *doing*; props belong to the renderer.
2. **Fires name their ground.** Whatever the text claims, the renderer must be able to place.
3. **Era-neutral situation text.** No period markers — era lives in venue authorship, not situation text. "writing a letter", never "dipping a quill" / "typing an email".
4. **Register, not idioms.** Noun phrases, sensory, concrete.
5. **`indoor: true` is opt-in and honest.**
6. **Off = no output.** Absent keys mean absence.

Per venue: **6–8 situations**, each with `id` (snake_case), `text`, `tags`, `scene_type_bias`, optional `indoor`.

### Breadth over depth (the samey-image rule)
The classic failure mode: over-crafting a few evocative scenes until they render beautifully but all look alike. **Breadth beats depth** — cover a wide spread of *distinct* scene types per card (crowd ↔ small group ↔ solo, calm ↔ tense, still ↔ active) and a wide spread of decor elements, rather than eight variations on one vibe. It's a balance, not maximalism — but when in doubt, add a *different* scene, not a deeper one.

---

## Scope (the batch)

Author new venue cards for the three thin subgenres. **Lead with western, then age_of_sail, then post_apocalyptic.**

### 1. `western` — 3+ venues (0 → 3+)
Proposal (swap with justification per house style):
- `frontier_saloon` — wood-and-brass bar, honky-tonk register. `interior_social`. crowd + leisure.
- `railhead_town` — depot street, tracks, baggage, bustle. `exterior_built`. street + city + road.
- `line_shack` — isolated grazing cabin, small-hold. `interior_domestic`. small_crew, indoor. (facet: forest? keep honest — probably not forest; use road / mountain where honest.)
- (stretch) `ranch_porch` — working ranch yard, corrals, feed. `exterior_built`. labor + road.

### 2. `age_of_sail` — +1 to 3 (2 → 3+)
Existing: `naval_frigate`, `pirate_ship`. Promote the genre to a healthier 3:
- `harbor_tavern` already carries `historical`/`fantasy` — **check** whether it should also carry `age_of_sail` honestly (a harbor tavern is age-of-sail-welcome). If yes, re-tag, don't duplicate.
- Stretch candidates: `careening_beach` (hull maintenance, tide), `prize_auction` (captured cargo sale), `harbor_market` (dockside trade). One-tag, don't over-add.

### 3. `post_apocalyptic` — +2 (1 → 3+)
Existing: `salvage_yard`. Add:
- `scavenger_market` — bazaar of salvaged goods, negotiation. `exterior_built`. crowd + leisure + street.
- `overgrowth_road` — abandoned road reclaimed by vegetation, a convoy path. `exterior_natural`. road + forest. (facet: keep honest — road + forest, not both city.)
- (stretch) `refugee_camp` — improvised shelter grid, communal. `exterior_built`. crowd + social.

### 4. Cantina placeholder situations — replace
`cantina.json` currently carries two generic situations (`generic_moment`, `generic_gathering`) with `tags: []`. These are **placeholders**. Replace with 6–8 real, era-neutral Cantina situations (saloon regulars, a game at a corner table, the morning-after crew, a tense exchange at the bar). Keep them genre-honest to `modern` / the subgenre groups the card serves.

---

## Authorship — no ceremony, Claude's our buddy

Nothing legal here. Two small asks:
- **Claude drafts, Alexander gives it voice.** Write the cards however feels natural; Alexander reads them all anyway and will tweak whatever renders oddly. If a card comes out great as-is, that's a win — ship it.
- **Just note which cards you drafted whole-cloth** in the delivery notes, so Alexander knows which deserve the closest read. No author fields, no adjudication ceremony. We're collaborators, not contractors.

## Optional add-ons (only if the batch is clean — do not derail the core)

- **Mature `decor.json`** — top up the decor bank if the new cards expose thin groups.
- **Re-run `--frequency` after new venues land** (build-stable, not content-stable — any venue change reshuffles seed→outcome; prefer raising `--freq-n` over pinning `--freq-seed0`).

## Open question (flagged, not resolved here)

**Wardrobe families.** The lint's `<3 venues` / `<2 wardrobe families` floors apply to **base genres**; subgenres are allowed starved by design. But a healthy subgenre *read* may need wardrobe. Does a subgenre (e.g. `western`) inherit its parent's wardrobe families, or does it need its own? **Decide BEFORE the cards ship** — flag the answer in the delivery notes so the lint doesn't surprise us. Do not author wardrobe in this batch.

## Acceptance — numbers arbitrate

Ellie runs, Claude doesn't need to:
- `python3 analyze_bank_balance.py --lint` — every genre ≥3 venues, every facet ≥2 uses, every situation tag reachable, every genre ≥2 wardrobe families, enum↔registry parity. Exit 1 on fail.
- Venue/situation draw-frequency sanity on the new subgenres (western especially: expect it to move from backstop-only to a real pool).

## Examples to study, in order

1. `scene_context/tags.json` — the law, now with `venue_archetype` + subgenre `parents`.
2. `scene_context/settings/cantina.json` — the exemplar card: `tags` (not `genre_tags`), `venue_archetype`, `features` groups, situation shape.
3. `scene_context/settings/harbor_tavern.json` — indoor mastery, subject_label, tag mix.
4. `EXPANSION-BRIEF-2.md` / `EXPANSION-BRIEF-3.md` — house style: Why / Current State / Target / Candidates with swap-justify.

**Deliver JSON only, no code.** We'll take it from there.
