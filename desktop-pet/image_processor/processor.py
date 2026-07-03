"""White background removal and image processing — flood-fill aware."""

import sys
from PIL import Image
import numpy as np
import os
from collections import deque


def _resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def _flood_fill_exterior(is_white, feather=35):
    """Find exterior white region connected to image edges via BFS.

    Only white pixels reachable from the image border are considered
    "background". Interior white pixels (eyes, teeth, etc.) surrounded
    by non-white content are preserved.

    Args:
        is_white: (H, W) boolean array — True where pixel is white
        feather: number of pixels to feather at the boundary

    Returns:
        alpha_mask: (H, W) float32 [0..1] — 0=remove, 1=keep
    """
    h, w = is_white.shape
    exterior = np.zeros((h, w), dtype=bool)
    q = deque()

    # Seed: all white edge pixels
    for y in range(h):
        if is_white[y, 0]:
            q.append((y, 0))
            exterior[y, 0] = True
        if w > 1 and is_white[y, w - 1]:
            q.append((y, w - 1))
            exterior[y, w - 1] = True
    for x in range(1, w - 1):
        if is_white[0, x]:
            q.append((0, x))
            exterior[0, x] = True
        if h > 1 and is_white[h - 1, x]:
            q.append((h - 1, x))
            exterior[h - 1, x] = True

    # BFS flood fill through white pixels only
    while q:
        y, x = q.popleft()
        for ny, nx in [(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)]:
            if 0 <= ny < h and 0 <= nx < w:
                if is_white[ny, nx] and not exterior[ny, nx]:
                    exterior[ny, nx] = True
                    q.append((ny, nx))

    # ── Feathering: BFS from exterior boundary inward ──
    # distance[y,x] = min steps from exterior (0 = exterior)
    distance = np.full((h, w), -1, dtype=np.int16)
    q2 = deque()

    # Seed: exterior pixels (distance 0)
    for y in range(h):
        for x in range(w):
            if exterior[y, x]:
                distance[y, x] = 0
                q2.append((y, x))

    # Also seed: non-white border pixels adjacent to exterior
    # (the boundary between exterior and non-exterior)
    # We add all pixels at distance 0 to the queue.
    # Then BFS outward into non-exterior pixels up to feather steps.

    while q2:
        y, x = q2.popleft()
        d = distance[y, x]
        if d >= feather:
            continue
        for ny, nx in [(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)]:
            if 0 <= ny < h and 0 <= nx < w:
                if distance[ny, nx] == -1:
                    distance[ny, nx] = d + 1
                    q2.append((ny, nx))

    # Build alpha mask from distances
    alpha = np.ones((h, w), dtype=np.float32)
    for y in range(h):
        for x in range(w):
            d = distance[y, x]
            if d == -1:
                alpha[y, x] = 1.0  # unreachable → interior → keep
            elif d == 0:
                alpha[y, x] = 0.0  # exterior → remove
            else:
                alpha[y, x] = min(d / feather, 1.0)  # feather band

    return alpha


def remove_white_background(image, threshold=200, feather=None):
    """Remove white background using flood-fill from image edges.

    Only white pixels connected to the image border are removed —
    interior white areas (eyes, teeth, etc.) surrounded by the
    character are preserved.

    Args:
        image: PIL Image (will be converted to RGBA)
        threshold: min(R,G,B) above which pixels are "white" candidates
        feather: edge transition width in pixels, defaults to 255-threshold

    Returns:
        PIL Image in RGBA mode with transparent background
    """
    if feather is None:
        feather = 10  # narrower default feather for flood-fill approach

    img = image.convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    rgb = arr[:, :, :3]
    h, w = arr.shape[:2]

    # Whiteness: min(R,G,B) — all channels must be bright to be "white"
    min_channel = np.min(rgb, axis=2)
    is_white = min_channel > threshold

    # ── Color-based alpha factor (backup: how "non-white" each pixel is) ──
    color_range = max(255 - threshold, 1)
    color_alpha = np.clip((255 - min_channel) / color_range, 0.0, 1.0)

    # ── Erode white mask by 1px to close anti-aliasing bridges ──
    eroded = is_white.copy()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if is_white[y, x]:
                if not (is_white[y - 1, x] and is_white[y + 1, x]
                        and is_white[y, x - 1] and is_white[y, x + 1]):
                    eroded[y, x] = False
    is_white = eroded

    # Flood-fill from edges to find exterior background
    distance_alpha = _flood_fill_exterior(is_white, feather=feather)

    # ── Combine: max of distance-based and color-based alpha ──
    # This preserves interior colored pixels even if they're near
    # the exterior boundary, while properly feathering near-white edges.
    alpha_mask = np.maximum(distance_alpha, color_alpha)
    alpha_mask = np.clip(alpha_mask, 0.0, 1.0)

    # Apply alpha
    arr[:, :, 3] = arr[:, :, 3] * alpha_mask

    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def remove_background_ai(image):
    """Use rembg to remove background with AI.

    Args:
        image: PIL Image

    Returns:
        PIL Image in RGBA mode with transparent background
    """
    try:
        from rembg import remove
        return remove(image)
    except ImportError:
        raise ImportError(
            "rembg is not installed. Install with: pip install rembg onnxruntime"
        )


