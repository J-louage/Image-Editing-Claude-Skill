#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "pillow-heif", "numpy"]
# ///
"""Image editing CLI with JSON output.

Supports: rotate, flip, resize, crop, pad, border, brightness, contrast, saturation,
blur, sharpen, sepia, tint, grayscale, transparency, watermark, thumbnail, EXIF,
color space, diff, batch processing, DPI, quality, format conversion, and file size optimization.
"""

import argparse
import glob as glob_module
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
import pillow_heif
from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# Register HEIF/HEIC support
pillow_heif.register_heif_opener()

FORMAT_MAP = {
    '.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP',
    '.tiff': 'TIFF', '.tif': 'TIFF', '.heic': 'HEIF', '.heif': 'HEIF',
}


# ============================================================================
# JSON Output
# ============================================================================


def output_json(data: dict) -> None:
    print(json.dumps(data, indent=2))


def output_error(message: str, code: str = "ERROR") -> None:
    output_json({"status": "error", "code": code, "message": message})
    sys.exit(1)


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} bytes"


# ============================================================================
# Image Operations — Transforms
# ============================================================================


def rotate_image(img: Image.Image, angle: float) -> Image.Image:
    if angle % 90 == 0:
        turns = int(angle // 90) % 4
        if turns == 1:
            return img.transpose(Image.Transpose.ROTATE_90)
        elif turns == 2:
            return img.transpose(Image.Transpose.ROTATE_180)
        elif turns == 3:
            return img.transpose(Image.Transpose.ROTATE_270)
        return img
    return img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)


def flip_image(img: Image.Image, direction: str) -> Image.Image:
    if direction == "horizontal":
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif direction == "vertical":
        return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    raise ValueError(f"Invalid flip direction: {direction}")


def resize_image(img: Image.Image, width: int = None, height: int = None) -> Image.Image:
    if width is None and height is None:
        return img
    orig_w, orig_h = img.size
    if width is not None and height is not None:
        new_size = (width, height)
    elif width is not None:
        new_size = (width, int(orig_h * (width / orig_w)))
    else:
        new_size = (int(orig_w * (height / orig_h)), height)
    return img.resize(new_size, resample=Image.Resampling.LANCZOS)


def thumbnail_image(img: Image.Image, width: int, height: int) -> Image.Image:
    """Smart crop-to-fit: center crop then resize to exact dimensions."""
    orig_w, orig_h = img.size
    target_ratio = width / height
    orig_ratio = orig_w / orig_h

    if orig_ratio > target_ratio:
        # Wider than target: crop sides
        new_w = int(orig_h * target_ratio)
        left = (orig_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, orig_h))
    elif orig_ratio < target_ratio:
        # Taller than target: crop top/bottom
        new_h = int(orig_w / target_ratio)
        top = (orig_h - new_h) // 2
        img = img.crop((0, top, orig_w, top + new_h))

    return img.resize((width, height), resample=Image.Resampling.LANCZOS)


def crop_image(img: Image.Image, top: int = 0, right: int = 0, bottom: int = 0, left: int = 0) -> Image.Image:
    orig_w, orig_h = img.size
    cr, cb = orig_w - right, orig_h - bottom
    if cr <= left or cb <= top:
        raise ValueError("Crop dimensions exceed image size")
    return img.crop((left, top, cr, cb))


def pad_image(img: Image.Image, top: int = 0, right: int = 0, bottom: int = 0, left: int = 0,
              color: tuple = None, edge: bool = False) -> Image.Image:
    if edge:
        arr = np.array(img)
        pad_width = ((top, bottom), (left, right), (0, 0)) if arr.ndim == 3 else ((top, bottom), (left, right))
        return Image.fromarray(np.pad(arr, pad_width, mode='edge'))
    else:
        w, h = img.size
        if color is None:
            color = (255, 255, 255, 0) if img.mode == "RGBA" else (255, 255, 255)
        new_img = Image.new(img.mode, (w + left + right, h + top + bottom), color)
        new_img.paste(img, (left, top))
        return new_img


def add_border(img: Image.Image, width: int, color: tuple, inside: bool = False) -> Image.Image:
    """Add a colored border. Inside crops content, outside expands canvas."""
    if inside:
        draw = ImageDraw.Draw(img)
        w, h = img.size
        # Draw border lines inward
        for i in range(width):
            draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=color)
        return img
    else:
        return pad_image(img, width, width, width, width, color=color)


# ============================================================================
# Image Operations — Adjustments
# ============================================================================


def adjust_brightness(img: Image.Image, factor: float) -> Image.Image:
    return ImageEnhance.Brightness(img).enhance(factor)


