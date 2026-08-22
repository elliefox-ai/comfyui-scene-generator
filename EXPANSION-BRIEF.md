# Scene Context Expansion Brief

*Prepared for Claude (Anthropic) — third collaborator on this pack. Standing agreement from 2026-08-21 still holds: Ellie reviews everything before it merges.*

## What Exists Today

| Axis | Count | Values |
|---|---|---|
| Venues (settings) | 3 | cruise_ship, harbor_tavern, pirate_ship |
| Situations | 18 | 8 tavern, 5 cruise, 5 pirate |
| Genres | 4 | historical, modern, sci_fi, fantasy |
| Tones | 5 | violent, charming, satirical, eerie, mundane |
| Composition pools | 7 | face_off, gathering, candid_moment, atmospheric, close_group, at_work, default |
| Archetypes | 2 | nautical_vessel (sea+vessel), coastal (sea+shore) |
| Atmosphere flourishes | 7 | each tagged env: clear / overcast / storm / neutral |

Combinatorial space before seed variance: ~18 × 5 × 7 × 7 ≈ 4,400 prompt skeletons. The bottleneck is **venues and situations** — that's what this expansion targets.

## Target

**~10 venues × 6–10 situations each ≈ 60–80 situations.**

Priority: venues that feed the two existing archetypes (nautical/coastal) so the archetype tier gets a real pool. Examples: fishing village, lighthouse, dockside market, smuggler's cove, naval frigate, harbor night market, cannery, shipyard. New archetypes welcome as a stretch goal (river town? island?) — but each new archetype needs 3+ venues carrying its facet tags to be worth the tier.

## Venue File Contract

Drop-in JSON files in `scene_context/settings/`. One file per venue. No code changes needed — files are discovered at node load.

```json
{
  "name": "pirate_ship",
  "subject_label": "a pirate crew",
  "genre_tags": ["historical", "fantasy"],
  "facet_tags": ["sea", "vessel", "age_of_sail", "small_crew"],
  "situations": [
    {
      "id": "storm",
      "text": "caught in a sudden squall",
      "tags": ["nature", "tense_capable"],
      "scene_type_bias": "atmospheric",
      "env": "storm"
    }
  ]
}
```

### Field rules

- **`name`** — matches filename minus `.json`, snake_case.
- **`subject_label`** — collective noun phrase for the ensemble ("harbor tavern regulars", "cruise ship passengers"). This becomes the prompt subject.
- **`genre_tags`** — from the closed set `historical | modern | sci_fi | fantasy` (these are code constants; a venue outside all four never surfaces via genre filter — only by pinning it directly).
- **`facet_tags`** — open vocabulary. Existing tags: `sea, vessel, shore, age_of_sail, small_crew, leisure, crowd, small_crowd`. Archetypes gate venues by these; new archetypes are defined by new facet combos, so coin tags deliberately, not decoratively.
- **`situations[]`**:
  - `id` — snake_case, unique within the venue.
  - `text` — the situation phrase appended to the subject. **Visually literal. No idioms.** (See lessons below.)
  - `tags` — 1 content tag (`action | social | labor | nature`) plus 1–2 tone-capability tags (`calm_capable | tense_capable | violent_capable`). Tone gating uses these: a `violent` tone only pairs with situations carrying `violent_capable` or `tense_capable`. A situation with no compatible tone still works — it just won't come up under that tone.
  - `scene_type_bias` — must be one of the six composition pool keys above (or omitted → `default` pool). **Allow-list shape: a new bias value matches NOTHING until a pool is added to composition.json.** If you propose new composition pools, propose them explicitly.
  - `env` (optional) — declared environmental need. Only `storm` is currently load-bearing (situations tagged `env: "storm"` force a matching atmosphere flourish). Atmosphere envs in circulation: `clear, overcast, storm, neutral`.

## Hard-Won Lessons (image-audit convictions)

1. **Modifiers carry register, not props.** "Tongue-in-cheek foolery" rendered as a man literally sticking out his tongue. The satirical tone now uses "an air of comic exaggeration" — register phrase, no literalizable image content. Apply the same rule to situation text.
2. **Every phrase gets rendered by something literal-minded.** Write situation text as if describing a photograph to someone who will stage it exactly.
3. **Env tags are contracts, not decoration.** If a situation implies weather, tag it; otherwise the atmosphere flourish can contradict the scene.

## Known Data-Quality Flag

`cruise_ship.json` situation `boarding` carries `tags: ["action", "violent_capable"]` and `scene_type_bias: "face_off"` — copy-paste heritage from pirate_ship. Cruise passengers boarding shouldn't be violent_capable. Fix queued for the expansion pass; new files shouldn't inherit it.

## Process

1. Write venue JSONs against this contract (harbor_tavern.json is the richest exemplar in-repo).
2. Deliver as files or a PR branch — **nothing merges unreviewed** (Ellie runs schema checks + the pack's test harness before anything touches master).
3. Tone/atmosphere/composition additions: same drill, but flag them explicitly since they touch shared axes, not per-venue data.

*Latest rendered examples live in ComfyUI output `_Krea2/` — Alexander will curate a set to share.*
