# EXPANSION-BRIEF-7 — Demeanor Bank (Depth + Age Keying)

**For:** Claude drafts candidate demeanor entries → Ellie rules on judgment calls → Alexander adjudicates the creative voice → Ellie commits.
**Read first:** `EXPANSION-BRIEF-3.md` (house style + the tag law), `EXPANSION-BRIEF-6.md` (latest delivery rhythm), `scene_context/character_features.json` (the bank you're expanding + its `_compose` group), `CO-AUTHORS.md` (provenance boundary).
**This batch is demeanor entries only** — no code, no wardrobe, no cards, no other feature pools. The banks, not the code.

---

## The directive (top of the page, on purpose)

> **The key is breadth of results — finding the point on the arc between versatility and specificity.**

For demeanor the arc reads like this:

- **Versatile pole:** wallpaper adjectives — "nice," "friendly," "serious." The figure renders no differently with or without them. Useless.
- **Specific pole:** inner psychology or scene-dictating quirks — "still grieving the sister," "twitches at the sound of bells." The camera can't see it, and what it CAN see dictates the scene around it. Collapses breadth.
- **The point on the arc:** a demeanor that changes how the figure **reads at portrait distance**, in any venue the genre's pool can produce, in any role the roll can name. "Flint-eyed" works in a saloon, a wreck line, a colony farm, a guild hall — same words, a different figure each time. **Renderable carriage, not inner state.** The test: could a portrait actor *play* it with face and shoulders alone? If it needs a backstory or a plot beat, it's off the arc.

## Why this batch

Demeanor fires at p=0.7 in the portrait ladder (detail=high) and draws from two paths:

1. **Flat pool** — 24 entries. Every other feature pool sits at 24 too, but demeanor is the one a portrait line *ends on* — it's the last thing the renderer reads, and repetition there is the most visible repetition there is.
2. **Compose path** (chance 0.6) — `temper` slot × `counter` slot joined by **" but "**: "weary but alert," "guarded but patient." The combinatorics look big until you notice the *vocabulary* is 19 + 17 words — long sessions echo the same three dozen words recombining. The ceiling is the slot vocab, not the phrase count.

And the keying is lopsided: `older` has **zero** flat entries and **zero** counter-slot options (temper has two soft weights for it). The identity-weighting machinery (`_weighted`: match 4× / untagged 2× / mismatch 1×) is sitting idle for a third of the age range.

## Current inventory (what exists — do not duplicate)

**Flat pool (24):** weary but alert · watchful · unhurried · tightly wound · easygoing · flint-eyed · quietly amused · settled, unhurried (`middle-aged`) · patient, hard to rattle (`middle-aged`) · restless, always in motion (`young adult`) · bright and curious (`young adult`) · quick to grin (`young adult`) · dour · brusque · guarded · genial · remote, somewhere else entirely · slow to warm · precise in everything · blunt to the point of rudeness · unreadable · quietly furious · mild, unbothered · insolent

**`temper` slot (19):** guarded · weary · brusque · restless · dour · genial · patient · watchful · easygoing · quiet · fierce · stubborn · mild · unreadable · insolent · cheerful · wary · composed · distracted — with existing age soft-weights: weary (older 1.5, middle-aged 1.3), restless (young adult 1.5), patient (middle-aged 1.5, older 1.3), cheerful (young adult 1.2)

**`counter` slot (17):** alert · genial · patient · watchful · easygoing · amused · curious · kind · calm · direct · warm · composed · quick to grin · slow to warm · hard to rattle · ready to laugh · easily distracted — age soft-weights: quick to grin (young adult 1.5), hard to rattle (middle-aged 1.5), ready to laugh (young adult 1.3), easily distracted (young adult 1.2)

## Schema (match existing entries exactly)

Flat:
```json
{"text": "flint-eyed"}
{"text": "settled, unhurried", "age": "middle-aged"}
```
Slot option (same shape, often with dict-form soft weights):
```json
{"text": "weary", "age": {"older": 1.5, "middle-aged": 1.3}}
```

**Legal tags — identity axes only, exactly these:**
- `age`: `"young adult"` | `"middle-aged"` | `"older"` (string match, or the dict form for soft multipliers)
- `sex`: `"female"` | `"male"`
- `race`: dict form only (`{"east_asian": 3}` — see the `eyes` options for the pattern)

**No genre, tone, role, or setting tags.** The features pools are genre-blind by design — the wardrobe carries the era. A genre tag here is dead weight and fails review.

## Tagging — one judgment call, flagged

- **Age keys: wanted, and the headline.** Spread across all three values. `older` is the empty shelf — give it real coverage in both the flat pool and *both* slots (the counter slot has zero today).
- **Sex keys: probably not.** A demeanor honest for one sex usually reads fine on both. If you find an entry where you genuinely disagree, draft it and flag it — don't slip it in.
- **Race keys: no. Ruling, not preference.** The `eyes` pool uses race keys for *anatomy* (monolid) — that's honest morphology. "Watchful by ethnicity" is a stereotype machine. Disposition isn't blood. If you disagree, make the argument in the delivery notes; do not ship race-keyed demeanor entries.

## Authoring law (same spine as BRIEF-3/5/6)

1. **Renderable carriage, not inner state.** The camera can't see "trusts no one"; it can see "unreadable." The actor test from the directive applies to every entry.
2. **Flat entries: 1–5 words, adjectival.** They land at the *end* of the portrait line, after face architecture and build — "…, close-set amber eyes, a birthmark through one eyebrow, wiry, flint-eyed." Comma-internal entries are fine ("settled, unhurried").
3. **Slot words: short.** One or two words — they're building blocks, not phrases. "Quick to grin" is the ceiling.
4. **Temper = baseline register, counter = what complicates it.** The " but " joiner means every pair must read as one coherent person: "dour but quick to grin" is a person; "dour but cheerful" is noise. When drafting a new slot word, hold it against the *other* slot's list and ask if at least half the pairs produce a person.
5. **Era-portable across all 8 genres.** The same pool serves age_of_sail and colony sci-fi. No words that pin an era or a world.
6. **No collisions with neighboring pools.** Postures ("weight sunk into one hip") is body placement — not yours. `build` ("wiry," "rangy") is architecture — not yours. `eyes` owns a few face-words ("piercing") — demeanor may reference the *face* ("flint-eyed" is precedent) but must not duplicate an existing eyes entry.
7. **Distinct registers beat synonyms.** "Tightly wound" and "coiled as a spring" are one image twice. If two entries would render the same portrait, one of them is redundant.

## Scope (the batch)

- **Flat pool: 24 → 60+.** Heavily weighted toward `older` coverage (currently zero) and fresh registers, not synonyms for the existing 24.
- **`temper` slot: 19 → 28+.**
- **`counter` slot: 17 → 28+.** At least 5 of the new counter options keyed or soft-weighted for `older`.
- Counts are floors, not targets — the arc (distinct images, not more entries) outranks the numbers, same as BRIEF-6.

## Acceptance — numbers arbitrate (Ellie runs these)

- JSON valid; no duplicates — exact, near-synonym, or echo of existing entries in any of the three lists.
- Tag law: identity axes only; race-keyed entries rejected on sight; sex-keyed entries require a delivery-note flag.
- `python3 analyze_bank_balance.py --lint` — demeanor is a tracked pool.
- Draw-frequency sanity: portrait rolls (detail=high) across the identity spread; keyed entries must actually surface at their 4× / soft weights.
- **Proof rolls in the delivery notes:** the same seed rolled at all three ages — the demeanor register should shift with the age phrase, not just the age phrase shift. One line of compose-path output ("X but Y") and one flat draw per age is enough.

## Examples to study, in order

1. `scene_context/character_features.json` — the full demeanor block (flat + `_compose.demeanor`), then `build` (nearest register), then `eyes` (the race-key pattern — reference only, see the ruling).
2. `EXPANSION-BRIEF-6.md` — the last accepted delivery: how the arc got applied to wardrobe; same spine applies here.
3. `EXPANSION-BRIEF-3.md` — house style and the original tag law.

**Deliver JSON only — the flat `demeanor` array and the `_compose.demeanor` slots block.** We'll take it from there.