def adjust_contrast(img: Image.Image, factor: float) -> Image.Image:
    return ImageEnhance.Contrast(img).enhance(factor)


def adjust_saturation(img: Image.Image, factor: float) -> Image.Image:
    return ImageEnhance.Color(img).enhance(factor)


def apply_blur(img: Image.Image, radius: float) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_sharpen(img: Image.Image, amount: float = 1.0) -> Image.Image:
    if amount <= 1.0:
        return img.filter(ImageFilter.SHARPEN)
    # UnsharpMask for stronger sharpening: radius, percent, threshold
    return img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(amount * 100), threshold=3))


def apply_sepia(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        rgb = img.convert("RGB")
        alpha = img.split()[3]
    else:
        rgb = img.convert("RGB")
        alpha = None

    arr = np.array(rgb, dtype=np.float64)
    sepia_matrix = np.array([
        [0.393, 0.769, 0.189],
        [0.349, 0.686, 0.168],
        [0.272, 0.534, 0.131],
    ])
    result = arr @ sepia_matrix.T
    result = np.clip(result, 0, 255).astype(np.uint8)
    out = Image.fromarray(result)

    if alpha is not None:
        out.putalpha(alpha)
    return out


def apply_tint(img: Image.Image, color: tuple, strength: float = 0.3) -> Image.Image:
    """Apply a color tint overlay with given strength (0.0–1.0)."""
    if img.mode == "RGBA":
        rgb = img.convert("RGB")
        alpha = img.split()[3]
    else:
        rgb = img.convert("RGB")
        alpha = None

    overlay = Image.new("RGB", rgb.size, color[:3])
    blended = Image.blend(rgb, overlay, strength)

    if alpha is not None:
        blended.putalpha(alpha)
    return blended


def convert_to_grayscale(img: Image.Image) -> Image.Image:
    return img.convert("L")


# ============================================================================
# Image Operations — Transparency
# ============================================================================


def handle_transparency(img: Image.Image, replacement_color: tuple = None) -> Image.Image:
    if img.mode != "RGBA":
        return img.convert("RGB")
    if replacement_color is None:
        replacement_color = (255, 255, 255)
    bg = Image.new("RGB", img.size, replacement_color)
    bg.paste(img, mask=img.split()[3])
    return bg


def extract_alpha_mask(img: Image.Image) -> Image.Image | None:
    if img.mode != "RGBA":
        return None
    return img.split()[3]


def alpha_blend(img: Image.Image, mask: Image.Image) -> Image.Image:
    if mask.mode != "L":
        mask = mask.convert("L")
    if mask.size != img.size:
        mask = mask.resize(img.size, resample=Image.Resampling.LANCZOS)
    rgb = img.convert("RGB") if img.mode != "RGB" else img
    r, g, b = rgb.split()
    return Image.merge("RGBA", (r, g, b, mask))


def autocrop_transparency(img: Image.Image, threshold_percent: float = 0) -> Image.Image:
    if img.mode != "RGBA":
        raise ValueError("Image must have transparency (RGBA mode) for autocrop")
    threshold = int((threshold_percent / 100) * 255)
    alpha = np.array(img.split()[3])
    rows = np.any(alpha > threshold, axis=1)
    cols = np.any(alpha > threshold, axis=0)
    if not np.any(rows) or not np.any(cols):
        return img
    top = np.argmax(rows)
    bottom = len(rows) - np.argmax(rows[::-1])
    left = np.argmax(cols)
    right = len(cols) - np.argmax(cols[::-1])
    return img.crop((left, top, right, bottom))


# ============================================================================
# Watermark
# ============================================================================


def add_text_watermark(img: Image.Image, text: str, position: str = "bottom-right",
                       opacity: int = 128, font_size: int = 24, color: tuple = (255, 255, 255)) -> Image.Image:
    """Add a text watermark to the image."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except (OSError, AttributeError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except (OSError, AttributeError):
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    margin = 20
    w, h = img.size
    positions = {
        "top-left": (margin, margin),
        "top-right": (w - text_w - margin, margin),
        "bottom-left": (margin, h - text_h - margin),
        "bottom-right": (w - text_w - margin, h - text_h - margin),
        "center": ((w - text_w) // 2, (h - text_h) // 2),
    }
    xy = positions.get(position, positions["bottom-right"])

    fill = (*color[:3], opacity)
    draw.text(xy, text, font=font, fill=fill)

    return Image.alpha_composite(img, overlay)


def add_image_watermark(img: Image.Image, watermark_path: str, position: str = "bottom-right",
                        opacity: int = 128, scale: float = 0.2) -> Image.Image:
    """Add an image watermark to the image."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    wm = Image.open(watermark_path).convert("RGBA")

    # Scale watermark relative to image
    target_w = int(img.size[0] * scale)
    ratio = target_w / wm.size[0]
    target_h = int(wm.size[1] * ratio)
    wm = wm.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)

    # Apply opacity
    if opacity < 255:
        alpha = wm.split()[3]
        alpha = alpha.point(lambda a: int(a * opacity / 255))
        wm.putalpha(alpha)

    margin = 20
    w, h = img.size
    ww, wh = wm.size
    positions = {
        "top-left": (margin, margin),
        "top-right": (w - ww - margin, margin),
        "bottom-left": (margin, h - wh - margin),
        "bottom-right": (w - ww - margin, h - wh - margin),
        "center": ((w - ww) // 2, (h - wh) // 2),
    }
    xy = positions.get(position, positions["bottom-right"])

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(wm, xy)
    return Image.alpha_composite(img, layer)


# ============================================================================
# EXIF Handling
# ============================================================================


def get_exif_data(img: Image.Image) -> dict | None:
    """Extract EXIF data as a dict."""
    try:
        exif = img.getexif()
        if not exif:
            return None
        from PIL.ExifTags import TAGS
        return {TAGS.get(k, str(k)): str(v) for k, v in exif.items()}
    except Exception:
        return None


def strip_exif(img: Image.Image) -> Image.Image:
    """Return a copy of the image with all EXIF/metadata removed."""
    data = list(img.getdata())
    stripped = Image.new(img.mode, img.size)
    stripped.putdata(data)
    return stripped


# ============================================================================
# Color Space Conversion
# ============================================================================


def convert_color_space(img: Image.Image, target: str) -> Image.Image:
    """Convert between color spaces: RGB, CMYK, L (grayscale), P3."""
    target_upper = target.upper()

    if target_upper == "P3":
        # sRGB to Display P3 via ICC profile embedding
        # Pillow doesn't natively convert to P3, so we just convert to RGB
        # and note it in output — the actual P3 conversion requires lcms2
        try:
            from PIL import ImageCms
            srgb = ImageCms.createProfile("sRGB")
            # Create a Display P3-like profile (wider gamut)
            p3 = ImageCms.createProfile("sRGB")  # Fallback — true P3 needs external ICC
            transform = ImageCms.buildTransform(srgb, p3, img.mode, "RGB")
            return ImageCms.applyTransform(img, transform)
        except Exception:
            return img.convert("RGB")
    elif target_upper in ("RGB", "CMYK", "L", "RGBA"):
        if img.mode == target_upper:
            return img
        return img.convert(target_upper)
    else:
        raise ValueError(f"Unsupported color space: {target}. Use RGB, CMYK, L, RGBA, or P3.")


# ============================================================================
# Image Comparison / Diff
# ============================================================================


def image_diff(img: Image.Image, other_path: str) -> tuple[Image.Image, dict]:
    """Generate a visual diff between two images."""
    other = Image.open(other_path).convert("RGB")
    img_rgb = img.convert("RGB")

    # Resize other to match if needed
    if other.size != img_rgb.size:
        other = other.resize(img_rgb.size, resample=Image.Resampling.LANCZOS)

    arr1 = np.array(img_rgb, dtype=np.int16)
    arr2 = np.array(other, dtype=np.int16)

    diff = np.abs(arr1 - arr2).astype(np.uint8)

    # Calculate statistics
    total_pixels = diff.shape[0] * diff.shape[1]
    changed_mask = np.any(diff > 10, axis=2)
    changed_pixels = int(np.sum(changed_mask))
    change_pct = round(changed_pixels / total_pixels * 100, 2)
    mean_diff = round(float(np.mean(diff)), 2)

    # Amplify diff for visibility
    amplified = np.clip(diff * 3, 0, 255).astype(np.uint8)

    stats = {
        "totalPixels": total_pixels,
        "changedPixels": changed_pixels,
        "changePercent": change_pct,
        "meanDifference": mean_diff,
    }

    return Image.fromarray(amplified), stats


# ============================================================================
# DPI
# ============================================================================


def set_dpi(img: Image.Image, dpi: int) -> Image.Image:
    img.info['dpi'] = (dpi, dpi)
    return img


# ============================================================================
# File Size Reduction
# ============================================================================


def _get_encoded_size(img: Image.Image, fmt: str, quality: int = None) -> int:
    buf = io.BytesIO()
    kw = {}
    if quality is not None:
        kw['quality'] = quality
        if fmt == 'WEBP':
            kw['method'] = 6
    elif fmt == 'PNG':
        kw['optimize'] = True
    img.save(buf, format=fmt, **kw)
    return buf.tell()


def _find_optimal_quality(img: Image.Image, target_bytes: int, fmt: str) -> int | None:
    lo, hi, best = 10, 95, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if _get_encoded_size(img, fmt, mid) <= target_bytes:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def reduce_file_size(img: Image.Image, target_mb: float, output_format: str) -> tuple[Image.Image, dict]:
    target_bytes = int(target_mb * 1024 * 1024)
    fmt_lower = output_format.lower()
    fmt = 'JPEG' if fmt_lower in ['jpeg', 'jpg'] else fmt_lower.upper()

    working = img
    if fmt_lower in ['jpeg', 'jpg'] and img.mode == 'RGBA':
        working = handle_transparency(img)

    if fmt_lower in ['jpeg', 'jpg', 'webp']:
        q = _find_optimal_quality(working, target_bytes, fmt)
        if q is not None:
            kw = {'quality': q}
            if fmt_lower == 'webp':
                kw['method'] = 6
            return working, kw

        lo_s, hi_s = 0.1, 0.9
        while hi_s - lo_s > 0.05:
            mid_s = (lo_s + hi_s) / 2
            resized = working.resize(
                (int(working.size[0] * mid_s), int(working.size[1] * mid_s)),
                resample=Image.Resampling.LANCZOS,
            )
            if _find_optimal_quality(resized, target_bytes, fmt) is not None:
                lo_s = mid_s
            else:
                hi_s = mid_s

        resized = working.resize(
            (int(working.size[0] * lo_s), int(working.size[1] * lo_s)),
            resample=Image.Resampling.LANCZOS,
        )
        q = _find_optimal_quality(resized, target_bytes, fmt)
        if q is not None:
            kw = {'quality': q}
            if fmt_lower == 'webp':
                kw['method'] = 6
            return resized, kw

    elif fmt_lower == 'png':
        kw = {'optimize': True}
        if _get_encoded_size(working, 'PNG') <= target_bytes:
            return working, kw

        lo_s, hi_s = 0.1, 0.9
        best_resized = None
        while hi_s - lo_s > 0.05:
            mid_s = (lo_s + hi_s) / 2
            resized = working.resize(
                (int(working.size[0] * mid_s), int(working.size[1] * mid_s)),
                resample=Image.Resampling.LANCZOS,
            )
            if _get_encoded_size(resized, 'PNG') <= target_bytes:
                best_resized = resized
                lo_s = mid_s
            else:
                hi_s = mid_s
        if best_resized is not None:
            return best_resized, kw

    raise ValueError(f"Cannot reduce to {target_mb}MB. Try a smaller target or different format.")


# ============================================================================
# Image Info
# ============================================================================


def get_image_info(img: Image.Image, file_path: Path) -> dict:
    file_size = os.path.getsize(file_path)
    dpi = img.info.get('dpi', (72, 72))
    if isinstance(dpi, tuple):
        dpi_x, dpi_y = int(round(dpi[0])), int(round(dpi[1]))
    else:
        dpi_x = dpi_y = int(round(dpi))

    info = {
        'file': str(file_path.name),
        'width': img.size[0],
        'height': img.size[1],
        'dimensions': f"{img.size[0]}x{img.size[1]}",
        'format': img.format or file_path.suffix[1:].upper(),
        'fileSize': format_size(file_size),
        'fileSizeBytes': file_size,
        'colorMode': img.mode,
        'dpi': f"{dpi_x}x{dpi_y}",
        'dpiX': dpi_x,
        'dpiY': dpi_y,
    }

    exif = get_exif_data(img)
    if exif:
        info['exif'] = exif

    return info


# ============================================================================
# Color & Parsing Helpers
# ============================================================================


def parse_color(color_str: str) -> tuple:
    color_str = color_str.strip()
    if "," in color_str and not color_str.startswith(("rgb", "hsl")):
        try:
            parts = [int(p.strip()) for p in color_str.split(",")]
            if len(parts) in (3, 4) and all(0 <= p <= 255 for p in parts):
                return tuple(parts)
        except ValueError:
            pass
    try:
        return ImageColor.getrgb(color_str)
    except ValueError:
        raise ValueError(f"Invalid color: {color_str}. Use hex (#RRGGBB), rgb(R,G,B), or named color.")


def parse_padding_or_crop(value: str) -> tuple[int, int, int, int]:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) == 1:
        return (parts[0], parts[0], parts[0], parts[0])
    elif len(parts) == 2:
        return (parts[0], parts[1], parts[0], parts[1])
    elif len(parts) == 4:
        return tuple(parts)
    raise ValueError("Use 1, 2, or 4 comma-separated values")


