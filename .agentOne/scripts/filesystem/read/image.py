from __future__ import annotations

import base64
import io
import os
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - worker env always installs Pillow
    Image = None
    ImageOps = None

MAX_EDGE_DEFAULT = 2048
_ALPHA_MODES = {"RGBA", "LA", "P"}


def _mime_for(fmt: str) -> str:
    return {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(fmt, "image/png")


def _encode_image(img: Image.Image) -> str:
    """Encode to a base64 data URI, keeping PNG for transparency."""
    has_alpha = img.mode in {"RGBA", "LA"} or "transparency" in img.info
    if has_alpha:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        fmt, mime = "PNG", "image/png"
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")
        fmt, mime = "JPEG", "image/jpeg"
    buffer = io.BytesIO()
    if fmt == "JPEG":
        img.save(buffer, format=fmt, quality=85)
    else:
        img.save(buffer, format=fmt)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def read_image(path: str, max_edge: int = MAX_EDGE_DEFAULT) -> tuple[bool, dict]:
    '''
    Read an image file from disk and inline it into the conversation as a
    multimodal image block.

    The image is downscaled so its longest edge is at most ``max_edge`` pixels
    (default 2048) and re-encoded (JPEG, or PNG when the image has
    transparency), then returned as a base64 data URI.  The LLM receives the
    data URI as an ``image_url`` content block; the previous text reply is
    preserved next to it.

    Args:
        path: The absolute or session-relative path to the image file.
        max_edge: Maximum length of the longest edge in pixels after
            downscaling.  Must be at least 64.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - content_type: "image"
            - image: str (base64 data URI to inline)
            - path: str
            - format: str ("JPEG" | "PNG")
            - width: int
            - height: int
            - max_edge: int
        On error, result contains:
            - status: "error"
            - message: str
    '''
    try:
        if not path:
            return (False, {'status': 'error', 'message': 'Path not provided'})
        if Image is None:
            return (False, {'status': 'error', 'message': 'Pillow is not installed on this worker'})

        p = Path(path).expanduser()
        if not p.is_file():
            return (False, {'status': 'error', 'message': f'Path is not a file: {path}'})

        try:
            img = Image.open(p)
            img = ImageOps.exif_transpose(img)
        except Exception as exc:
            return (False, {'status': 'error', 'message': f'Not a readable image file: {path}: {exc}'})

        with img:
            width, height = img.size
            max_edge = max(64, int(max_edge))
            longest = max(width, height)
            scale = min(1.0, max_edge / longest)
            if scale < 1.0:
                img = img.resize(
                    (max(1, int(width * scale)), max(1, int(height * scale))),
                    getattr(Image, "LANCZOS", Image.Resampling.LANCZOS),
                )
            data_uri = _encode_image(img)
            final_w, final_h = img.size

        return (True, {
            'status': 'success',
            'content_type': 'image',
            'image': data_uri,
            'path': str(path),
            'format': 'PNG' if 'image/png' in data_uri else 'JPEG',
            'width': final_w,
            'height': final_h,
            'max_edge': max_edge,
        })

    except Exception as exc:
        import traceback
        return (False, {'status': 'error', 'message': f'Error reading image {path}: {str(exc)}\n{traceback.format_exc()}'})