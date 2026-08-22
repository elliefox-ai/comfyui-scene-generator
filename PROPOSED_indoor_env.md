# Proposed: an "indoor" env value (sketch, not applied)

Flagged per the brief's ask to "propose how enclosed spaces should read."
This is a heavier lift than the batch-1 atmosphere tweak — it touches
`ENV_COMPAT` in `scene_context_node.py`, not just `atmosphere.json` data —
so this is a sketch for Alexander's call, not a ready diff.

## The concrete problem

Sampled live against the staged batch 2 pack:

> `mountain_relay_station` / `monitoring_the_instruments` — "monitoring a
> bank of dials and screens in the station's control room" — paired with
> **"beneath driving rain and storm-lit skies."**

The situation is indoors. The flourish describes an outdoor sky. Nothing
in the schema stops this today: an omitted `env` just means "any
flourish is eligible," and every current flourish describes a sky. This
isn't a new bug — `harbor_tavern`'s indoor situations have had the same
exposure since batch 1 — but batch 2 roughly doubles the indoor-heavy
venue count (mountain_waystation, mountain_relay_station,
forest_ranger_station, print_shop_alley all lean interior), so it's
worth naming now rather than letting it compound quietly.

## Sketch of a fix

1. Add an `"indoor"` env value to the atmosphere flourish vocabulary,
   with 2-3 interior-appropriate flourishes:
   ```json
   {"text": "by lamplight, the room close and warm", "env": "indoor"},
   {"text": "in the hush of a candlelit room", "env": "indoor"}
   ```
2. Extend `ENV_COMPAT` in `scene_context_node.py`:
   ```python
   ENV_COMPAT = {
       "storm": {"storm", "neutral", "overcast"},
       "clear": {"clear", "neutral"},
       "overcast": {"overcast", "neutral", "storm"},
       "indoor": {"indoor"},  # strict — no outdoor sky leaks in
   }
   ```
3. Tag genuinely enclosed situations `"env": "indoor"` — a judgment call
   per situation, not automatic from venue type (a waystation's yard
   scene is outdoor even though the venue is mostly an inn).

## Why this isn't just applied

- It's a code change, not a data drop-in — outside this batch's
  "no code changes needed" contract.
- Retroactively tagging existing indoor situations (harbor_tavern,
  print_shop_alley interiors, etc.) is a real editorial pass, not
  something to smuggle into a venue-content delivery.
- Alternative: leave it alone. The mismatch is mild ("driving rain"
  outside a window someone's sitting near isn't absurd) and forcing
  every interior situation to declare `env` narrows the atmosphere pool
  venue-by-venue, cutting against the decoupling-by-default principle.

Your call. Happy to write the full diff (data + code + audit-script
check for indoor situations missing the tag) if you want it — didn't
want to hand you an unreviewed `ENV_COMPAT` change alongside a venue
batch.
