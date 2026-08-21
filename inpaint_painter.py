"""
Inpaint Painter — direct-canvas mask painting for inpaint workflows.

Load an image, paint a mask directly on the node canvas. No popup editors.
Outputs mask (MASK) and image (IMAGE) for any inpaint workflow.

The mask is painted in JS, serialized as base64 PNG in the mask_data widget,
and decoded to a tensor on execute.
"""

import os
import io
import base64
import hashlib
import torch
import numpy as np
import folder_paths
import node_helpers
from PIL import Image, ImageOps


class InpaintPainter:
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["image"])
        return {
            "required": {
                "image": (sorted(files), {
                    "tooltip": "Select an uploaded image, or use the upload button."
                }),
                "mask_data": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Painted mask data (base64 PNG). Populated by the canvas painter."
                }),
                "mask_color": (["white", "black"], {
                    "default": "white",
                    "tooltip": "Output mask value for painted areas. White = 1.0 (standard inpaint). Black = 0.0 (inverted)."
                }),
                "brush_size": ("INT", {
                    "default": 32, "min": 4, "max": 256, "step": 1,
                    "tooltip": "Brush radius in pixels."
                }),
            }
        }

    RETURN_TYPES = ("MASK", "IMAGE", "IMAGE")
    RETURN_NAMES = ("mask", "image", "masked_image")
    FUNCTION = "compute"
    CATEGORY = "EllieFoxAI"

    def _load_image_file(self, image_name):
        """Load image from ComfyUI input directory."""
        image_path = folder_paths.get_annotated_filepath(image_name)
        img = node_helpers.pillow(Image.open, image_path)
        img = node_helpers.pillow(ImageOps.exif_transpose, img)
        img = img.convert("RGB")
        image_np = np.array(img).astype(np.float32) / 255.0
        return torch.from_numpy(image_np)[None,]

    def compute(self, image, mask_data, mask_color, brush_size):
        # --- Load source image ---
        img_tensor = self._load_image_file(image)
        batch, h, w, _ = img_tensor.shape

        # --- Decode mask from base64 PNG ---
        if mask_data and len(mask_data) > 100:
            # Strip data URL prefix if present
            if mask_data.startswith("data:image"):
                _, b64 = mask_data.split(",", 1)
            else:
                b64 = mask_data
            try:
                mask_bytes = base64.b64decode(b64)
                mask_img = Image.open(io.BytesIO(mask_bytes)).convert("L")
                # Resize to match image exactly (in case of rounding drift)
                mask_img = mask_img.resize((w, h), Image.BILINEAR)
                mask_np = np.array(mask_img).astype(np.float32) / 255.0
            except Exception:
                mask_np = np.zeros((h, w), dtype=np.float32)
        else:
            # No mask painted — all zeros (nothing to inpaint)
            mask_np = np.zeros((h, w), dtype=np.float32)

        mask_tensor = torch.from_numpy(mask_np).unsqueeze(0).repeat(batch, 1, 1)

        if mask_color == "black":
            mask_tensor = 1.0 - mask_tensor

        # Masked image: source with painted area fully replaced using the selected mask color
        masked_tensor = img_tensor.clone()
        raw_mask = torch.from_numpy(mask_np).unsqueeze(0).repeat(batch, 1, 1).unsqueeze(-1)  # (B, H, W, 1)
        overlay_val = 1.0 if mask_color == "white" else 0.0
        # Fully opaque replacement where mask is painted
        masked_tensor = masked_tensor * (1.0 - raw_mask) + raw_mask * overlay_val

        return (mask_tensor, img_tensor, masked_tensor)

    @classmethod
    def IS_CHANGED(cls, image, mask_data, mask_color, brush_size):
        image_path = folder_paths.get_annotated_filepath(image)
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        m.update(mask_data.encode())
        m.update(mask_color.encode())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, image):
        if not folder_paths.exists_annotated_filepath(image):
            return f"Invalid image file: {image}"
        return True
