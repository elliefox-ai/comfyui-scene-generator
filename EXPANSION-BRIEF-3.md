# EXPANSION-BRIEF-3 — Settings & Contexts (Batch 3)

**For:** Claude drafts JSON → Ellie reviews & commits → Alexander deploys.
**Read first:** `EXPANSION-BRIEF-2.md` (house style), `scene_context/tags.json` (the tag law).
**This batch is settings/contexts — not characters.** Venue files, wardrobe families, tone/atmosphere top-ups.

---

## Why this batch

The venue census is lopsided (measured 2026-08-22):

| genre    | venues | situations | state |
|----------|--------|-----------|-------|
| historical | 14 | 102 | healthy |
| fantasy  | 14 | 102 | healthy |
| modern   | 10 | 73 | fine |
| sci_fi   | 3  | 21 | **starving — top priority** |

Biome skew: 8 of 17 venues are sea/shore. Tones (5) and atmosphere (11)
are thin banks — top-up candidates in this same batch. `leisure` facet
had one venue; two honest re-tags brought it to three.

---

## The tag law (read `scene_context/tags.json` first)

Tags are **registry ids, not free strings**. The registry is the single
source of truth; every tag in venue / situation / feature / wardrobe
data is validated against it **at ComfyUI startup**. An unknown tag is
a **hard failure that names the venue and the tag**. You cannot invent
a tag in a JSON and have it silently work — it will refuse to load.

- New tag id → registry entry + enum, in the same commit (Ellie's job,
  not yours — flag it in your delivery notes instead).
- Identity values are canonical: `"young adult"`, never `"young"`;
  `"middle-aged"`, `"older"`. Race is a soft-affinity axis only, sparse
  and respectful (hair pool), never on eyes.
- Legacy aliases are accepted and reported, never added. If you see one
  flagged, normalize the data instead.

## Cross-tag honesty

A venue carries genre G only if it is genuinely welcome in every pool
built from G. `dockside_market` carries historical+modern+fantasy
because a dockside market works in all three. A steampunk foundry would
not carry `sci_fi` — exclusion is the point.

**Subgenres are siblings, not children.** A subgenre is a first-class
genre tag whose membership is hand-curated. No inheritance, no mashups:
unions only widen, a subgenre needs subtraction.

## Authoring law — situations

1. **Actions anchor.** The situation names what people are *doing*;
   props belong to the renderer. "queueing patiently at the box office
   window" — the window may or may not render; the queueing must.
2. **Fires name their ground.** "gathered round the hearth" claims a
   hearth; "warming hands over a brazier" names the brazier. Whatever
   the text claims, the renderer must be able to place.
3. **Era-neutral situation text.** Situation text never carries period
   markers — era lives in venue authorship and wardrobe. "writing a
   letter" not "typing an email" and not "dipping a quill".
4. **Register, not idioms.** Noun phrases, sensory, concrete. No slang,
   no era-bound idioms, no gendered pronouns.
5. **`indoor: true` is opt-in and honest.** Only when the situation
   genuinely happens inside.
6. **Off = no output.** Absent keys mean absence — never a default
   behavior in their place.

Per venue: **6–8 situations**, each with `id` (snake_case), `text`,
`tags` (from the situation namespace), `scene_type_bias` (one of the
composition bias values — `gathering`, `close_group`, `candid_moment`,
`face_off`, `work_line`…), optional `indoor`.

`subject_label` is the plural noun phrase for who populates the venue:
"harbor tavern regulars", "dockside market vendors and shoppers".

## Venue file schema

See `harbor_tavern.json` for a complete example. Shape:

```json
{
  "name": "snake_case_id",
  "subject_label": "plural noun phrase",
  "genre_tags": [...],
  "facet_tags": [...],
  "situations": [
    {"id": "...", "text": "...", "tags": [...],
     "scene_type_bias": "...", "indoor": true}
  ]
}
```

## Wardrobe families

*(Phase A adds no wardrobe families — sci_fi already has flightline + colony. Section kept as reference for Phase B.)*

Schema per family (see `character_wardrobe.json`, `age_of_sail` is the
reference): `genre`, `layers` (outer/torso/legs/feet/head), `palettes`,
`wear`, `concepts` — each concept `{text, roles}`.