def crop_to_content(image, padding=5):
    """Crop image to non-transparent content bounds.

    Args:
        image: PIL Image in RGBA mode
        padding: extra pixels around content

    Returns:
        Cropped PIL Image
    """
    arr = np.array(image)
    alpha = arr[:, :, 3]

    # Find non-transparent pixels
    rows = np.any(alpha > 10, axis=1)
    cols = np.any(alpha > 10, axis=0)

    if not rows.any() or not cols.any():
        return image

    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]

    y_min = max(0, y_min - padding)
    y_max = min(image.height, y_max + padding + 1)
    x_min = max(0, x_min - padding)
    x_max = min(image.width, x_max + padding + 1)

    return image.crop((x_min, y_min, x_max, y_max))


def process_image(image_path, threshold=200, use_ai=False, output_size=None):
    """Full image processing pipeline.

    Args:
        image_path: path to input image
        threshold: white threshold (0-255)
        use_ai: if True, use rembg AI instead of threshold
        output_size: optional (width, height) to resize to

    Returns:
        PIL Image in RGBA mode, cropped and processed
    """
    img = Image.open(image_path)

    if use_ai:
        img = remove_background_ai(img)
    else:
        img = remove_white_background(img, threshold=threshold)

    img = crop_to_content(img)

    if output_size:
        img.thumbnail(output_size, Image.LANCZOS)

    return img


def process_and_save(input_path, output_dir, threshold=200, use_ai=False):
    """Process image and save to output directory.

    Args:
        input_path: path to input image
        output_dir: directory to save processed image
        threshold: white threshold
        use_ai: use AI removal

    Returns:
        str: path to saved processed image
    """
    img = process_image(input_path, threshold=threshold, use_ai=use_ai,
                        output_size=(256, 256))

    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.splitext(os.path.basename(input_path))[0]
    # Strip existing _pet suffix to prevent "_pet_pet_pet" stacking
    while basename.endswith('_pet'):
        basename = basename[:-4]
    output_path = os.path.join(output_dir, f"{basename}_pet.png")
    img.save(output_path, "PNG")

    return output_path