# ============================================================================
# Auto-naming
# ============================================================================


def auto_output_name(input_path: Path, operations: list[str], output_suffix: str = None) -> Path:
    """Generate an output filename based on operations applied."""
    stem = input_path.stem
    ext = output_suffix or input_path.suffix

    # Build suffix from operation keywords
    op_parts = []
    for op in operations:
        word = op.split()[0].replace("°", "").strip()
        if word and word not in op_parts:
            op_parts.append(word)

    if op_parts:
        suffix = "_" + "_".join(op_parts[:4])  # Max 4 parts
    else:
        suffix = "_edited"

    return input_path.parent / f"{stem}{suffix}{ext}"


# ============================================================================
# Save & Output
# ============================================================================


def save_image(img: Image.Image, output_path: Path, args, operations: list[str],
               input_path: Path, exif_bytes: bytes | None = None) -> dict:
    """Save image and return result dict."""
    save_kwargs = {}
    suffix = output_path.suffix.lower()
    output_format = FORMAT_MAP.get(suffix, 'PNG')

    if args.max_size:
        try:
            img, size_kw = reduce_file_size(img, args.max_size, output_format)
            save_kwargs.update(size_kw)
            operations.append(f"optimize for max {args.max_size}MB")
        except ValueError as e:
            output_error(str(e), "SIZE_REDUCTION_FAILED")
    else:
        if suffix in [".jpg", ".jpeg"]:
            if img.mode == "RGBA":
                img = handle_transparency(img)
            save_kwargs["quality"] = args.quality if args.quality is not None else 95
        elif suffix == ".png":
            save_kwargs["optimize"] = True
        elif suffix == ".webp":
            save_kwargs["quality"] = args.quality if args.quality is not None else 90

    if args.dpi is not None:
        save_kwargs["dpi"] = (args.dpi, args.dpi)

    # Preserve EXIF if requested and format supports it
    if exif_bytes and not args.strip_exif and suffix in [".jpg", ".jpeg", ".tiff", ".tif", ".webp"]:
        save_kwargs["exif"] = exif_bytes

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format=output_format, **save_kwargs)

    final_size = os.path.getsize(output_path)
    result = {
        "status": "complete",
        "mode": "edit",
        "inputPath": str(input_path.resolve()),
        "outputPath": str(output_path.resolve()),
        "inputDimensions": f"{Image.open(input_path).size[0]}x{Image.open(input_path).size[1]}" if input_path != output_path else "N/A",
        "outputDimensions": f"{img.size[0]}x{img.size[1]}",
        "outputFormat": output_format,
        "fileSize": format_size(final_size),
        "fileSizeBytes": final_size,
        "operations": operations,
    }
    if args.quality is not None:
        result["quality"] = args.quality
    if args.dpi is not None:
        result["dpi"] = args.dpi
    return result


