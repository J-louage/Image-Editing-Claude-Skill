---
name: image-editing
description: "Image manipulation tool for resizing, rotation, flipping, cropping, padding, border, thumbnail, brightness/contrast/saturation, blur/sharpen, sepia/tint, watermark (text & image), format conversion (JPEG/PNG/WebP/TIFF/HEIC), transparency operations, grayscale, color space conversion, EXIF handling, image diff, batch processing, DPI control, quality control, and file size optimization. Use when users need to transform, convert, or optimize images. Trigger phrases: resize image, crop image, convert to webp, reduce file size, rotate image, flip image, remove background, set dpi, add watermark, blur image, sharpen, sepia, thumbnail, batch resize, /image-editing."
argument-hint: "[input] [options]"
---

# Image Editing

Image manipulation tool supporting transforms, adjustments, effects, watermarks, batch processing, format conversions, transparency operations, quality/DPI control, and optimization. All output is structured JSON.

## Tool Location

The editing CLI is at: `${SKILL_DIR}/scripts/image_edit.py`

Run with: `uv run "${SKILL_DIR}/scripts/image_edit.py" INPUT [OPTIONS]`

## Prerequisites

- **uv** installed (`brew install uv`)
- Dependencies (`pillow`, `pillow-heif`, `numpy`) are auto-managed by uv

## Interactive Flow

### 1. Parse Arguments

Check what the user provided via `$ARGUMENTS`:
- Input image path (or glob pattern with `--batch`)
- `--output` / `-o` (output path; omit for auto-naming, `--output=-` for stdout)
- Operation flags (see sections below)
- `--quality` (1-100, JPEG/WebP only)
- `--dpi` (positive integer)
- `--max-size` (target file size in MB)
- `--info` (metadata query, no output needed)
- `--batch` (process multiple files via glob pattern)

### 2. Gather Missing Information

If **input path** is missing, ask:
> Which image would you like to edit? Provide the file path.

If **output path** is missing (and not using --info), the script auto-generates a name:
```
input_op1_op2.ext
```
For example: `photo.png` → `photo_rotate_sepia.png`

**The script always uses a different output filename than the input** to avoid overwriting the original.

### 3. Choose Operations

Based on the user's request, select the appropriate flags:

**Transforms:**
- `--rotate ANGLE` — Rotate counterclockwise (90, 180, 270, or any angle)
- `--flip horizontal|vertical` — Mirror the image
- `--width W` / `--height H` — Resize (aspect ratio preserved if only one given)
- `--thumbnail W,H` — Smart crop-to-fit to exact dimensions
- `--crop PIXELS` — Crop from edges (single, V,H, or T,R,B,L)
- `--pad PIXELS` — Add padding (single, V,H, or T,R,B,L)
- `--border PX` — Add border around image

**Adjustments:**
- `--brightness F` — Brightness factor (1.0=original, >1 brighter, <1 darker)
- `--contrast F` — Contrast factor (1.0=original, >1 more contrast)
- `--saturation F` — Saturation factor (1.0=original, 0=gray, >1 vivid)
- `--blur R` — Gaussian blur with radius R
- `--sharpen A` — Sharpen (1=light, >1=unsharp mask)

**Color Effects:**
- `--grayscale` — Convert to single-channel grayscale
- `--sepia` — Apply sepia tone
- `--tint COLOR` — Apply color tint overlay
- `--tint-strength S` — Tint strength 0.0-1.0 (default: 0.3)
- `--color-space SPACE` — Convert color space (RGB, CMYK, L, RGBA, P3)

**Watermark:**
- `--watermark-text TEXT` — Add text watermark
- `--watermark-image PATH` — Add image watermark
- `--watermark-position POS` — Position: top-left, top-right, bottom-left, bottom-right, center
- `--watermark-opacity A` — Opacity 0-255 (default: 128)
- `--watermark-font-size PX` — Font size for text watermark (default: 24)
- `--watermark-color COLOR` — Color for text watermark (default: white)
- `--watermark-scale S` — Scale for image watermark 0-1 (default: 0.2)

**Quality & Format:**
- `--quality Q` — Output quality 1-100 (JPEG/WebP; default: JPEG=95, WebP=90)
- `--dpi DPI` — Set output DPI (72=screen, 150=web, 300=print)
- `--max-size MB` — Reduce file size to target (binary search optimization)
- Output format is determined by the output file extension

**Transparency:**
- `--remove-transparency` — Flatten alpha to white background
- `--replace-transparency COLOR` — Flatten alpha to specified color
- `--extract-mask` — Save alpha channel as grayscale mask
- `--mask MASK_PATH` — Apply grayscale mask as alpha channel
- `--autocrop-transparency THRESHOLD` — Trim transparent borders (0-100%)

**Border:**
- `--border PX` — Add border in pixels
- `--border-color COLOR` — Border color (default: black)
- `--border-inside` — Draw border inside image instead of expanding canvas

**EXIF:**
- `--strip-exif` — Remove all EXIF/metadata from output
- EXIF is preserved by default for formats that support it (JPEG, TIFF, WebP)

**Comparison:**
- `--diff PATH` — Generate visual diff with another image

**Batch:**
- `--batch` — Process glob pattern (e.g., `"*.png"`)
- With `--batch`, `-o` specifies an output directory

