"""
Outpaint Controller v4 — integrated image loading.

No separate LoadImage node needed. Upload directly in this node.
Auto-detects real image dimensions every time.

Outputs:
    left, right, top, bottom (INT) — drop into any padding node
    mask (MASK) — 1.0 in padded region (generate), 0.0 in source (preserve)
    padded_image (IMAGE) — source scaled + padding applied
    original_image (IMAGE) — the loaded source, for chaining
"""

import os
import hashlib
import torch
import numpy as np
import folder_paths
import node_helpers
from PIL import Image, ImageOps


ASPECT_RATIOS = {
    "16:9":  (1.0,       9.0/16.0),
    "3:2":   (1.0,       2.0/3.0),
    "4:3":   (1.0,       3.0/4.0),
    "1:1":   (1.0,       1.0),
    "4:3 v": (3.0/4.0,   1.0),
    "3:2 v": (2.0/3.0,   1.0),
    "9:16":  (9.0/16.0,  1.0),
}


class OutpaintController:
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["image"])
        return {
            "required": {
                "image": (sorted(files), {
                    "tooltip": "Select an uploaded image, or use the upload button in the grid panel."
                }),
                "aspect_ratio": (["custom"] + list(ASPECT_RATIOS.keys()), {
                    "default": "custom",
                    "tooltip": "Preset target aspect ratio. Sets target_width/height from long side."
                }),
                "source_resize": ("INT", {
                    "default": 0, "min": 0, "max": 8192, "step": 8,
                    "tooltip": "Scale source longest edge to this. 0 = no resize. Smaller = more padding room."
                }),
                "target_width": ("INT", {
                    "default": 1024, "min": 64, "max": 8192, "step": 8,
                }),
                "target_height": ("INT", {
                    "default": 1024, "min": 64, "max": 8192, "step": 8,
                }),
                "center_x": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                }),
                "center_y": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                }),
                "feather": ("INT", {
                    "default": 16, "min": 0, "max": 512, "step": 1,
                }),
                "edge_crop": ("INT", {
                    "default": 0, "min": 0, "max": 64, "step": 1,
                    "tooltip": "Crop this many pixels from each edge of the source before padding. Strips JPEG/compression artifacts that cause seams."
                }),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT", "INT", "MASK", "IMAGE", "IMAGE")
    RETURN_NAMES = ("left", "right", "top", "bottom", "mask", "padded_image", "original_image")
    FUNCTION = "compute_padding"
    CATEGORY = "EllieFoxAI"

    def _load_image_file(self, image_name):
        """Load image from ComfyUI input directory."""
        image_path = folder_paths.get_annotated_filepath(image_name)
        img = node_helpers.pillow(Image.open, image_path)
        img = node_helpers.pillow(ImageOps.exif_transpose, img)
        img = img.convert("RGB")
        image_np = np.array(img).astype(np.float32) / 255.0
        return torch.from_numpy(image_np)[None,]

    def compute_padding(self, image, aspect_ratio, source_resize,
                        target_width, target_height,
                        center_x, center_y, feather, edge_crop):

        # --- Load source image from file ---
        img_tensor = self._load_image_file(image)

        # --- Resolve target dimensions from aspect ratio ---
        if aspect_ratio != "custom" and aspect_ratio in ASPECT_RATIOS:
            rw, rh = ASPECT_RATIOS[aspect_ratio]
            long_side = max(target_width, target_height)
            if rw >= rh:
                W_t = long_side
                H_t = max(8, round(long_side * rh / 8) * 8)
            else:
                W_t = max(8, round(long_side * rw / 8) * 8)
                H_t = long_side
        else:
            W_t, H_t = target_width, target_height

        # --- Source dims from loaded tensor ---
        batch, src_h, src_w, _ = img_tensor.shape
        image = img_tensor

        # --- Apply source_resize (scale longest edge down) ---
        if source_resize > 0:
            longest = max(src_w, src_h)
            if longest > source_resize:
                scale = source_resize / longest
                new_w = max(8, round(src_w * scale / 8) * 8)
                new_h = max(8, round(src_h * scale / 8) * 8)
                image = torch.nn.functional.interpolate(
                    image.permute(0, 3, 1, 2),
                    size=(new_h, new_w),
                    mode='bilinear',
                    align_corners=False,
                ).permute(0, 2, 3, 1)
                src_w, src_h = new_w, new_h

        # --- Safety: if source still exceeds target, scale to fit ---
        if src_w > W_t or src_h > H_t:
            scale = min(W_t / src_w, H_t / src_h)
            new_w = max(8, round(src_w * scale / 8) * 8)
            new_h = max(8, round(src_h * scale / 8) * 8)
            image = torch.nn.functional.interpolate(
                    image.permute(0, 3, 1, 2),
                    size=(new_h, new_w),
                    mode='bilinear',
                    align_corners=False,
                ).permute(0, 2, 3, 1)
            src_w, src_h = new_w, new_h

        # --- Edge crop: trim artifacts from source edges ---
        if edge_crop > 0 and src_w > edge_crop * 2 and src_h > edge_crop * 2:
            image = image[:, edge_crop:src_h - edge_crop, edge_crop:src_w - edge_crop, :]
            src_w -= edge_crop * 2
            src_h -= edge_crop * 2

        # --- Compute padding from centerpoint (snap to 8px grid for VAE alignment) ---
        pad_left = max(0, round(center_x * max(0, W_t - src_w) / 8) * 8)
        pad_right = max(0, max(0, W_t - src_w) - pad_left)
        pad_top = max(0, round(center_y * max(0, H_t - src_h) / 8) * 8)
        pad_bottom = max(0, max(0, H_t - src_h) - pad_top)

        # --- Pad the image ---
        padded = torch.nn.functional.pad(
            image.permute(0, 3, 1, 2),
            (pad_left, pad_right, pad_top, pad_bottom),
            mode="constant", value=0,
        ).permute(0, 2, 3, 1)

        # --- Build mask (matches padded dims exactly) ---
        padded_h = src_h + pad_top + pad_bottom
        padded_w = src_w + pad_left + pad_right
        mask_np = np.ones((padded_h, padded_w), dtype=np.float32)

        x0, y0 = pad_left, pad_top
        x1, y1 = pad_left + src_w, pad_top + src_h

        x0c, y0c = max(0, x0), max(0, y0)
        x1c, y1c = min(padded_w, x1), min(padded_h, y1)
        if x1c > x0c and y1c > y0c:
            mask_np[y0c:y1c, x0c:x1c] = 0.0

        if feather > 0:
            for d in range(feather):
                alpha = 1.0 - d / feather
                if x0 + d < padded_w and x0 + d >= 0:
                    mask_np[:, x0 + d] = np.maximum(mask_np[:, x0 + d], alpha)
                if x1 - 1 - d >= 0 and x1 - 1 - d < padded_w:
                    mask_np[:, x1 - 1 - d] = np.maximum(mask_np[:, x1 - 1 - d], alpha)
                if y0 + d < padded_h and y0 + d >= 0:
                    mask_np[y0 + d, :] = np.maximum(mask_np[y0 + d, :], alpha)
                if y1 - 1 - d >= 0 and y1 - 1 - d < padded_h:
                    mask_np[y1 - 1 - d, :] = np.maximum(mask_np[y1 - 1 - d, :], alpha)

        mask = torch.from_numpy(mask_np).unsqueeze(0).repeat(batch, 1, 1)

        return (pad_left, pad_right, pad_top, pad_bottom, mask, padded, img_tensor)

    @classmethod
    def IS_CHANGED(cls, image):
        image_path = folder_paths.get_annotated_filepath(image)
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, image):
        if not folder_paths.exists_annotated_filepath(image):
            return f"Invalid image file: {image}"
        return True
