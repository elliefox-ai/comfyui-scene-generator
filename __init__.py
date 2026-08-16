from .scene_gen import SceneGenerator
from .outpaint_controller import OutpaintController
from .inpaint_painter import InpaintPainter
from .prompt_peek import PromptPeek
from .diagnostics import VAERoundTrip, LatentBoundaryAnalyzer

NODE_CLASS_MAPPINGS = {
    "SceneGenerator": SceneGenerator,
    "OutpaintController": OutpaintController,
    "InpaintPainter": InpaintPainter,
    "PromptPeek": PromptPeek,
    "VAERoundTrip": VAERoundTrip,
    "LatentBoundaryAnalyzer": LatentBoundaryAnalyzer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneGenerator": "🗳️ Scene Generator (Ideogram 4)",
    "OutpaintController": "🎨 Outpaint Controller",
    "InpaintPainter": "🖌️ Inpaint Painter",
    "PromptPeek": "🔍 PromptPeek (image → prompt)",
    "VAERoundTrip": "🔧 VAE Round-Trip",
    "LatentBoundaryAnalyzer": "🔧 Latent Boundary Analyzer",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
