# Persona Architecture v2 — Design Spec (draft 1, 2026-08-30)

## Ruling (Alexander, 11:28)
Clean structure over backward compatibility. No preset aliases for old workflows.
Breaking change accepted; old seeds will not reproduce. This is the final-production
baseline, not an incremental ship.

## Role surface
- `role` param: closed persona set (or `"any"`). No occupation names.
- Personas: **warrior, worker, scholar, healer, leader, drifter, athlete, caregiver,
  charmer, gala**.
- **CONFIRMED (Alexander, 11:56): official retired → split leader/worker.**
  Authority register → leader; process register → worker.
  His silhouette test, verbatim: *"Big coats and big hats versus coveralls
  and tight caps."* Persona set locked at ten.

## Persona table — `personas.json` (new file)
One row per persona. Weights only — nothing hard-locked, unlisted = baseline.

```json
{
  "warrior": {
    "family_leans":  {"streetwear": 1.4, "enclave": 1.8, "wanderer": 1.5},
    "garment_leans": {
      "by_substring": {"moto jacket": 2.0, "combat boots": 1.8, "flak vest": 2.2,
                        "kilted wrap": 1.6, "steel-toed boots": 1.5}
    },
    "feature_leans": {"marks": 1.5, "build_broad": 1.4},
    "wear_leans":    {"worn": 1.3, "pristine": 0.7},
    "posture_lean":  "confident",
    "uniform_look":  null
  }
}
```

- Selection = multipliers on EXISTING draw probabilities. Garment/family weights
  are the new half; the old concept-boost half died with the concepts bank
  (retired 13:39).
- `uniform_look`: optional reference into the harvested costume library.

## Concepts bank — RETIRED (Alexander, 13:39)
- **Ruling:** the profession-claims conception "made more sense before we
  achieved so much other structure, and it just needs to be retired now."
  The concepts bank was the identity-flavor mechanism before personas existed;
  in v2 personas own identity (weights + uniform looks), archetypes own
  garments, scenarios own settings — the bank's job is extinct. No retag
  mapping; the whole claim slot leaves the character line.