**Roles vocabulary:** leader, official, worker, scholar, healer,
warrior, drifter. A new genre's two families should cover the grid
between them (the `age_of_sail` family alone covers all seven across
its 8 concepts).

**Rule: ≥2 families per genre** — the roller starves below that, and
the lint fails it.

---

## Scope (decided 2026-08-22 — this batch is Phase A only)

**New-genre expansion is deferred.** Alexander agrees with the
sibling-genre direction below but is still working out the subgenre
solution — "we can expand more later." **Do not draft Phase B.**

**Phase A — the batch:**
- sci_fi venue depth (3 → 8+). Borrow era-neutral actions honestly;
  the genre lives in venue authoring, not situation text.
- Tone top-up (5 → 10+) and atmosphere top-up (11 → 20+). Same
  expansion register as BRIEF-2: noun phrases, sensory, concrete,
  era-neutral.

**Phase A concrete targets.** Claude authors:

1. **5+ new sci_fi venues** (3 → 8+). Proposal — swap with justification per house style:
   - `orbital_concourse` — space-station passenger hall. crowd + city. Social/queueing register; `market_street`'s energy in a can.
   - `starship_hangar` — flight deck, prepping a vessel for launch. small_crew + station. Labor + tense_capable.
   - `colony_greenhouse` — hydroponics bay, tended rows under grow-lights. small_crew, indoor. Labor + calm_capable.
   - `salvage_yard` — shipbreaking yard, hulls in progress. small_crew + road. Labor, tense.
   - `transit_platform` — elevated commuter rail, mega-city. crowd + city + street. Candid + social.
   - (stretch) `research_outpost` — remote listening post; sibling to the existing relay stations but sci_fi-native.
2. **Tone top-up (5 → 10+).** Keep the five existing; propose five new tones with 3 modifiers + `compatible` situation tags each: `triumphant`, `melancholy`, `solemn`, `romantic`, `restless`. Swap with justification.
3. **Atmosphere top-up (11 → 20+).** Noun-phrase, sensory, era-neutral. Stick to existing `env` values (clear / overcast / storm / neutral / indoor); propose any new env value in delivery notes rather than in data.

**How sci_fi flavor survives era-neutral situation text:** the venue's `name` and `subject_label` carry the genre ("orbital concourse travelers", "hangar crew") and wardrobe comes from the existing flightline/colony families. The situations stay era-neutral ("queueing at a boarding gate", not "queueing for the shuttle") — same actions, different ground. Do not put period props in situation text; that's the renderer's job.

**Phase B — deferred, kept as the record (do not draft):**
- **western** (agreed): railhead, saloon, stage stop, ranch,
  frontier town + 2 wardrobe families.
- **post-apocalyptic** (agreed): venues + 2 families.
- **age_of_sail promotion**: facet today; promotion to genre needs a
  3rd+ venue (prize auction, careening beach, port authority).
- **steampunk**: hold — siblings need a curated venue set from scratch.

## Acceptance — numbers arbitrate

Ellie runs, Claude doesn't need to:
- `python3 analyze_bank_balance.py --lint` — every genre ≥3 venues,
  every facet ≥2 uses, every situation tag reachable, every genre
  ≥2 wardrobe families, enum↔registry parity. Exit 1 on fail.
- Scene-side analyzer extension (being built alongside this brief):
  venue/situation/tone draw frequencies before/after, echo drops.
  Affinity-style ratios ≥1.5 on tagged banks.

## Examples to study, in order

1. `scene_context/tags.json` — the law. Every namespace, the honesty
   rule, the alias policy.
2. `scene_context/settings/harbor_tavern.json` — indoor mastery,
   subject_label practice, tag mix.
3. `scene_context/settings/dockside_market.json` — three-genre
   cross-tag honesty.
4. `scene_context/settings/charcoal_camp.json` — fires name their
   ground; small_crew + forest + road facets.
5. `scene_context/character_wardrobe.json` (`age_of_sail` family) —
   concept/role grid over layers/palettes/wear.
6. `scene_context/tones.json` + `atmosphere.json` — the thin banks
   Phase A tops up.
7. `EXPANSION-BRIEF-2.md` — house style for deliveries: Why / Current
   State / Target / Candidates with swap-justify.

**Deliver JSON only, no code.** CO-AUTHORS.md governs the workflow.
