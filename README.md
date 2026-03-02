# Image Editing Skill

A comprehensive image manipulation CLI tool for Claude Code. Supports transforms, adjustments, effects, watermarks, batch processing, format conversions, transparency operations, and optimization — all with structured JSON output.

## Installation

1. Install [uv](https://docs.astral.sh/uv/):
   ```bash
   brew install uv
   ```

2. Copy `.claude/skills/image-editing/` into your project's `.claude/skills/` directory.

3. Dependencies (`pillow`, `pillow-heif`, `numpy`) are auto-managed by uv — no manual install needed.

## Usage

```bash
uv run .claude/skills/image-editing/scripts/image_edit.py INPUT [OPTIONS]
```

Or invoke via Claude Code:
```
/image-editing photo.png --width 800
```

## Examples

### Basic Operations

```bash
# Resize (aspect ratio preserved)
uv run image_edit.py photo.png --width 800 -o resized.png

# Rotate 90° counterclockwise
uv run image_edit.py photo.png --rotate 90 -o rotated.png

# Flip horizontal
uv run image_edit.py photo.png --flip horizontal -o flipped.png

# Crop 50px from all edges
uv run image_edit.py photo.png --crop 50 -o cropped.png

# Add 20px white padding
uv run image_edit.py photo.png --pad 20 --pad-color white -o padded.png
```

### Adjustments

```bash
# Brighten image
uv run image_edit.py photo.png --brightness 1.3 -o bright.png

# Increase contrast
uv run image_edit.py photo.png --contrast 1.4 -o contrast.png

# Desaturate (0 = grayscale, 1 = original, >1 = vivid)
uv run image_edit.py photo.png --saturation 0.5 -o muted.png

# Gaussian blur
uv run image_edit.py photo.png --blur 3 -o blurred.png

# Sharpen (1 = light, >1 = stronger unsharp mask)
uv run image_edit.py photo.png --sharpen 2 -o sharp.png
```

### Color Effects

```bash
# Sepia tone
uv run image_edit.py photo.png --sepia -o sepia.png

# Blue tint at 30% strength
uv run image_edit.py photo.png --tint blue --tint-strength 0.3 -o tinted.png

# Convert to grayscale
uv run image_edit.py photo.png --grayscale -o gray.png

# Convert color space to CMYK (for print)
uv run image_edit.py photo.png --color-space CMYK -o print.tiff
```

### Borders

```bash
# 5px red border (expands canvas)
uv run image_edit.py photo.png --border 5 --border-color red -o bordered.png

# 10px border drawn inside the image
uv run image_edit.py photo.png --border 10 --border-color blue --border-inside -o framed.png
```

### Thumbnails

```bash
# Smart crop-to-fit: centers and crops to exact 300x300
uv run image_edit.py photo.png --thumbnail 300,300 -o thumb.png
```

### Watermarks

```bash
# Text watermark
uv run image_edit.py photo.png \
  --watermark-text "© 2026" \
  --watermark-position bottom-right \
  --watermark-opacity 180 \
  --watermark-font-size 36 \
  --watermark-color white \
  -o watermarked.png

# Image watermark (logo overlay)
uv run image_edit.py photo.png \
  --watermark-image logo.png \
  --watermark-position center \
  --watermark-scale 0.15 \
  --watermark-opacity 200 \
  -o branded.png
```

### Format Conversion

```bash
# PNG to WebP
uv run image_edit.py photo.png -o photo.webp --quality 80

# HEIC to JPEG
uv run image_edit.py photo.heic -o photo.jpg --quality 90

# PNG to TIFF for print
uv run image_edit.py photo.png -o photo.tiff --dpi 300
```

### Batch Processing

```bash
# Resize all PNGs to 800px wide
uv run image_edit.py "*.png" --width 800 --batch -o /output/dir

# Convert all JPEGs to WebP
uv run image_edit.py "photos/*.jpg" --batch -o /output/webp
# (rename manually or use auto-naming by omitting -o)

# Apply sepia to all images
uv run image_edit.py "*.png" --sepia --batch
```

### Image Comparison

```bash
# Generate visual diff between two images
uv run image_edit.py original.png --diff modified.png -o diff.png
```

### EXIF Handling

```bash
# Strip all metadata
uv run image_edit.py photo.jpg --strip-exif -o clean.jpg

# View image info including EXIF
uv run image_edit.py photo.jpg --info
```

### Transparency

```bash
# Remove transparency (white background)
uv run image_edit.py icon.png --remove-transparency -o icon_flat.png

# Replace transparency with custom color
uv run image_edit.py icon.png --replace-transparency "#f0f0f0" -o icon_gray.png

# Extract alpha channel as mask
uv run image_edit.py icon.png --extract-mask -o mask.png

# Apply mask as alpha channel
uv run image_edit.py photo.png --mask mask.png -o masked.png

# Auto-crop transparent borders
uv run image_edit.py icon.png --autocrop-transparency 5 -o trimmed.png
```

### File Size Optimization

```bash
# Reduce to target file size
uv run image_edit.py photo.png -o optimized.jpg --max-size 0.5
```

### Combined Operations

```bash
# Multiple operations in one command
uv run image_edit.py photo.png -o final.jpg \
  --rotate 90 \
  --width 800 \
  --brightness 1.2 --contrast 1.1 \
  --border 3 --border-color coral \
  --sepia \
  --watermark-text "Draft" --watermark-opacity 100 \
  --quality 85 --dpi 150
```

### Auto-Naming

```bash
# Omit -o for automatic output naming
uv run image_edit.py photo.png --rotate 90 --sepia
# → photo_rotate_sepia.png
```

### Stdout Output

```bash
# Pipe image to another tool
uv run image_edit.py input.png --width 100 --output=- | other-tool
```

## Options Reference

| Option | Description | Default |
|--------|-------------|---------|
| `-o`, `--output` | Output path (auto-named if omitted, `-` for stdout) | auto |
| `--info` | Show image metadata as JSON | — |
| `--batch` | Process glob pattern | — |
| **Transforms** | | |
| `--rotate ANGLE` | Rotate counterclockwise (degrees) | — |
| `--flip` | `horizontal` or `vertical` | — |
| `--width W` | Target width (preserves aspect ratio) | — |
| `--height H` | Target height (preserves aspect ratio) | — |
| `--thumbnail W,H` | Smart crop-to-fit to exact dimensions | — |
| `--crop PIXELS` | Crop from edges | — |
| `--pad PIXELS` | Add padding | — |
| `--pad-color COLOR` | Padding color | white |
| `--pad-edge` | Replicate edge pixels for padding | false |
| `--border PX` | Add border | — |
| `--border-color COLOR` | Border color | black |
| `--border-inside` | Draw border inside image | false |
| **Adjustments** | | |
| `--brightness F` | Brightness factor (1.0 = original) | — |
| `--contrast F` | Contrast factor (1.0 = original) | — |
| `--saturation F` | Saturation factor (1.0 = original) | — |
| `--blur R` | Gaussian blur radius | — |
| `--sharpen A` | Sharpen amount (1 = light) | — |
| **Effects** | | |
| `--grayscale` | Convert to grayscale | — |
| `--sepia` | Apply sepia tone | — |
| `--tint COLOR` | Apply color tint | — |
| `--tint-strength S` | Tint strength (0.0–1.0) | 0.3 |
| `--color-space SPACE` | Convert color space | — |
| **Watermark** | | |
| `--watermark-text TEXT` | Text watermark content | — |
| `--watermark-image PATH` | Image watermark file | — |
| `--watermark-position` | top-left, top-right, bottom-left, bottom-right, center | bottom-right |
| `--watermark-opacity A` | Opacity (0–255) | 128 |
| `--watermark-font-size PX` | Font size | 24 |
| `--watermark-color COLOR` | Text color | white |
| `--watermark-scale S` | Image watermark scale (0–1) | 0.2 |
| **Quality** | | |
| `--quality Q` | Output quality (1–100, JPEG/WebP) | JPEG=95, WebP=90 |
| `--dpi DPI` | Output DPI | original |
| `--max-size MB` | Target file size | — |
| **Transparency** | | |
| `--remove-transparency` | Flatten to white background | — |
| `--replace-transparency COLOR` | Flatten to custom color | — |
| `--extract-mask` | Save alpha as grayscale | — |
| `--mask PATH` | Apply mask as alpha | — |
| `--autocrop-transparency T` | Trim transparent borders (0–100%) | — |
| **Other** | | |
| `--strip-exif` | Remove EXIF/metadata | false |
| `--diff PATH` | Visual diff with another image | — |

## Supported Formats

| Format | Extensions | Read | Write |
|--------|-----------|------|-------|
| JPEG | .jpg, .jpeg | Yes | Yes |
| PNG | .png | Yes | Yes |
| WebP | .webp | Yes | Yes |
| TIFF | .tiff, .tif | Yes | Yes |
| HEIC/HEIF | .heic, .heif | Yes | Yes |

## Operation Order

Operations apply in this fixed order regardless of flag order:

1. rotate
2. flip
3. autocrop transparency
4. crop
5. thumbnail / resize
6. pad
7. border
8. brightness
9. contrast
10. saturation
11. blur
12. sharpen
13. mask (alpha blend)
14. grayscale
15. sepia
16. tint
17. color space
18. transparency (remove/replace)
19. watermark
20. strip EXIF
21. DPI

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

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `uv: command not found` | Install uv: `brew install uv` |
| `No such file or directory` | Check the input path exists |
| `Cannot reduce to X MB` | Try a larger target size or different format |
| HEIC not loading | Ensure `pillow-heif` is available (auto-installed by uv) |
| `-o -` not working | Use `--output=-` instead for stdout pipe |
| Watermark text invisible | Increase `--watermark-font-size` or `--watermark-opacity` |
| CMYK output large | CMYK TIFFs are uncompressed — expected for print workflows |
