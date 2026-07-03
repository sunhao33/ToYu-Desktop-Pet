"""Generate ToYu — a pixel-art potato desktop pet."""

from PIL import Image
import os

C = {
    '.': (0, 0, 0, 0),           # transparent
    'O': (0x5C, 0x3D, 0x1E, 255),  # dark outline
    'B': (0x8B, 0x69, 0x14, 255),  # brown shadow
    'P': (0xC4, 0x9A, 0x3C, 255),  # potato body
    'L': (0xD4, 0xAE, 0x50, 255),  # light highlight
    'H': (0xE0, 0xC0, 0x60, 255),  # bright highlight top
    'E': (0x2C, 0x18, 0x10, 255),  # eye dark
    'W': (0xFF, 0xFF, 0xFF, 255),  # eye white/glint
    'R': (0xE8, 0x90, 0x90, 255),  # blush
    'M': (0x6B, 0x3A, 0x1A, 255),  # mouth
    'S': (0x9E, 0x7A, 0x40, 255),  # potato spots/texture
}

TOYU_32 = [
    "................................",  # 0
    "................................",  # 1
    "............OOOO................",  # 2
    "..........OOOOOOOO..............",  # 3
    ".........OOOOOOOOOOO............",  # 4
    "........OOOOOOOOOOOOO...........",  # 5
    ".......OOOOOOOOOOOOOOO..........",  # 6
    "......OOOOOOOOOOOOOOOOO.........",  # 7
    "......OOOOOOO..OOOOOOOO.........",  # 8
    ".....OOOOOOO....OOOOOOO.........",  # 9
    ".....OOOOOOO....OOOOOOO.........",  # 10
    "....OOOOOOOO....OOOOOOOO........",  # 11
    "....OOOOOOOOO..OOOOOOOOO........",  # 12
    "....OOOOOOOOOOOOOOOOOOOO........",  # 13
    "....OOOOOOOOOOOOOOOOOOOO........",  # 14
    "....OOOOOOOOOOOOOOOOOOOO........",  # 15
    "....OOOOOOOOOOOOOOOOOOOO........",  # 16
    ".....OOOOOOOOOOOOOOOOOO.........",  # 17
    "......OOOOOOOOOOOOOOOO..........",  # 18
    "......OOOOOOOOOOOOOOO...........",  # 19
    ".......OOOOOOOOOOOOO............",  # 20
    "........OOOOOOOOOOO.............",  # 21
    ".........OOOOOOOOO..............",  # 22
    "..........OOOOOOO...............",  # 23
    "............OOO.................",  # 24
    "................................",  # 25
    "................................",  # 26
    "................................",  # 27
    "................................",  # 28
    "................................",  # 29
    "................................",  # 30
    "................................",  # 31
]

TOYU_COLOR = [
    "................................",  # 0
    "............OOOO................",  # 1
    "..........OOBBBBOO..............",  # 2
    "........OBBPPPPBBOO............",  # 3
    ".......OBPPPPPPPPBBO...........",  # 4
    "......OBPPPPPPPPPPBBO..........",  # 5
    ".....OBPPPLLPPPPPPPBO..........",  # 6
    ".....OBPPLHHHLPPPPPBO..........",  # 7
    "....OBPPLLHHLPPPPPPBO.........",  # 8
    "....OBPPPLLLPPPPPPPBO.........",  # 9
    "....OBPPPPESPPWEPPPPBO.........",  # 10
    "....OBPPPPESPPWEPPPPBO.........",  # 11
    "....OBPPPPPSSSSPPPPPPO.........",  # 12
    ".....OBPPPPRPPPRPPPPBO..........",  # 13
    ".....OBPPPPPPPPPPPPBO..........",  # 14
    ".....OBPPPPPMMPPPPPBO..........",  # 15
    "......OBPPPMMMMPPBBO...........",  # 16
    "......OBPPPPPPPPBBO............",  # 17
    ".......OBBPPPPPBBO.............",  # 18
    "........OOBBBBBOO..............",  # 19
    "..........OOOOO................",  # 20
    ".........OSPSPSPO...............",  # 21
    "..........OSPSPO................",  # 22
    "...........OPPO................",  # 23
    "............OO.................",  # 24
    "............OO.................",  # 25
    "..........OOOO.................",  # 26
    "..........O..O.................",  # 27
    "................................",  # 28
    "................................",  # 29
    "................................",  # 30
    "................................",  # 31
]

def render_pixel_art(art, palette, scale=4):
    """Render a pixel art grid to a PIL Image.

    Args:
        art: list of strings, each char = palette key
        palette: dict mapping char to (R,G,B,A)
        scale: each "pixel" gets scaled to scale×scale real pixels

    Returns:
        PIL Image in RGBA
    """
    height = len(art)
    width = max(len(row) for row in art)
    img = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))

    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            color = palette.get(ch)
            if color and color[3] > 0:
                for dy in range(scale):
                    for dx in range(scale):
                        img.putpixel((x * scale + dx, y * scale + dy), color)

    return img

def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    scale = 5  # 32×5 = 160px

    toyu = render_pixel_art(TOYU_COLOR, C, scale=scale)
    pet_path = os.path.join(output_dir, "toyu_pet.png")
    toyu.save(pet_path, "PNG")
    print(f"ToYu pet: {pet_path} ({toyu.width}×{toyu.height})")

    icon_img = render_pixel_art(TOYU_COLOR, C, scale=2)  # 32×2 = 64px
    icon_path = os.path.join(output_dir, "toyu_icon.ico")
    icon_img.save(icon_path, format="ICO", sizes=[(64, 64)])
    print(f"ToYu icon: {icon_path}")

    large = render_pixel_art(TOYU_COLOR, C, scale=4)
    large_path = os.path.join(output_dir, "toyu_128.png")
    large.save(large_path, "PNG")
    print(f"ToYu large: {large_path} ({large.width}×{large.height})")

if __name__ == "__main__":
    main()
