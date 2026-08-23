"""Registry tests — the tag law must catch what it promises to catch.

Exit 0 = pass. Run: python3 test_scene_tags.py
"""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scene_tags  # noqa: E402
from scene_context_node import GENRE_OPTIONS, GENRE2_OPTIONS, RANDOM  # noqa: E402


def main():
    tags = scene_tags.load_tags()
    assert {"genre", "facet", "situation"} <= set(tags), "core namespaces missing"
    assert {"identity_age", "identity_sex", "identity_race"} <= set(tags), \
        "identity namespaces missing"
    print(f"registry loads: {len(tags['genre'])} genres, "
          f"{len(tags['facet'])} facets, {len(tags['situation'])} situation tags")

    legacy = scene_tags.validate_scene_tags()
    assert legacy == [], f"expected zero legacy notes after migration, got: {legacy}"
    print("full validation passes; zero legacy aliases remain (migrated 2026-08-22)")

    broken = copy.deepcopy(tags)
    del broken["facet"]["sea"]
    try:
        scene_tags.validate_scene_tags(tags=broken)
    except ValueError as e:
        assert "sea" in str(e), "error must name the missing tag"
        assert "harbor_tavern" in str(e) or "pirate" in str(e).lower() \
            or "venue" in str(e), "error must name a venue"
        print(f"negative test: unknown facet caught, names the venue — "
              f"{str(e).splitlines()[0]}")
    else:
        raise AssertionError("removing 'sea' from the registry must fail validation")

    broken_age = copy.deepcopy(tags)
    del broken_age["identity_age"]["older"]
    try:
        scene_tags.validate_scene_tags(tags=broken_age)
    except ValueError as e:
        assert "older" in str(e), "error must name the missing identity value"
        print("negative test: unknown identity value caught")
    else:
        raise AssertionError("removing 'older' must fail validation (complexion/features)")

    expected = [RANDOM] + list(tags["genre"])
    assert GENRE_OPTIONS == expected, "GENRE_OPTIONS must derive from registry"
    assert GENRE2_OPTIONS[0] == "none" and GENRE2_OPTIONS[1:] == GENRE_OPTIONS, \
        "GENRE2_OPTIONS must be none + genre options"
    print("enums derive from the registry — structural parity confirmed")

    print("REGISTRY TESTS PASS")


if __name__ == "__main__":
    main()
