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
| Reads entire codebase in seconds | Tests actual image generation in ComfyUI |
| Identifies root causes across systems | Sees visual output and aesthetic problems |
| Writes, tests, and deploys code | Decides what looks right and what doesn't |
| Calculates exact pixel sizes and ratios | Knows when characters are "too small" by eye |
| Generates content (backgrounds, subjects, actions) | Provides creative direction and domain expertise |
| Spots architectural patterns and inconsistencies | Catches UX/confusion problems in the design |
| Maintains memory across sessions | Makes product and priority calls |

Neither side can ship this project alone. Ellie can't see images or judge visual quality. Alexander shouldn't have to calculate bbox scaling factors or trace RNG state through a prompt builder. The division isn't "creative vs. technical" — it's *what each participant is actually good at*.

---

## The Wrong Turns

For honesty, things Ellie got wrong that Alexander caught:

1. **Background cues described character size** → should have described camera distance
2. **Template-first background priority** → broke thematic coherence
3. **`_build_preview_elements()` used wrong RNG seed** → preview showed different characters than output (this was a pre-existing bug, but Ellie wrote the fix)
4. **Scene types named like genres** → confused with scenario genres
5. **Backgrounds weren't shot-width-aware** → close-ups got "wide open spaces" descriptions

Every one of these was caught through the test-feedback loop, not through code review alone. The collaboration works because both sides are willing to say "that's wrong" and mean it.
