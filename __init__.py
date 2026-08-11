from .scene_gen import SceneGenerator
from .outpaint_controller import OutpaintController

NODE_CLASS_MAPPINGS = {
    "SceneGenerator": SceneGenerator,
    "OutpaintController": OutpaintController,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneGenerator": "🗳️ Scene Generator (Ideogram 4)",
    "OutpaintController": "🎨 Outpaint Controller",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
