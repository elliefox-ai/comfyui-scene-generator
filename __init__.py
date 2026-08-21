from .scene_gen import SceneGenerator
from .scene_context_node import SceneContextPicker
from .scene_context_composer import SceneContextComposer

NODE_CLASS_MAPPINGS = {
    "SceneGenerator": SceneGenerator,
    "SceneContextPicker": SceneContextPicker,
    "SceneContextComposer": SceneContextComposer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneGenerator": "🗳️ Scene Generator (Ideogram 4)",
    "SceneContextPicker": "🧭 Scene Context Picker",
    "SceneContextComposer": "🎼 Scene Context Composer",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
