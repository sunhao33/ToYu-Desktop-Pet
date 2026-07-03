"""Generate TV-kun — a pixel-art CRT television desktop pet."""

from PIL import Image
import os

C = {
    '.': (0, 0, 0, 0),              # transparent
    'O': (0x2A, 0x2A, 0x2A, 255),  # dark outline
    'G': (0x3A, 0x3A, 0x3A, 255),  # outline shadow
    'D': (0x44, 0x44, 0x44, 255),  # body shadow/dark
    'B': (0x58, 0x58, 0x58, 255),  # body grey
    'L': (0x72, 0x72, 0x72, 255),  # body light
    'H': (0x90, 0x90, 0x90, 255),  # bright highlight
    'A': (0xB0, 0xB4, 0xB8, 255),  # antenna silver
    'S': (0x15, 0x1E, 0x28, 255),  # screen bg (deep CRT glass)
    'T': (0x1E, 0x2A, 0x36, 255),  # screen mid-tone
    'E': (0x33, 0xFF, 0xAA, 255),  # eye glow
    'e': (0x1A, 0xBB, 0x77, 255),  # eye inner
    'W': (0xCC, 0xFF, 0xEE, 255),  # bright glint / static
    'M': (0x33, 0xFF, 0xAA, 255),  # mouth glow
    'R': (0xFF, 0x44, 0x44, 255),  # power LED on
    'K': (0x3A, 0x3A, 0x3A, 255),  # knob dark
    'N': (0x66, 0x66, 0x66, 255),  # knob light
    'F': (0x3E, 0x3E, 0x3E, 255),  # feet
}

TV_KUN = [
    "................................",  # 0
    "...........AAAA.................",  # 1  rabbit ears top
    "..........A.A..A................",  # 2  ear posts
    ".........A..AA..A...............",  # 3
    "........A...AA...A..............",  # 4  ear base
    ".......GGGGGGGGGGGGGG...........",  # 5  antenna mount
    "......GDDDDDDDDDDDDDDDG.........",  # 6  body shadow top
    ".....GDBBBBBBBBBBBBBBBBDG.......",  # 7  body top
    "....GDBLLLLLLLLLLLLLLLLBDG......",  # 8  body highlight
    "...GDDBLLLLLLLLLLLLLLLBDDG.....",  # 9  body upper
    "...GDDBBBBSSSSSSSSSBBBBBDDG.....",  # 10 screen border top
    "...GDBBBSSSSSSSSSSSSSSBBBDG.....",  # 11
    "...GDBBSSSSSSSSSSSSSSSSBBG.R...",  # 12 screen edge + power LED
    "...GBBSSSTTTTTTTTTTTTTSSBG.....",  # 13
    "...GBSSSTTTTTTTTTTTTTTSSG.....",  # 14 screen inner
    "...GBSSTTTT..EEEE..TTTTSG.....",  # 15 eyes area
    "...GBSSTTTE..EEEE..ETTTSG.....",  # 16 eyes
    "...GBSSTTT...........TTTSG.....",  # 17 between eyes
    "...GBSSSTT....W......TSSSG.....",  # 18 cheek glint
    "...GBSSSSTT..WWWW..TTSSSG.....",  # 19 mouth smile area
    "...GBBSSSTTTTTTTTTTTTSSBG.....",  # 20 mouth
    "...GBBSSSSSSTTTTTTSSSSSBG.....",  # 21 screen lower
    "...GDBBSSSSSSSSSSSSSSBBDG.....",  # 22 screen border bottom
    "...GDBBBBBSSSSSSSSBBBBBDG......",  # 23 body lower
    "....GDDBBBBBBBBBBBBBBDDG.......",  # 24 body bottom
    ".....GDDBBBBBBBBBBBDDDG........",  # 25
    "......GGDDDBBBBBBBDDDG.KK.......",  # 26 knobs area
    "........GGDDDDDDDDDGG..........",  # 27
    "..........GGGGGGGGG............",  # 28
    ".........FF.......FF...........",  # 29 feet left
    ".........FF.......FF...........",  # 30 feet right
    "................................",  # 31
]

def render_pixel_art(art, palette, scale=4):
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

    tv = render_pixel_art(TV_KUN, C, scale=scale)
    pet_path = os.path.join(output_dir, "tv_pet.png")
    tv.save(pet_path, "PNG")
    print(f"TV-kun pet: {pet_path} ({tv.width}x{tv.height})")

if __name__ == "__main__":
    main()
