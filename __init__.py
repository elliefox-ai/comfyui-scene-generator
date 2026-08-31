from .scene_context_composer import SceneContextComposer
from .scene_character_roller import SceneCharacterRoller
from .scene_ambient import SceneAmbientActivity

NODE_CLASS_MAPPINGS = {
    "SceneContextComposer": SceneContextComposer,
    "SceneCharacterRoller": SceneCharacterRoller,
    "SceneAmbientActivity": SceneAmbientActivity,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneContextComposer": "🎼 Scene Context Composer",
    "SceneCharacterRoller": "🎲 Scene Character Roller",
    "SceneAmbientActivity": "🎭 Scene Ambient Activity",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