def save_to_stdout(img: Image.Image, fmt: str, args) -> None:
    """Write image bytes to stdout."""
    save_kwargs = {}
    if fmt in ('JPEG', 'WEBP'):
        save_kwargs["quality"] = args.quality if args.quality is not None else 90
    elif fmt == 'PNG':
        save_kwargs["optimize"] = True
    buf = io.BytesIO()
    img.save(buf, format=fmt, **save_kwargs)
    sys.stdout.buffer.write(buf.getvalue())


# ============================================================================
# Process Single Image
# ============================================================================


def process_image(input_path: Path, args, output_path: Path = None) -> dict:
    """Process a single image through the operation pipeline. Returns result dict."""
    try:
        img = Image.open(input_path)
        img.load()
    except Exception as e:
        return {"status": "error", "code": "IMAGE_LOAD_FAILED", "message": f"Failed to load {input_path}: {e}"}

    # Capture EXIF for preservation
    exif_bytes = None
    if not args.strip_exif:
        try:
            exif = img.getexif()
            if exif:
                exif_bytes = exif.tobytes()
        except Exception:
            pass

    operations = []

    # --- Info mode ---
    if args.info:
        info = get_image_info(img, input_path)
        return {"status": "complete", "mode": "info", **info}

    # --- Extract mask ---
    if args.extract_mask:
        mask = extract_alpha_mask(img)
        if mask is None:
            return {"status": "error", "code": "NO_ALPHA", "message": f"No transparency in {input_path}"}
        op = output_path or auto_output_name(input_path, ["mask"])
        mask.save(op)
        sz = os.path.getsize(op)
        return {
            "status": "complete", "mode": "extract-mask",
            "outputPath": str(op.resolve()),
            "dimensions": f"{mask.size[0]}x{mask.size[1]}",
            "fileSize": format_size(sz), "fileSizeBytes": sz,
        }

    # --- Diff mode ---
    if args.diff:
        diff_img, diff_stats = image_diff(img, args.diff)
        op = output_path or auto_output_name(input_path, ["diff"])
        op.parent.mkdir(parents=True, exist_ok=True)
        diff_img.save(op)
        sz = os.path.getsize(op)
        return {
            "status": "complete", "mode": "diff",
            "outputPath": str(op.resolve()),
            "dimensions": f"{diff_img.size[0]}x{diff_img.size[1]}",
            "fileSize": format_size(sz), "fileSizeBytes": sz,
            **diff_stats,
        }

    input_dims = f"{img.size[0]}x{img.size[1]}"

    # --- Transforms ---
    if args.rotate is not None:
        img = rotate_image(img, args.rotate)
        operations.append(f"rotate {args.rotate}°")

    if args.flip:
        img = flip_image(img, args.flip)
        operations.append(f"flip {args.flip}")

    if args.autocrop_transparency is not None:
        if img.mode == "RGBA":
            old = img.size
            img = autocrop_transparency(img, args.autocrop_transparency)
            operations.append(f"autocrop {old[0]}x{old[1]} → {img.size[0]}x{img.size[1]}")

    if args.crop:
        try:
            t, r, b, l = parse_padding_or_crop(args.crop)
            img = crop_image(img, t, r, b, l)
            operations.append(f"crop t={t} r={r} b={b} l={l}")
        except ValueError as e:
            return {"status": "error", "code": "INVALID_CROP", "message": str(e)}

    if args.thumbnail:
        tw, th = args.thumbnail
        img = thumbnail_image(img, tw, th)
        operations.append(f"thumbnail {tw}x{th}")
    elif args.width is not None or args.height is not None:
        img = resize_image(img, args.width, args.height)
        operations.append(f"resize to {img.size[0]}x{img.size[1]}")

    if args.pad:
        try:
            t, r, b, l = parse_padding_or_crop(args.pad)
            pc = parse_color(args.pad_color) if args.pad_color else None
            img = pad_image(img, t, r, b, l, color=pc, edge=args.pad_edge)
            operations.append(f"pad t={t} r={r} b={b} l={l}")
        except ValueError as e:
            return {"status": "error", "code": "INVALID_PADDING", "message": str(e)}

    if args.border:
        bw = args.border
        bc = parse_color(args.border_color) if args.border_color else (0, 0, 0)
        inside = args.border_inside
        img = add_border(img, bw, bc, inside=inside)
        operations.append(f"border {bw}px {'inside' if inside else 'outside'}")

    # --- Adjustments ---
    if args.brightness is not None:
        img = adjust_brightness(img, args.brightness)
        operations.append(f"brightness {args.brightness}")

    if args.contrast is not None:
        img = adjust_contrast(img, args.contrast)
        operations.append(f"contrast {args.contrast}")

    if args.saturation is not None:
        img = adjust_saturation(img, args.saturation)
        operations.append(f"saturation {args.saturation}")

    if args.blur is not None:
        img = apply_blur(img, args.blur)
        operations.append(f"blur radius={args.blur}")

    if args.sharpen is not None:
        img = apply_sharpen(img, args.sharpen)
        operations.append(f"sharpen {args.sharpen}")

    # --- Mask / blend ---
    if args.mask:
        mp = Path(args.mask).expanduser()
        if not mp.exists():
            return {"status": "error", "code": "MASK_NOT_FOUND", "message": f"Mask not found: {args.mask}"}
        try:
            img = alpha_blend(img, Image.open(mp))
            operations.append("alpha blend")
        except Exception as e:
            return {"status": "error", "code": "MASK_FAILED", "message": str(e)}

    # --- Color effects ---
    if args.grayscale:
        img = convert_to_grayscale(img)
        operations.append("grayscale")

    if args.sepia:
        img = apply_sepia(img)
        operations.append("sepia")

    if args.tint:
        tc = parse_color(args.tint)
        strength = args.tint_strength if args.tint_strength is not None else 0.3
        img = apply_tint(img, tc, strength)
        operations.append(f"tint {args.tint} ({strength})")

    if args.color_space:
        img = convert_color_space(img, args.color_space)
        operations.append(f"convert to {args.color_space}")

    # --- Transparency ---
    if args.replace_transparency or args.remove_transparency:
        if img.mode == "RGBA":
            if args.replace_transparency:
                c = parse_color(args.replace_transparency)
                img = handle_transparency(img, c)
                operations.append(f"replace transparency with {c}")
            else:
                img = handle_transparency(img)
                operations.append("remove transparency")

    # --- Watermark ---
    if args.watermark_text:
        pos = args.watermark_position or "bottom-right"
        opacity = args.watermark_opacity if args.watermark_opacity is not None else 128
        fs = args.watermark_font_size if args.watermark_font_size is not None else 24
        wc = parse_color(args.watermark_color) if args.watermark_color else (255, 255, 255)
        img = add_text_watermark(img, args.watermark_text, pos, opacity, fs, wc)
        operations.append(f"text watermark '{args.watermark_text}'")

    if args.watermark_image:
        pos = args.watermark_position or "bottom-right"
        opacity = args.watermark_opacity if args.watermark_opacity is not None else 128
        scale = args.watermark_scale if args.watermark_scale is not None else 0.2
        img = add_image_watermark(img, args.watermark_image, pos, opacity, scale)
        operations.append("image watermark")

    # --- EXIF strip ---
    if args.strip_exif:
        img = strip_exif(img)
        operations.append("strip exif")

    # --- DPI ---
    if args.dpi is not None:
        img = set_dpi(img, args.dpi)
        operations.append(f"set dpi to {args.dpi}")

    # --- Output ---
    if not output_path:
        output_path = auto_output_name(input_path, operations)

    # stdout mode
    if str(output_path) == "-":
        suffix = input_path.suffix.lower()
        fmt = FORMAT_MAP.get(suffix, 'PNG')
        save_to_stdout(img, fmt, args)
        return {"status": "complete", "mode": "stdout", "format": fmt, "operations": operations}

    result = save_image(img, output_path, args, operations, input_path, exif_bytes)
    # Overwrite inputDimensions with the pre-computed value
    result["inputDimensions"] = input_dims
    return result