- Mechanically: characters stop making noun identity claims ("a jazz
  trumpeter", "a promoter"). The description asserts only what it places —
  garments, features, posture, persona-derived silhouette. The supported-
  claims law (13:26) applied wholesale instead of case-by-case.
- Enumeration pass becomes classification-for-EXTRACTION, not retagging.
  Default disposition = retire. Anything worth keeping (occasion flavor like
  "a wedding guest", "a first date") re-enters only as ANCHORED prose — a
  scenario line where the setting can back the claim. Instruments/venues
  re-enter as conscious scenario choices (cf. attic noir's "a jazz club
  backstage at 2 AM").
- Build wave simplifies: the roller swap REMOVES the concepts draw instead of
  remapping ~25 entries.
- **Salvage classification complete (14:03, work order closed):** 126 concepts
  across 17 families enumerated. 124 pure profession/mood claims -> retire
  outright (default per ruling, no case-by-case). Salvage candidates —
  occasion flavor only: "a wedding guest", "a first date" (evening family),
  re-entering ONLY as anchored scenario prose. Borderline, defaulting retire:
  "a traveling gambler in borrowed finery" (frontier_town — wear-anchored but
  identity-first). The bank's data stays in character_wardrobe.json as a
  flavor QUARRY: the micro-character writing ("a topman with rope-scarred
  hands", "a barkeep who's heard every story twice") seeds future
  treatment/scenario pools. Same disposition as the legacy ambient bank —
  mechanism retired, prose lives.

## Costume table disposition
- `occupation_costumes.json` → data source only, no longer a param surface.
- Entries referenced by persona `uniform_look` (nurse→healer, sommelier→charmer, ...).
- Occupations with no persona home: garments harvested where they fit, rest retired.
- Uniform looks fire as ONE weighted option inside their persona.

## Authenticity dial (0/1/2, default 1)
- **0 stylized** — pristine wear up, marks down, builds heightened, stagewear
  silhouettes welcome, uniform looks suppressed.
- **1 exaggerated/cinematic** — v2 baseline (today's register).
- **2 documentary** — worn states up, marks up, exotic suppressed, uniform looks
  boosted; uniform vs costume noun flip lives here.
- Implementation: multiplier layer over wear/marks/feature weights + noun flip.
  No new phrase bank.
- Register logic: persona has `uniform_look` + authenticity high → *"uniform"*;
  no uniform look (or low authenticity) → *"costume"* reading.
- First concrete uniform×authenticity rule (Alexander, 12:22, re: maid): at
  documentary level, uniformed looks FLATTEN toward utilitarian — *"the
  non-stylized uniform is very flat and utilitarian. Either a plain dress or
  a tee and pants."* The pinafore is the costume reading; the plain dress /
  tee+pants is the uniform reading. Implementation candidate: a documentary
  multiplier shifts weight from costume-y pieces within a uniform look toward
  plain items already on the shelf.

## Discipline
- WITHIN v2: same seed → same output. Kept.
- ACROSS versions: none (dropped by ruling). All four harnesses re-baselined to v2.
- **Supported claims only (Alexander, 13:26):** the description never asserts an
  identity its own text can't back — every emitted claim gets at least one
  anchor (garment, prop, or setting) or the claim drops. Nothing declared that
  can't be placed; same philosophy as the mark/wrist placement fix.

## Build order (after Alexander's persona veto/merge)
1. ✅ Persona set confirmed (Alexander, 11:56) — ten personas, official retired.
2. ✅ `personas.json` draft seeded from census (draft 1 — weights are flagged
   judgment calls; coarse feature/wear/posture keys map to real vocab at wiring).
   Concepts bank retired (13:39): the roller swap REMOVES the concepts draw
   (extraction pass classifies the bank for salvage) — lands WITH the swap so
   local tests never strand red mid-wave.
3. ✅ Roller swapped (2026-08-30 ~14:25) — role → closed persona set
   (`_load_personas`, hard error on missing file); family/garment/wear/build
   multiplier application; concepts draw REMOVED; uniform-look coin
   (stylized .05 / cinematic .25 / documentary .6, accessories dropped at
   documentary). Draw order: persona layer consumes no rng.
4. ✅ Authenticity dial landed WITH the swap (stylized/cinematic/documentary;
   wear pristine/worn multipliers, marks ×0.5/×1.0/×1.5 cap .9). Noun flip
   n/a — the concepts bank was retired instead (13:39).
5. ✅ Re-baseline harnesses; deploy as scene-gen v2 in one wave. — all five harnesses green (heat harness guards: closed
   persona set, nurse via healer@documentary, register divergence
   sweep, determinism). DEPLOY PENDING Alexander's window.

## Ambient activity — v2 (rulings through 13:26; design SETTLED, no code)
Old randomizer had banked ambient pools; v2 ports the CONCEPT, not the template
strings (clean break applies). Full legacy source saved verbatim:
`scene_context/ambient_legacy_bank.txt` (eye-candy bank + the long
civic/spectacle bank; "},|" junctions = ~17 original sub-bank seams — natural
bucket boundaries for the pools). **Legacy bank = QUARRY, not spec** (Alexander,
13:04): selective harvest; banks build up gradually and expand as we like.

### Node — DECIDED (Alexander leaned separate node and deferred; Ellie's call: yes)
Dedicated ambient node, same pattern as the character roller: optional free-text
description OR roll (text wins when present); own seed — keep the cast, reroll
the crowd. Home for count/bias dials later; keeps the scene node's face clean.
Code-side (v2 wave): new node module + ambient input slot in the composer.

### Interface: two dropdowns (Alexander, 13:19; greenlight 13:26; pools extended 13:59)
- `subject` — **none (default)** | accurate | sexy | absurd | cool | dorky |
  elegant | multiversal | random. Category entries (wholesome, militant, ...)
  join the list as the banks grow.
- `treatment` — **straight (default)** | satire | chaotic
- none + straight = zero ambient draws, byte-identical.
- Every earlier ruled option survives as a grid point: accurate = accurate +
  straight; sexy = sexy + straight; absurd = absurd + straight; cool = cool +
  straight; dorky = dorky + straight; elegant = elegant + straight;
  multiversal = multiversal + straight; satire = random + satire; chaotic =
  random + chaotic; random = random + random. Off-menu cells (bikini team x
  rampaging) come free — that was the point of the matrix.

### Contracts (12:44, unchanged)
- Heat governs the SUBJECT (wardrobe/pose); ambient governs the
  BACKGROUND. Two domains, two dials, no coupling, no precedence gates, no
  fallback logic. "None" adds nothing, never suppresses. A racy background
  requires deliberate selection — no accidental path.
- Order: ambient draws AFTER all character/garment draws — background never
  perturbs character rng.

### Treatments are CATEGORY-BIASED OPERATORS (Alexander, 13:26)
Bias direction = category -> treatment pool weights; generic operator phrases as
fallback; no hard locks (same law as personas). Unifying line, Alexander's:
**"humiliation is the subversion of seeming power or prestige."**
- **satire = puncture what the register claims:**
  - wholesome/satire — ironically rude or aggressive (Santa in a fistfight)
  - militant/satire — blended bias, two pools: (a) humiliation/puncture,
    shared with sexy/satire (an aide stumbling ungracefully); (b) a
    tender/gentle/nurture pool — the register-specific inversion the founding
    examples were always pointing at ("lavish attention on a small animal to
    one aide", "visible in the background, crocheting a large scarf");
    Alexander 13:32: militant is "also subverted by" tenderness
  - sexy/satire — dorky or slapstick-humiliated (LARPing; stumbling and
    falling ungracefully)
  - Structure note (13:32): satire's per-category bias is a BLEND — the
    generic humiliation pool plus, where the register claims hardness, a
    register-specific inversion pool (militant -> tender/gentle/nurture).
    Wholesome takes no tender-inversion: it is already tender; its inversion
    is rudeness. Both mechanisms are the register displayed as its own
    opposite.
- **chaotic = amp the register's own energy direction:**
  - wholesome/chaotic — making a mess, cussing a ruckus (fairies rampaging wild)
  - militant/chaotic — violent action (a different animal from militant/satire)
  - sexy/chaotic — drawing too much attention, causing a scene

### Vocabulary (subject-axis entries)
- accurate — genre/era-authentic ambient, straight world.
- satire — operator above; house style (infomercial hostesses, soap-opera
  villainess are seed material).
- absurd — single non-sequitur intrusions, played straight (the giant rubber
  duck: "a giant rubber duck {floating|impossibly large|art installation|surreal}").
- sexy — eye-candy cameo bank, straight (bikini team, playmates, decade pin-ups).
- cool — background presence, badass-to-ominous, played straight (leather
  jacket against a lamppost, motorcycle behind, sunglasses at night, the
  figure at the edge of frame with face half-lit). Composes with every genre;
  noir and sci-fi want it badly. Seed stock: motorcycle stunt riders, the
  scream queen's leather jacket, cyberpunk visors.
- dorky — earnest charm played straight (a tourist family mugging through
  photos in front of a deadly-serious scene). Also the HOME register for the
  dorky phrase-pool sexy/satire borrows. Thin in the legacy bank — the
  harvest stocks it fresh.
- elegant — high-register dress played straight: gowns, black tie, gala-goers,
  old money strolling past. Modern "accurate" is casual; this gives you
  dressed-up. Richest vein in the legacy bank (red carpet starlet, pageant
  queen, Monaco yacht guest, noir lounge singer). Feeds the gala persona's
  future shelf.
- Antipode structure (13:59): cool <-> dorky. Satire reads a register as its
  own opposite — dorky/satire = accidentally cool (the fumbling tourist nails
  a heroic pose; mirror of sexy/satire); cool/satire = deflated (sunglasses
  guy walks into a lamppost). Chaotic amps — cool/chaotic = action movie;
  dorky/chaotic = overwhelming earnest energy.
- Deferred to the harvest, not pre-committed: tender/soft (quieter than
  wholesome — everyday nurture; the banks decide). Animal-cute joins as a
  category bank when the harvest reaches it, not a dropdown entry.
- multiversal — 2-3 draws from DIFFERENT categories regardless of coherence.
  "Satire is a tone; multiversal is a physics." The Santa/UFO/cryptid/kaiju/
  Death-taking-a-break run of the legacy bank is its ammunition.

### Shared mechanics
- Persona bias one layer out (charmer -> eye-candy, scholar -> accurate,
  warrior -> chaotic). Bias, never lock.
- Authenticity interplay: satire/absurd read stylized — likely suppressed at
  documentary (2). Design sitting.

### Curation flags for the harvest (subagent brief, queued behind v2 core wave)
- Culturally/politically specific entries (regalia, named protest movements,
  religious ceremonies, "dwarf troupe") need taste calls: tag by genre/era vs
  drop. Design-sitting conversation, not a solo call.
- Era-capsule entries (decade pin-ups) -> tag as era costumes.
- Legacy entries carry EMBEDDED treatment phrases ("crocheting a large scarf")
  — strip at harvest into the operator pools' seed stock.
- Data work = big subagent hand-off (category-tagged subject pools +
  per-category treatment pools, with validators) — queued behind the v2 core
  wave.
## Open items not in this spec
- Gala gown/tuxedo item shelf (new garments — separate Claude hand-off when greenlit).
- Heat interplay (charmer × heat) — design sitting, after v2 core.
- Track D pool deepening — queued behind v2 (garment states may be retagged anyway).

### Ambient node — BUILT locally (2026-08-30 ~14:45)
- `scene_ambient.py`: **SceneAmbientActivity** (🎭 Scene Ambient Activity), registered in `__init__.py`; imports `_expand` from the roller via the pack's dual relative/bare pattern.
- Dropdowns: subject **none | accurate | wholesome | militant | sexy | absurd | cool | dorky | elegant | random | multiversal** (AMENDMENT to the 9-entry draft above: written before the final harvest — all eight pools are selectable). random = ONE pool per crowd (coherent); multiversal = per-figure pool draw (crossover). treatment none | satire | chaotic | random (per-figure 50/50). count 1–3. Own seed — "keep the cast, reroll the crowd"; draw order documented (pool → entry → treatment pick → phrase).
- Militant satire = blended cell (humiliation + tender_inversion merged); accurate/absurd fall back to generic operators (satire AND chaotic). Era tags carried data; v1 renders text only.
- Composer slot: optional `ambient` (forceInput) → "in the background, {fragment}" lands before the flourish beat; `components["ambient"]` records it. Unwired = byte-identical to the pre-ambient composer.
- `test_ambient.py` green via SIMULATION checks: random/multiversal/pinned crowds replay the documented draw order against the same banks and demand byte-equality — no output-side inference. Plus purity (no operator phrases at treatment=none), multiversal diversity, data-driven treatment-cell checks, composer slot. All five prior harnesses regression-green.
- Deploy wave contents: roller + heat + composer + ambient + __init__ + personas.json + ambient_banks_draft.json. Awaiting Alexander's window.

### DEPLOYED — v2 wave live on Megatron (2026-08-30 ~14:48)
- Alexander gave the window ("Let's deploy, I'll restart"). Wave md5-verified post-copy: roller (v2 personas/authenticity), composer (ambient slot), scene_ambient.py (new), __init__.py (4 nodes), personas.json + ambient_banks_draft.json (new data). heat was SAME (v1.1 already live; no-op). All six test harnesses shipped for pack self-consistency; scene_context drift sweep clean. Backups: /tmp/deploy-backup-v2-144705/.
- Deploy lesson: cp -p TO /mnt/e aborts (drvfs rejects utimes) — plain cp, md5 gate. First pass died mid-wave on this; idempotent re-copy recovered cleanly.
- Live verification pending Alexander's restart: object_info must show SceneAmbientActivity + composer ambient input; then smoke roll.