**Padding Helpers:**
- `--pad-color COLOR` — Set padding color (with --pad)
- `--pad-edge` — Replicate edge pixels for padding (with --pad)

### 4. Execute

Run the command:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" INPUT_PATH \
  [-o OUTPUT_PATH] \
  [--rotate ANGLE] \
  [--flip horizontal|vertical] \
  [--width W] [--height H] \
  [--thumbnail W,H] \
  [--crop PIXELS] \
  [--pad PIXELS] [--pad-color COLOR] [--pad-edge] \
  [--border PX] [--border-color COLOR] [--border-inside] \
  [--brightness F] [--contrast F] [--saturation F] \
  [--blur R] [--sharpen A] \
  [--grayscale] [--sepia] \
  [--tint COLOR] [--tint-strength S] \
  [--color-space SPACE] \
  [--watermark-text TEXT] [--watermark-image PATH] \
  [--watermark-position POS] [--watermark-opacity A] \
  [--watermark-font-size PX] [--watermark-color COLOR] \
  [--watermark-scale S] \
  [--quality Q] \
  [--dpi DPI] \
  [--max-size MB] \
  [--remove-transparency | --replace-transparency COLOR] \
  [--mask MASK_PATH] \
  [--autocrop-transparency THRESHOLD] \
  [--extract-mask] \
  [--strip-exif] \
  [--diff PATH] \
  [--batch] \
  [--info]
```

### 5. Report Results

The script outputs JSON with:
- `status`: "complete" or "error"
- `outputPath`: Full path to saved file
- `outputDimensions`: Final width x height
- `fileSize`: Human-readable file size
- `operations`: List of operations applied
- `quality` and `dpi` if set

Report the output path and key details to the user. Do NOT read the image back.

## Image Info

Query image metadata without editing:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" INPUT_PATH --info
```

Returns JSON with dimensions, format, file size, color mode, DPI, and EXIF data (if present).

## Operation Order

Operations apply in this fixed order regardless of flag order:
rotate → flip → autocrop → crop → thumbnail/resize → pad → border → brightness → contrast → saturation → blur → sharpen → mask → grayscale → sepia → tint → color-space → transparency → watermark → strip-exif → dpi

## Combining Operations

Multiple operations can be combined in a single command:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" input.png -o output.jpg \
  --rotate 90 \
  --width 800 \
  --brightness 1.2 --contrast 1.1 \
  --border 3 --border-color coral \
  --sepia \
  --quality 85 \
  --dpi 150
```

## Batch Processing

Process multiple files with a glob pattern:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" "*.png" --width 800 --batch -o /output/dir
```

In batch mode:
- The input is a glob pattern (must be quoted)
- `-o` specifies an output directory (files keep their original names)
- If `-o` is omitted, auto-naming is used per file
- Returns JSON with `totalFiles`, `successful`, `failed`, and per-file `results`

## Thumbnail Generation

Create exact-size thumbnails with smart crop-to-fit:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" input.png --thumbnail 300,300 -o thumb.png
```

The image is center-cropped to match the target aspect ratio, then resized to exact dimensions.

## Watermarks

### Text Watermark
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" input.png \
  --watermark-text "© 2026" \
  --watermark-position center \
  --watermark-opacity 180 \
  --watermark-font-size 48 \
  --watermark-color red \
  -o watermarked.png
```

### Image Watermark
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" input.png \
  --watermark-image logo.png \
  --watermark-position bottom-right \
  --watermark-scale 0.15 \
  --watermark-opacity 200 \
  -o watermarked.png
```

## Image Comparison

Generate a visual diff between two images:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" image1.png --diff image2.png -o diff.png
```

Returns diff statistics: `totalPixels`, `changedPixels`, `changePercent`, `meanDifference`.

## Format Conversion

Convert by specifying the output extension:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" input.png -o output.webp
uv run "${SKILL_DIR}/scripts/image_edit.py" input.heic -o output.jpg
```

Supported: JPEG (.jpg/.jpeg), PNG (.png), WebP (.webp), TIFF (.tiff/.tif), HEIC/HEIF (.heic/.heif)

## Auto-Naming

When `-o` is omitted, the output filename is auto-generated from operations:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" photo.png --rotate 90 --sepia
# → photo_rotate_sepia.png
```

## Stdout Output

Pipe image data to another tool:
```bash
uv run "${SKILL_DIR}/scripts/image_edit.py" input.png --width 100 --output=- | other-tool
```

## Color Formats

| Format | Examples |
|--------|----------|
| Named | `red`, `blue`, `coral`, `darkslategray` (140+ CSS colors) |
| Hex | `#RGB`, `#RRGGBB`, `#RRGGBBAA` |
| RGB | `255,128,0` or `rgb(255,128,0)` |
| HSL | `hsl(120,100%,50%)` |

## Quality Guide

| Use Case | Format | Quality | DPI |
|----------|--------|---------|-----|
| Web/screen | WebP | 80-85 | 72 |
| Social media | JPEG | 85-90 | 72 |
| Print (standard) | JPEG/PNG | 95 | 150 |
| Print (high quality) | TIFF/PNG | 100 | 300 |
| Thumbnail | WebP | 70-75 | 72 |
| Archive | PNG | — | original |