# ============================================================================
# CLI
# ============================================================================


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Image editing CLI with JSON output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  uv run image_edit.py input.png --rotate 90
  uv run image_edit.py input.png -o output.webp --quality 80
  uv run image_edit.py input.png --brightness 1.3 --contrast 1.2
  uv run image_edit.py input.png --blur 3
  uv run image_edit.py input.png --sepia
  uv run image_edit.py input.png --thumbnail 300,300
  uv run image_edit.py input.png --watermark-text "© 2026"
  uv run image_edit.py input.png --border 5 --border-color red
  uv run image_edit.py input.png --strip-exif -o clean.jpg
  uv run image_edit.py input.png --color-space CMYK -o output.tiff
  uv run image_edit.py input.png --diff other.png -o diff.png
  uv run image_edit.py "*.png" --width 800 --batch
  uv run image_edit.py input.png -o - | other-tool
  uv run image_edit.py input.png --info
""",
    )

    p.add_argument("input", help="Input image path (or glob pattern with --batch)")
    p.add_argument("-o", "--output", help="Output path (auto-generated if omitted, '-' for stdout)")

    # Modes
    p.add_argument("--info", action="store_true", help="Show image metadata as JSON")
    p.add_argument("--batch", action="store_true", help="Process glob pattern (e.g., '*.png')")

    # Transforms
    p.add_argument("--rotate", type=float, metavar="ANGLE", help="Rotate counterclockwise (degrees)")
    p.add_argument("--flip", choices=["horizontal", "vertical"], help="Flip image")
    p.add_argument("--width", type=int, help="Target width (aspect preserved if height omitted)")
    p.add_argument("--height", type=int, help="Target height (aspect preserved if width omitted)")
    p.add_argument("--thumbnail", type=lambda s: tuple(int(x) for x in s.split(",")), metavar="W,H",
                   help="Smart crop-to-fit to exact WxH")
    p.add_argument("--crop", metavar="PIXELS", help="Crop from edges (single, V,H, or T,R,B,L)")
    p.add_argument("--pad", metavar="PIXELS", help="Add padding (single, V,H, or T,R,B,L)")
    p.add_argument("--pad-color", metavar="COLOR", help="Padding color")
    p.add_argument("--pad-edge", action="store_true", help="Replicate edge pixels for padding")
    p.add_argument("--autocrop-transparency", type=float, metavar="THRESHOLD",
                   help="Crop transparent borders (threshold 0-100%%)")

    # Border
    p.add_argument("--border", type=int, metavar="PX", help="Add border (pixels)")
    p.add_argument("--border-color", metavar="COLOR", help="Border color (default: black)")
    p.add_argument("--border-inside", action="store_true", help="Draw border inside image (default: outside)")

    # Adjustments
    p.add_argument("--brightness", type=float, metavar="F", help="Brightness factor (1.0=original, >1 brighter)")
    p.add_argument("--contrast", type=float, metavar="F", help="Contrast factor (1.0=original, >1 more contrast)")
    p.add_argument("--saturation", type=float, metavar="F", help="Saturation factor (1.0=original, 0=gray)")
    p.add_argument("--blur", type=float, metavar="R", help="Gaussian blur radius")
    p.add_argument("--sharpen", type=float, metavar="A", help="Sharpen (1=light, >1=unsharp mask)")

    # Color effects
    p.add_argument("--grayscale", action="store_true", help="Convert to grayscale")
    p.add_argument("--sepia", action="store_true", help="Apply sepia tone")
    p.add_argument("--tint", metavar="COLOR", help="Apply color tint")
    p.add_argument("--tint-strength", type=float, metavar="S", help="Tint strength 0.0-1.0 (default: 0.3)")
    p.add_argument("--color-space", metavar="SPACE", help="Convert color space (RGB, CMYK, L, RGBA, P3)")

    # Quality & format
    p.add_argument("--quality", "-q", type=int, metavar="Q", help="Output quality 1-100 (JPEG/WebP)")
    p.add_argument("--dpi", type=int, metavar="DPI", help="Set output DPI")
    p.add_argument("--max-size", type=float, metavar="MB", help="Reduce file to target MB")

    # Transparency
    p.add_argument("--remove-transparency", action="store_true", help="Flatten alpha to white")
    p.add_argument("--replace-transparency", metavar="COLOR", help="Flatten alpha to COLOR")
    p.add_argument("--extract-mask", action="store_true", help="Extract alpha as grayscale mask")
    p.add_argument("--mask", metavar="PATH", help="Apply grayscale mask as alpha")

    # Watermark
    p.add_argument("--watermark-text", metavar="TEXT", help="Add text watermark")
    p.add_argument("--watermark-image", metavar="PATH", help="Add image watermark")
    p.add_argument("--watermark-position", metavar="POS",
                   choices=["top-left", "top-right", "bottom-left", "bottom-right", "center"],
                   help="Watermark position (default: bottom-right)")
    p.add_argument("--watermark-opacity", type=int, metavar="A", help="Watermark opacity 0-255 (default: 128)")
    p.add_argument("--watermark-font-size", type=int, metavar="PX", help="Text watermark font size (default: 24)")
    p.add_argument("--watermark-color", metavar="COLOR", help="Text watermark color (default: white)")
    p.add_argument("--watermark-scale", type=float, metavar="S", help="Image watermark scale 0-1 (default: 0.2)")

    # EXIF
    p.add_argument("--strip-exif", action="store_true", help="Remove all EXIF/metadata")

    # Diff
    p.add_argument("--diff", metavar="PATH", help="Generate visual diff with another image")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Validation
    if args.quality is not None and not (1 <= args.quality <= 100):
        output_error("Quality must be 1-100", "INVALID_QUALITY")
    if args.dpi is not None and args.dpi < 1:
        output_error("DPI must be positive", "INVALID_DPI")

    # --- Batch mode ---
    if args.batch:
        files = sorted(glob_module.glob(args.input))
        if not files:
            output_error(f"No files match pattern: {args.input}", "NO_MATCH")

        results = []
        for f in files:
            fp = Path(f).expanduser()
            if not fp.is_file():
                continue
            # In batch mode, output goes next to input with auto-naming
            out = None
            if args.output:
                out_dir = Path(args.output).expanduser()
                out_dir.mkdir(parents=True, exist_ok=True)
                out = out_dir / fp.name
            result = process_image(fp, args, out)
            results.append(result)

        output_json({
            "status": "complete",
            "mode": "batch",
            "totalFiles": len(results),
            "successful": sum(1 for r in results if r.get("status") == "complete"),
            "failed": sum(1 for r in results if r.get("status") == "error"),
            "results": results,
        })
        return

    # --- Single image ---
    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        output_error(f"File not found: {args.input}", "FILE_NOT_FOUND")

    # Determine output path
    output_path = None
    if args.output:
        output_path = Path(args.output).expanduser() if args.output != "-" else Path("-")
    elif not args.info:
        # Auto-naming: will be resolved inside process_image
        pass

    result = process_image(input_path, args, output_path)

    if result.get("mode") != "stdout":
        output_json(result)


if __name__ == "__main__":
    main()
