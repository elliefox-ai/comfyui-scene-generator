from .scene_gen import SceneGenerator
from .outpaint_controller import OutpaintController
from .inpaint_painter import InpaintPainter

NODE_CLASS_MAPPINGS = {
    "SceneGenerator": SceneGenerator,
    "OutpaintController": OutpaintController,
    "InpaintPainter": InpaintPainter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneGenerator": "🗳️ Scene Generator (Ideogram 4)",
    "OutpaintController": "🎨 Outpaint Controller",
    "InpaintPainter": "🖌️ Inpaint Painter",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
