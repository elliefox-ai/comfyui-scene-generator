from .scene_gen import SceneGenerator
from .scene_context_node import SceneContextPicker
from .scene_context_composer import SceneContextComposer
from .scene_character_roller import SceneCharacterRoller

NODE_CLASS_MAPPINGS = {
    "SceneGenerator": SceneGenerator,
    "SceneContextPicker": SceneContextPicker,
    "SceneContextComposer": SceneContextComposer,
    "SceneCharacterRoller": SceneCharacterRoller,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneGenerator": "🗳️ Scene Generator (Ideogram 4)",
    "SceneContextPicker": "🧭 Scene Context Picker",
    "SceneContextComposer": "🎼 Scene Context Composer",
    "SceneCharacterRoller": "🎲 Scene Character Roller",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
