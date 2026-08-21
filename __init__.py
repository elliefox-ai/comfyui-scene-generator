from .scene_gen import SceneGenerator

NODE_CLASS_MAPPINGS = {
    "SceneGenerator": SceneGenerator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneGenerator": "🗳️ Scene Generator (Ideogram 4)",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
