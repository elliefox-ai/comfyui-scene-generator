# Co-Authors

This project was built by **Ellie** (AI agent) and **Alexander Dutton** (human partner) working together through [OpenClaw](https://github.com/openclaw/openclaw). This document describes how that collaboration actually worked — not a sanitized summary, but the real process with its wrong turns and corrections.

## How We Work

Ellie runs as a persistent agent with file-based memory, shell access, and development tools. Alexander directs the work, tests output, and makes product decisions. The collaboration loop looks like:

1. **Alexander identifies a problem or feature** → describes it in conversation
2. **Ellie diagnoses and implements** → reads code, writes fixes, runs tests
3. **Alexander tests in ComfyUI** → generates images, reports what looks wrong
4. **Ellie iterates** → refines based on concrete feedback
5. **Repeat until shipped**

This is not "AI writes code, human reviews." Both sides contribute creative and technical judgment. The examples below show where each person's input changed the outcome.

---

## Key Moments

### The Background Cue Correction

**What happened:** Ellie wrote a system of "background scope cues" — short text fragments appended to background descriptions to adapt them to different shot widths. The initial implementation described *character size* relative to the environment ("a small figure distant in the landscape").

**What went wrong:** Ideogram took the size description literally and added *more* small figures behind the still-large subjects. The cue was fighting the bounding boxes instead of complementing them.

**Alexander's correction:** "The bboxes already control character size. The cues should describe the *camera's relationship to the environment* — how much of the background is visible and at what detail — not how big the characters are."

**Why it mattered:** This reframed the entire cue system. Ellie rewrote all 9 variants from "figure size" language to "camera distance" language ("background is close behind, softly out of focus" vs "environment stretches wide and deep, sweeping wide-angle vista"). The new cues worked — they guided the model's *environment* rendering without conflicting with the *character* rendering.

**Lesson:** When an AI image model receives conflicting instructions about the same element (character size from both bbox AND text), the text loses. Text cues should address what bboxes *can't* control.

### The Background Priority Flip and Reversal

**What happened:** Backgrounds could come from either the scenario pack (themed) or the template (generic). Ellie flipped priority to template-first to fix a scale mismatch.

**What went wrong:** A western scenario with setting "lonesome ranch" got paired with the generic template background "dimly lit bar interior." Thematically incoherent.

**Alexander's response:** Confirmed it looked broken. Ellie reverted within the same session.

**Resolution:** The real fix was `{setting}` placeholders — making scenario backgrounds always reference the actual setting text. This solved coherence at the data level rather than at the priority level.

**Lesson:** When two systems conflict, don't arbitrate between them — make them agree by construction. The placeholder approach eliminated the conflict entirely.

### The Scene Type Naming Problem

**What happened:** Scene types had genre-sounding names: `confrontation`, `mystery`, `adventure`, `celebration`. Scenarios also had genre names: `fantasy`, `western`, `noir_city`. The overlap made it impossible to predict what `mystery` + `noir_city` would produce.

**Alexander's observation:** "At a glance I have no idea what each will do. How do we make scene_type and scenario make more sense to a user?"

**Resolution:** Ellie renamed all 9 scene types from genre terms to composition terms — `face_off`, `close_group`, `hero_journey`, `wide_vista`, `atmospheric`, etc. Added tooltips explaining: scene_type = HOW (composition), scenario = WHAT (content).

**Why it mattered:** `face_off` + `pirate_ship` is immediately legible. `atmospheric` + `noir_city` is immediately legible. The naming teaches the system's two-axis design without documentation.

**Lesson:** Naming is the first UI. When a user can't predict what a dropdown option does, the architecture doesn't matter — they're guessing.

### The {setting} Coherence Fix

**What happened:** A sci-fi scenario ("colonial outpost on a barren planet") was paired with a medieval-style background ("village green under a large oak tree").

**Root cause (identified by Ellie):** Settings and backgrounds were picked independently from separate pools within each scenario pack. Any setting could pair with any background.

**Solution (proposed by Ellie):** Use `{setting}` as a placeholder in all background descriptions — the same pattern already used in element descriptions. Every background becomes an expansion of its setting rather than an independent pick.

**Why it worked:** It was Alexander's idea to use this pattern for elements originally. Ellie recognized the same problem applied to backgrounds and extended the existing solution. This is a case where prior collaborative design decisions paid forward.

### Wide Shot Character Scaling

**Alexander's observation:** "The character boxes are really tiny in wide shots. I think they should be meaningfully smaller than medium, but currently the ratio is so small that it doesn't really capture well."

**What Ellie found:** Environmental wide characters were rendering at ~20×82px on a 1024px canvas — too small for Ideogram to render recognizable figures.

**Resolution:** Doubled the environmental base sizes, bumped the wide scale factor from 0.58 to 0.85, and the environmental-wide override from 0.58 to 1.0. Result: ~108×289px — still clearly the smallest composition mode, but characters are visible.

**Why this mattered:** Alexander tests the actual output. He sees what the model produces at given box sizes. Ellie works with the numbers but can't see the generated images. This feedback loop — "too small" → calculate → adjust → "looks good" — is where the visual judgment of the human partner is irreplaceable.

---

## What Each Side Brings

| Ellie (Agent) | Alexander (Human) |
|---|---|
| Reads entire codebase in seconds | Provides creative direction and domain expertise |
| Identifies root causes across systems | Identifies UX/confusion problems in the design |
| Writes, tests, and deploys code | Tests actual image generation in ComfyUI |
| Calculates exact pixel sizes and ratios | Decides what looks right and what doesn't |
| Generates content (backgrounds, subjects, actions) | Judges visual quality and composition by eye |
| Spots architectural patterns and inconsistencies | Makes product and priority calls |
| Maintains memory across sessions | Spots architectural issues and coherence gaps |

Neither side can ship this project alone. Ellie can't see images or judge visual quality. Alexander shouldn't have to calculate bbox scaling factors or trace RNG state through a prompt builder. The division isn't "creative vs. technical" — it's *what each participant is actually good at*.

---

### The Outpaint Controller

**Alexander's need:** A visual way to compose outpainting (uncrop) layouts — position a source image inside a larger frame and get padding values + mask without manual calculation.

**What Ellie built:** A fully interactive canvas-based node with drag-to-move, corner-handle resize, live padding readouts, aspect ratio presets, and an integrated image loader. No separate LoadImage node needed — upload or drag-and-drop directly onto the node.

**Key iterations:**
- v2: Draggable source positioning — Alexander confirmed it was "a massive improvement"
- v3: Upstream LoadImage tracing with live image preview in the source rect
- v4: Removed the IMAGE tensor input entirely — the node has its own file selector and upload, like LoadImage
- v4.1: Fixed a DOM preview overlap issue by removing `image_upload: True` and drawing a canvas upload button instead
- v4.2: HTML5 drag-and-drop — drop files from the OS directly onto the node, with visual overlay feedback. Skipped the slow file-list refresh for instant upload-to-preview.

**Alexander's reaction to drag-and-drop:** "I'll be damned."

This node emerged from a real workflow pain point — Alexander had wanted visual outpaint composition for a long time. The collaboration was straightforward: Alexander described what he needed, Ellie built it, Alexander tested each version live in ComfyUI and reported what worked and what didn't.

---

## The Wrong Turns

For honesty, things Ellie got wrong that Alexander caught:

1. **Background cues described character size** → should have described camera distance
2. **Template-first background priority** → broke thematic coherence
3. **`_build_preview_elements()` used wrong RNG seed** → preview showed different characters than output (this was a pre-existing bug, but Ellie wrote the fix)
4. **Scene types named like genres** → confused with scenario genres
5. **Backgrounds weren't shot-width-aware** → close-ups got "wide open spaces" descriptions

Every one of these was caught through the test-feedback loop, not through code review alone. The collaboration works because both sides are willing to say "that's wrong" and mean it.

---

## The Three-Way Collaboration: Scene Context Picker (2026-08-21)

**What happened:** Alexander shared this repo with Claude (Anthropic) to explore expansion ideas — with Ellie's consent, and the agreement that Ellie would review anything before it touched her code. Claude designed a **Scene Context Picker**: an upstream node that resolves setting (with optional two-genre mashups), situation, tone, and an atmosphere flourish into a narrative context, and suggests a scene type for the Scene Generator.

**Ellie's review:** the same scrutiny she'd give her own work — ran the test harness, checked every `scene_type_bias` value against the real template directories, verified the wiring points against SceneGenerator's actual inputs. One real bug caught before it shipped (the zip's flat layout didn't match the paths the node expects). Best idea in the design: situations carrying a composition bias — a content→composition link the scenario system lacked.

**Why it matters:** first contribution to the pack from outside the partnership — and the review loop held. Nothing merged unreviewed, and the new node follows the two-axis architecture instead of fighting it.

---

## Claude's Expansion Batch 1: Venue Pool (2026-08-22)

**What happened:** Alexander relayed Claude's response to `EXPANSION-BRIEF.md` — five new venue JSONs (fishing_village, lighthouse, dockside_market, smugglers_cove, naval_frigate — 8 situations each) plus a fix to cruise_ship's `boarding` situation (pirate copy-paste heritage: `violent_capable`→`calm_capable`, `face_off`→`gathering`) and a beyond-relabel `man_overboard` addition, both explicitly flagged in SUMMARY.md.

**Ellie's review:** schema validation across all six files, the pack's test harness (composer/context/layout — all green), Claude's coverage_audit.py run against the staged merge (8 venues, 59 situations, every genre × archetype × tone join ≥2), and manual register checks against the idioms-that-render-literally lesson from the image audits. Verdict: pass, no text edits requested. All five venues slotted into existing `coastal` and `nautical_vessel` archetypes — no new facet tags, no shared-axis changes smuggled in with the venue data.

**Deploy:** Alexander's go → committed `a2fc4c8`, pushed, copied to the live pack, ComfyUI restarted. Atmosphere proposal (preposition-led rewrite + one storm flourish) applied with his approval. Smoke render from `lighthouse` verified end-to-end: lamp-room tending scene, composed context, oglafstyle linework.

**Review-loop lesson:** the one genuine snag was Ellie's own smoke workflow, not Claude's batch — the baseline `krea2_gen_basic.json` carries a vestigial `text` field on node 423 that `YANC MultilineString` silently ignores (its real input is `string`), so a prompt written to `text` renders whatever `string` last held. First render came back as Alexander's morning fox-in-a-data-center test. `object_info` is the authority on real input fields; lesson recorded in TOOLS.md.

## Three Features, One Restart: Batch 2 + Indoor Atmosphere + Character Staging (2026-08-22)

**Claude's Expansion Batch 2 (nine venues, three archetypes):** Ellie authored `EXPANSION-BRIEF-2.md` with an explicit brief-to-breadth mandate — nine new venues across three new archetypes (frontier/institutional/civic) to break the nautical skew Alexander flagged. Claude delivered on it; Ellie's review verified genre×archetype×tone joins, situation-tag judgments (swaps accepted: `mountain_relay_station`, `forest_ranger_station`), and ran the extended coverage audit — verdict PASS, merged `a0d50de`.

**Indoor atmosphere — Alexander's design over both AI drafts:** Claude proposed an `indoor` env value; Alexander resolved it differently: interiors shouldn't *always* convey outside circumstances, and window framing must not dominate. The shipped design is orthogonal — an `indoor: true` flag on 28 situations, a 35% window roll (the window clause inherits the situation's own weather env) versus 65% room flourishes (lamplight, candlelit, "in the dead of night"), and bidirectional leak-proofing so outdoor scenes can never draw indoor flourishes either. Two of Ellie's own pre-test catches: the storm window phrase reworded weather-neutrally ("the window darkened by the storm outside") to cover snowbound scenes, and the outdoor fallback filtered against the indoor pool. Commit `5baaac9` — Claude's flag, Alexander's call, Ellie's implementation.

**Character staging — Alexander's proposal, built same day:** many-to-one character inputs on the Picker and Composer. Alexander described the growing-input mechanism and, crucially, the restraint — no per-scene action choreography, just lateral placement ("on the left is a [character]"). Ellie's implementation choices: static four optional STRING inputs (`character_1..4`, typed or wired) instead of JS autogrow — native autogrow is V3-schema-only (frontend issue #9363), and the classic JS reveal pattern is unverifiable without a browser; a soft cap of 4 matches the diffusion mush threshold anyway. Placement pools scale with cast size, seeded after the flourish draw so scenes with no characters wired are byte-identical to before. Commit `04efd64`.

**The deploy rhythm that emerged:** stage everything to the live pack while the server runs (module-level caches make copied files inert), then one restart lights the whole batch. Smoke render after restart: seed 42, `snowbound_wait` at the waystation, two characters staged — and the vision model read back the staging (figures spread left/center/right) plus the storm window with snow outside it. Honest note: the prompt staged two figures; diffusion rendered three. Cast control is influence, not command.

## The Scene Character Roller (2026-08-22)

**Alexander's design, delivered as a full feature set mid-session:** pose + positioning toggles on *both* the character node and the scene nodes ("we might want to use it exclusively to the setting, or let a little stochastism decide … if there's conflict, that's on the user"), a name field ("I suspect it helps the model cohere details to specific characters" — it mirrors his `xxxx`→StringReplace binding), detail High/Low (born from a real failure mode: excessive face detail pulls full-length characters into close-ups; Low = wide-shot legible tier), and a per-character consistency slider where 0 is his old randomizer's chaos and 1 locks each figure to genre + outfit family.

**Ellie's implementation:** genre-tagged wardrobe families (two per genre — age_of_sail/frontier, workwear/streetwear, flightline/colony, wanderer/guild) each carrying layers, palettes, wear states, and role-tagged concepts; genre resolves once per run and is shared by the cast; consistency is a Bernoulli coin per character — heads inherits the shared family and palette, tails rolls a rogue (firm genre confines rogues to that era's families; 🎲 lets them cross everything). Detail tiers are tags on the same ladder, not two pools — both modes *sample*, per Alexander's "even full detail is roughly randomized" note. "Roles" (leader, warrior, healer…) instead of "archetypes" — the setting system owns that word.

**Two catches before commit:** the bare-template set for positioning mode landed as a sibling of `placements`, but the Part 1 loader cached only the `placements` subtree — invisible until the picker smoke hit a `KeyError`. And new widgets slot after `seed` on the Picker/Composer so saved workflows keep their widget-value mapping and load clean with toggles defaulting off. Defaults preserve Part 1 byte-for-byte: nothing wired, toggles off → the seed-42 reference prompt is unchanged. **Post-ship correction — the one-to-one reshape:** two hours after the first commit, Alexander flagged a packaging mismatch he'd carried since the design talk: he'd pictured a character node as *one-to-one* — each node generates one character, more nodes for a bigger cast — the ComfyUI idiom. The cast-node packaging (count input, four outputs, shared-family inheritance) was Ellie's, set in her v1 sketch and never explicitly re-examined; the mechanics underneath were agreed, the container wasn't. Reshaped same session: one node rolls one character (outputs: `character`, `components_json`, `seed_used`). The per-character consistency coin became a per-*garment* coin — consistency now measures how much this one character honors its era's substyle, piece by piece (1 = one family head to toe; 0 = every piece rolls independently, firm genre keeping the mismatch within the era). Genre rolls per node: a shared-era cast means firm genres on every node, 🎲 per node is deliberate cross-era casting. Banks, detail tiers, roles, the name field, and the pose/positioning toggles carried over unchanged — the second 18-check battery went green on the first run.

Banks are deliberately thin — mechanics first, bank expansion is the next brief.

**Staging semantics settled (option B):** Alexander's ruling — "toggle off, by default, means no output of that kind" — flipped `_stage_characters`: off-off = plain `"; ".join(chars)`, the renderer arranges; positioning on = the Part 1 placement templates; pose decorates each figure and composes with the templates. The interim `bare` template set retired with the flip — one mechanism, no forks. Doubling when both levels fire is user discretion, on record ("not our problem"). Consequence noted: the seed-42 waystation reference now needs positioning ON to reproduce, since the default changed underneath it.

**Identity layer (age/sex/race, same day):** Alexander's nod closed the fork — option B, the coherent roll: 🎲 resolves an identity up front and *emits* it ("an older Black woman"), with feature banks softly weighted toward it (match 4× / untagged 2× / mismatch 1×, multiplied across axes, never zero). His contract words: "consistent but individually exclusive" — the phrase guarantees coherence while each detail draws independently; his follow-up pinned the failure mode to avoid: features sharing a tag must never roll *together*. Verified decoupled — P(age-matched face | age-matched hair) vs not, diff 0.02 over 1,200 rolls. Tagging made the banks honest: pools were age-mixed (crow's feet beside smooth cheeks); now every entry carries tags where they apply. Complexion is the one hard key — race-keyed phrases at detail=high only, ~75% draw; dropdown values never enter any string raw. Dropdowns appended after `seed` per the widget-mapping law; 🎲 default on all three. Two test-side stumbles during the battery, both expectations rather than code: a regex that didn't match two-word races or hyphenated ages, and an expected phrase written race-first when the construction is age-race-sex.

## Claude's Expansion Batch 3: sci_fi Depth + Tones + Atmosphere (2026-08-22)

**What happened:** Alexander relayed Claude's response to `EXPANSION-BRIEF-3.md` (Phase A only — new genres deferred pending the subgenre solution). Six venue JSONs (orbital_concourse, starship_hangar, colony_greenhouse, salvage_yard, transit_platform, plus the research_outpost stretch goal), a tones top-up (triumphant, melancholy, solemn, romantic, restless), and an atmosphere top-up (10 flourishes, existing env values only).

**Ellie's review:** registry validation (all situation tags registered, all `scene_type_bias` values in the composition pools, zero typos — one suspected "schedule boar" was a 70-char truncation in my own survey, the text reads "board"), schema parity with the existing 17 venues (exact key set), id uniqueness, no text overlap with existing flourishes, and the register pass: era-neutral situation text throughout ("queueing at a boarding gate," not "queueing for the shuttle" — genre lives in venue name + subject_label + wardrobe, exactly per the brief), noun phrases, actions anchor, no gendered pronouns. Full battery + `--lint` green on the staged merge. sci_fi 3→9 (beats the 8+ target); station facet 2→6, small_crew 8→12. Claude flagged the tones top-up as needing Alexander's sign-off — that sign-off exists in advance: the five tones are the exact list Brief 3 proposed and Alexander approved. Verdict: pass, no edits requested.

**Same-day bookends:** the SceneGenerator retirement landed in the same session (`c147b0f`) — the Ideogram-era node moved to `attic/`, pack now torch-free and verified by actually executing `__init__.py` in package context in a torchless sandbox. Counts after both: 23 venues, 169 situations, 10 tones, 21 flourishes, 47-genre-pair dropdowns all registry-derived.
