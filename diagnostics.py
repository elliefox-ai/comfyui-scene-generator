"""
Diagnostic nodes for outpaint seam analysis.

VAERoundTrip: Encode → Decode without sampling. Shows VAE-only boundary artifacts.
LatentInspector: Saves latent statistics for analysis.
"""

import torch
import numpy as np
import folder_paths


class VAERoundTrip:
    """
    Encodes an image through the VAE and decodes it immediately.
    No sampling, no mask processing. Pure VAE encode → decode.
    
    Compare the output with the input to see if the VAE itself
    creates artifacts at mask/padding boundaries.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "vae": ("VAE",),
            },
            "optional": {
                "mask": ("MASK",),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "MASK")
    RETURN_NAMES = ("roundtripped", "difference", "mask_overlay")
    FUNCTION = "roundtrip"
    CATEGORY = "EllieFoxAI/Diagnostics"

    def roundtrip(self, image, vae, mask=None):
        # Encode → decode
        latent = vae.encode(image[:, :, :, :3])
        decoded = vae.decode(latent)

        # Pixel-level difference (amplified 5x for visibility)
        diff = torch.abs(image[:, :, :, :3] - decoded).clamp(0, 1)
        diff_amplified = (diff * 5).clamp(0, 1)

        # If mask provided, overlay it on the difference map
        if mask is not None:
            # Resize mask to match image
            mask_resized = torch.nn.functional.interpolate(
                mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])),
                size=(image.shape[1], image.shape[2]),
                mode="bilinear"
            ).squeeze(1)

            # Create overlay: green where mask=0 (source), red where mask=1 (padding)
            overlay = decoded.clone()
            # Red channel boost in padding area
            overlay[:, :, :, 0] = torch.clamp(overlay[:, :, :, 0] + mask_resized * 0.3, 0, 1)
            # Green channel boost in source area
            overlay[:, :, :, 1] = torch.clamp(overlay[:, :, :, 1] + (1 - mask_resized) * 0.2, 0, 1)
        else:
            overlay = decoded

        return (decoded, diff_amplified, overlay)


class LatentBoundaryAnalyzer:
    """
    Analyzes latent space at mask boundaries.
    Shows how the VAE represents the transition from source to padding.
    
    Outputs a heatmap showing latent energy at the boundary.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "vae": ("VAE",),
                "mask": ("MASK",),
                "boundary_width": ("INT", {"default": 32, "min": 8, "max": 128, "step": 8,
                                           "tooltip": "Width of boundary zone to analyze (in pixels on each side)"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("latent_heatmap", "boundary_zoom")
    FUNCTION = "analyze"
    CATEGORY = "EllieFoxAI/Diagnostics"

    def analyze(self, image, vae, mask, boundary_width=32):
        # Encode to latent
        latent = vae.encode(image[:, :, :, :3])

        # Latent shape: [B, C, H/8, W/8]
        # Compute per-channel energy (magnitude)
        latent_energy = torch.norm(latent, dim=1, keepdim=True)  # [B, 1, H/8, W/8]

        # Upscale to image resolution for visualization
        latent_up = torch.nn.functional.interpolate(
            latent_energy,
            size=(image.shape[1], image.shape[2]),
            mode="bilinear"
        )

        # Normalize to 0-1
        if latent_up.max() > 0:
            latent_norm = latent_up / latent_up.max()
        else:
            latent_norm = latent_up

        # Create heatmap: blue=low energy, red=high energy
        heatmap = torch.zeros_like(image[:, :, :, :3])
        heatmap[:, :, :, 2] = 1.0  # blue base
        # Add red where energy is high
        heatmap[:, :, :, 0] = latent_norm.squeeze(1)
        # Add green in mid-range
        mid = (latent_norm.squeeze(1) * (1 - latent_norm.squeeze(1))) * 2
        heatmap[:, :, :, 1] = mid

        # Resize mask for boundary detection
        mask_img = torch.nn.functional.interpolate(
            mask.reshape((-1, 1, mask.shape[-2], mask.shape[-1])),
            size=(image.shape[1], image.shape[2]),
            mode="bilinear"
        ).squeeze(1)

        # Find boundary (where mask transitions)
        mask_binary = (mask_img > 0.5).float()
        # Gradient of mask = boundary
        boundary = torch.zeros_like(mask_binary)
        boundary[:, :-1, :] += torch.abs(mask_binary[:, 1:, :] - mask_binary[:, :-1, :])
        boundary[:, :, :-1] += torch.abs(mask_binary[:, :, 1:] - mask_binary[:, :, :-1])
        boundary = torch.clamp(boundary, 0, 1)

        # Boundary zoom: show only boundary region with latent energy
        boundary_zoom = heatmap.clone()
        # Dim non-boundary areas
        boundary_mask = torch.clamp(boundary * 10, 0, 1).unsqueeze(-1)
        boundary_zoom = boundary_zoom * boundary_mask + image[:, :, :, :3] * (1 - boundary_mask) * 0.3

        return (heatmap, boundary_zoom)


# Node mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "VAERoundTrip": VAERoundTrip,
    "LatentBoundaryAnalyzer": LatentBoundaryAnalyzer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VAERoundTrip": "🔧 VAE Round-Trip (Diagnostics)",
    "LatentBoundaryAnalyzer": "🔧 Latent Boundary Analyzer",
}