def process_bead_image(image_path, output_size=32):
    """Convert a perler bead photo into a pixel-art pet.

    Uses block averaging (LANCZOS resize) to smooth out bead gaps and
    shadows, saturation-aware background detection to separate beads
    from the table/pegboard, and nearest-palette color quantization.

    Args:
        image_path: path to bead photo
        output_size: grid dimension (default 32x32)

    Returns:
        PIL Image in RGBA at output_size*5 pixels, or None on failure
    """
    from ui.bead_editor import BEAD_PALETTE

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return None

    # Step 1: Resize to 4x the target grid, then pick the most
    # saturated pixel in each 4x4 block. This avoids the color
    # washout that happens when averaging bead+background together —
    # bead centers are bright and saturated, gaps are dull.
    block_size = 4
    img_big = img.resize((output_size * block_size, output_size * block_size),
                         Image.LANCZOS)
    big_pixels = img_big.load()

    # Build a 32x32 image where each cell = the most saturated pixel
    # from the corresponding 4x4 block in the 128x128 intermediate.
    img_small = Image.new("RGB", (output_size, output_size))
    small_pixels = img_small.load()
    for y in range(output_size):
        for x in range(output_size):
            best_sat = -1
            best_rgb = (0, 0, 0)
            for dy in range(block_size):
                for dx in range(block_size):
                    r, g, b = big_pixels[x * block_size + dx,
                                          y * block_size + dy]
                    sat = max(r, g, b) - min(r, g, b)
                    if sat > best_sat:
                        best_sat = sat
                        best_rgb = (r, g, b)
            small_pixels[x, y] = best_rgb
    pixels = small_pixels

    # Step 2: Improved background detection using multiple methods
    # Method 1: Collect border pixels for background reference
    border_rgb = []
    for x in range(output_size):
        for dy in (0, 1, output_size - 2, output_size - 1):
            if 0 <= dy < output_size:
                border_rgb.append(pixels[x, dy])
    for y in range(2, output_size - 2):
        for dx in (0, 1, output_size - 2, output_size - 1):
            if 0 <= dx < output_size:
                border_rgb.append(pixels[dx, y])

    # Filter out saturated border pixels (likely bead edges)
    low_sat_border = []
    for r, g, b in border_rgb:
        sat = max(r, g, b) - min(r, g, b)
        if sat < 40:
            low_sat_border.append((r, g, b))

    if len(low_sat_border) >= 4:
        low_sat_border.sort()
        bg_r, bg_g, bg_b = low_sat_border[len(low_sat_border) // 2]
    else:
        border_rgb.sort()
        bg_r, bg_g, bg_b = border_rgb[len(border_rgb) // 2]

    # Step 3: Build palette lookup
    palette_keys = [k for k in BEAD_PALETTE if k != '.']
    palette_lookup = []
    for k in palette_keys:
        c = BEAD_PALETTE[k][1]
        palette_lookup.append((c.red(), c.green(), c.blue()))

    def closest_color(r, g, b):
        best_k = '.'
        best_dist = float('inf')
        for i, (pr, pg, pb) in enumerate(palette_lookup):
            dr, dg, db = r - pr, g - pg, b - pb
            dist = dr * dr + dg * dg + db * db
            if dist < best_dist:
                best_dist = dist
                best_k = palette_keys[i]
        return best_k

    def rgb_dist(r1, g1, b1, r2, g2, b2):
        return (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2

    # Step 4: Build char grid. A cell is transparent only if it is BOTH
    # desaturated (low color) AND close to the background reference.
    # This preserves bead colors even when they've been slightly blended
    # with background by the resize.
    BG_DIST_THRESHOLD = 3000   # squared RGB distance (~55 per channel)
    SATURATION_THRESHOLD = 35  # max-min must exceed this to be a bead

    grid = []
    for y in range(output_size):
        row_chars = []
        for x in range(output_size):
            r, g, b = pixels[x, y]
            sat = max(r, g, b) - min(r, g, b)
            near_bg = rgb_dist(r, g, b, bg_r, bg_g, bg_b) < BG_DIST_THRESHOLD
            if near_bg and sat < SATURATION_THRESHOLD:
                row_chars.append('.')
            else:
                row_chars.append(closest_color(r, g, b))
        grid.append(''.join(row_chars))

    # Step 5: Post-processing - remove isolated pixels (noise)
    def is_isolated(x, y, grid, output_size):
        """Check if a pixel is isolated (no neighbors of same color)."""
        if grid[y][x] == '.':
            return False
        color = grid[y][x]
        neighbors = 0
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < output_size and 0 <= ny < output_size:
                if grid[ny][nx] == color:
                    neighbors += 1
        return neighbors == 0

    # Clean up isolated pixels
    cleaned_grid = [list(row) for row in grid]
    for y in range(1, output_size - 1):
        for x in range(1, output_size - 1):
            if is_isolated(x, y, grid, output_size):
                cleaned_grid[y][x] = '.'
    grid = [''.join(row) for row in cleaned_grid]

    # Step 6: Render at 5x scale with the bead palette
    palette = {k: (v[1].red(), v[1].green(), v[1].blue(),
                   255 if k != '.' else 0) for k, v in BEAD_PALETTE.items()}
    from resources.generate_toyu import render_pixel_art
    return render_pixel_art(grid, palette, scale=5)


def get_default_pet_path():
    """Get path to the default pet image (ToYu the potato)."""
    return _resource_path("resources/toyu_pet.png")


def get_tv_pet_path():
    """Get path to the TV-kun pet image."""
    return _resource_path("resources/tv_pet.png")


def get_house_path():
    """Get path to the house sprite image."""
    return _resource_path("resources/house.png")


def get_knock_path():
    """Get path to the door knock sound effect."""
    return _resource_path("resources/knock.wav")
