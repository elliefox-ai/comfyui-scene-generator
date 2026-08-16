"""
PromptPeek — image loader with live prompt inspection.

Select, cycle, or drop an image; the JS extension reads its PNG metadata
client-side and renders the prompt text directly on the node — no execution
needed. Server side, this node behaves as a normal LoadImage-style
passthrough and also extracts prompt text / raw prompt JSON at run time.
"""

import json
import os

import numpy as np
import torch
from PIL import Image, ImageOps

import folder_paths
import node_helpers

POSITIVE_CLASSES = {"CLIPTextEncode", "CLIPTextEncodeSDXL", "CLIPTextEncodeFlux"}
SAMPLER_CLASSES = {"KSampler", "KSamplerAdvanced"}
LOADER_CLASSES = {"CheckpointLoaderSimple", "UNETLoader", "CheckpointLoader"}


def _resolve_text(graph, ref):
    """Resolve a KSampler positive/negative link ref to its text-encode string."""
    if isinstance(ref, (list, tuple)) and len(ref) == 2:
        node = graph.get(str(ref[0]), graph.get(ref[0]))
        if isinstance(node, dict):
            text = node.get("inputs", {}).get("text", "")
            if isinstance(text, str):
                return text
    return None


def summarize_graph(graph):
    """Pull the interesting bits out of a ComfyUI prompt graph."""
    meta = {"positive": "", "negative": "", "model": "", "loras": []}
    sampler = None
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", ""))
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        if class_type in SAMPLER_CLASSES and sampler is None:
            sampler = inputs
            meta["positive"] = _resolve_text(graph, inputs.get("positive")) or meta["positive"]
            meta["negative"] = _resolve_text(graph, inputs.get("negative")) or meta["negative"]
        if class_type in LOADER_CLASSES and not meta["model"]:
            meta["model"] = inputs.get("ckpt_name") or inputs.get("unet_name") or ""
        if class_type == "LoraLoader":
            lora = inputs.get("lora_name")
            if lora:
                meta["loras"].append(lora)
    if not meta["positive"]:
        # Fallback heuristic: longest CLIPTextEncode text is the positive.
        longest = ""
        for node in graph.values():
            if isinstance(node, dict) and str(node.get("class_type", "")) in POSITIVE_CLASSES:
                text = node.get("inputs", {}).get("text", "")
                if isinstance(text, str) and len(text) > len(longest):
                    longest = text
        meta["positive"] = longest
    if sampler is not None:
        meta["seed"] = str(sampler.get("seed", sampler.get("noise_seed", "")))
        meta["steps"] = str(sampler.get("steps", ""))
        meta["cfg"] = str(sampler.get("cfg", ""))
        meta["sampler"] = str(sampler.get("sampler_name", ""))
    return meta


def extract_prompt_info(png_path):
    """Extract ComfyUI (or A1111) prompt metadata from a PNG file."""
    img = node_helpers.pillow(Image.open, png_path)
    raw = img.info or {}

    prompt_json = raw.get("prompt", "")
    params = raw.get("parameters", "")  # A1111-style fallback

    text = ""
    if prompt_json:
        try:
            graph = json.loads(prompt_json)
            if isinstance(graph, dict):
                text = summarize_graph(graph).get("positive", "")
        except (json.JSONDecodeError, TypeError):
            pass
    if not text and params:
        text = params
    return text, prompt_json or params


class PromptPeek:
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["image"])
        return {
            "required": {
                "image": (sorted(files), {
                    "image_upload": True,
                    "tooltip": "Image to inspect. Drop a file onto the node, upload, or cycle the input folder. The prompt it was generated with is shown live on the node.",
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "prompt_text", "prompt_json")
    FUNCTION = "load"
    CATEGORY = "EllieFoxAI"

    def load(self, image):
        path = folder_paths.get_annotated_filepath(image)
        img = node_helpers.pillow(Image.open, path)
        img = node_helpers.pillow(ImageOps.exif_transpose, img)
        img = img.convert("RGB")
        tensor = torch.from_numpy(np.array(img).astype(np.float32) / 255.0)[None,]
        text, raw = extract_prompt_info(path)
        return (tensor, text, raw)

    @classmethod
    def VALIDATE_INPUTS(cls, image):
        if not folder_paths.exists_annotated_filepath(image):
            return f"Invalid image file: {image}"
        return True

    @classmethod
    def IS_CHANGED(cls, image):
        return os.path.getmtime(folder_paths.get_annotated_filepath(image))
