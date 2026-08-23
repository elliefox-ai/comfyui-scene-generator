from .scene_context_node import SceneContextPicker
from .scene_context_composer import SceneContextComposer
from .scene_character_roller import SceneCharacterRoller

NODE_CLASS_MAPPINGS = {
    "SceneContextPicker": SceneContextPicker,
    "SceneContextComposer": SceneContextComposer,
    "SceneCharacterRoller": SceneCharacterRoller,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneContextPicker": "🧭 Scene Context Picker",
    "SceneContextComposer": "🎼 Scene Context Composer",
    "SceneCharacterRoller": "🎲 Scene Character Roller",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
