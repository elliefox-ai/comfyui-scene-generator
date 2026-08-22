# Scene Context Expansion Brief — Batch 2

*Prepared for Claude (Anthropic). Standing agreement from 2026-08-21 holds: Ellie reviews everything before it merges. Batch 1 (2026-08-22) merged clean — see CO-AUTHORS.md for the postmortem.*

## Why Batch 2 Exists

Batch 1 succeeded on its own terms: 3 → 8 venues, 18 → 59 situations, every genre × archetype × tone join ≥2. But the brief that scoped it prioritized "feed the two existing archetypes" — and both of those are maritime by birth. Result: **all 8 venues carry the `sea` facet tag.** The genre axes still do their job (sci-fi smugglers reads nothing like historical frigate), but environmentally it's boats and brine all the way down. Alexander noticed: *"we have an unusual preponderance of nautical premises."*

Batch 2's goal is **breadth: new environment archetypes, zero boats.**

## Current State (post-batch-1)

| Axis | Count | Values |
|---|---|---|
| Venues (settings) | 8 | cruise_ship, dockside_market, fishing_village, harbor_tavern, lighthouse, naval_frigate, pirate_ship, smugglers_cove |
| Situations | 59 | 8 tavern, 7 cruise, 8 × 5 new venues |
| Genres | 4 | historical, modern, sci_fi, fantasy |
| Tones | 5 | violent, charming, satirical, eerie, mundane |
| Composition pools | 7 | face_off, gathering, candid_moment, atmospheric, close_group, at_work, default |
| Archetypes | 2 | nautical_vessel (sea+vessel), coastal (sea+shore) |
| Atmosphere flourishes | 8 | each tagged env: clear / overcast / storm / neutral |

## Target

**3 new environment archetypes × 3 venues each = 9 venues, 6–8 situations apiece.** Each new archetype gets exactly one entry in `archetypes.json` with a clean facet combo. Archetypes from batch 1 remain untouched.

## Candidate Archetypes (proposed — Claude may swap, but justify)

Chosen for the pack's use case — character illustration with ensemble casts, not landscapes. Each must hold an ensemble of 2–8 people doing something stageable.

1. **Mountain** — facet combo `["mountain", "road"]`
   Venues: mountain waystation/inn, high pass (travelers/escorts), goat-herders' summer settlement
2. **Forest** — facet combo `["forest", "road"]`
   Venues: forest road (pilgrims/bandits), charcoal-burners' camp, hunting lodge
3. **Urban** — facet combo `["city", "street"]`
   Venues: market street, theater row (stage-door crowd), print-shop/scriptorium alley

Alternates if one of the three doesn't sing: river ferry crossing (freshwater, not sea), oasis/caravan stop (desert), rail platform (period-split: steam/modern/sci-fi terminal), monastery cloister, cathedral interior.

**Constraints on archetype choice:**
- Each needs a prompt-safe `label` ("on a mountain road", "in the forest", "on a city street") — the preposition-led phrasing matters; existing labels are "on a nautical vessel", "on the coast".
- Venue facets must reference the new archetype's combo AND add their own specifics (e.g. `["mountain", "road", "waystation", "small_crowd"]`).
- **Genre coverage:** each archetype should have at least one modern or sci_fi venue so the genre filter has something to bite on beyond historical/fantasy. The maritime pool is history-heavy; batch 2 shouldn't inherit that skew.

## Venue File Contract

Unchanged from batch 1 — full text in EXPANSION-BRIEF.md (the original still stands; this document supersedes it only in scope). Same rules:

- Drop-in JSONs in `scene_context/settings/`, one per venue, discovered at node load. No code changes.
- `name` matches filename, snake_case; `subject_label` is the ensemble noun phrase that becomes the prompt subject.
- `genre_tags` from the closed set `historical | modern | sci_fi | fantasy`.
- `facet_tags`: open vocabulary, but coin tags deliberately — they define archetypes.
- Situations: `id` snake_case unique; `text` **visually literal, no idioms** — describe a photograph, not a figure of speech; `tags` = 1 content tag (`action | social | labor | nature`) + 1–2 tone-capability tags; `scene_type_bias` from the 7 composition keys; optional `env` tag when weather is load-bearing.
- Tone/atmosphere/composition additions = shared axes → flag separately, Alexander's call.

## New for Batch 2

**Terrain atmosphere check.** The atmosphere pool has clear/overcast/storm/neutral envs and 8 flourishes — maritime-neutral phrasing throughout ("under a clear blue sky" is fine anywhere; most others reference sea/sky/coast). When you write mountain/forest/urban venues, flag any situation whose natural weather contradicts the current flourish pool, and propose **at most 2–3 new flourishes** (flagged separately as shared-axis changes) only where genuinely needed. Do not restock the pool wholesale.

**Interior/enclosed spaces.** Several candidate venues are interiors (inn, lodge, scriptorium). The atmosphere flourish system was built for outdoor scenes. For indoor situations, either omit `env` and keep the flourish generic, or propose how enclosed spaces should read — but don't let "outdoor weather" flourishes attach to candlelit interiors.

## Hard-Won Lessons (still binding)

1. **Modifiers carry register, not props.** "Tongue-in-cheek foolery" rendered literally. Register phrases, not literalizable idiom content.
2. **Every phrase gets rendered by something literal-minded.** Write situation text as if staging a photograph.
3. **Env tags are contracts, not decoration.** Tag weather only when the situation needs it.

Plus batch-1's postmortem line: the batch was clean; the only bug in the whole deploy was Ellie writing a prompt to a vestigial workflow field. The bar remains: schema + harness + coverage audit green, and register checks on every situation text.

## Process

1. Write 9 venue JSONs + one `archetypes.json` addition (3 new entries) + any flagged flourish proposals.
2. Update `coverage_audit.py` expectations for the new joins.
3. Deliver as files or PR branch — nothing merges unreviewed. Ellie runs schema checks, the test harness, and the coverage audit against the staged merge before anything touches master.
4. Alexander gets the call on atmosphere/shared-axis items, as always.

*Live rendered examples: ComfyUI output `_Krea2/` — the lighthouse smoke render (lamp-room tending, oglafstyle linework) is the batch-1 exemplar.*
