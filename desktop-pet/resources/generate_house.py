"""Generate pixel-art house and door-knock sound for the desktop pet."""

from PIL import Image
import os
import struct
import wave
import math

C = {
    '.': (0, 0, 0, 0),             # transparent
    'O': (0x3D, 0x28, 0x22, 255), # dark outline
    'R': (0xC7, 0x4B, 0x3A, 255), # roof main red
    'r': (0xDD, 0x6B, 0x55, 255), # roof light
    'H': (0xEA, 0x80, 0x6A, 255), # roof highlight
    'h': (0xF0, 0x95, 0x80, 255), # roof bright
    'C': (0x8B, 0x5E, 0x3E, 255), # chimney brick
    'c': (0xA2, 0x72, 0x52, 255), # chimney light
    'S': (0xDD, 0xDD, 0xDD, 255), # smoke
    'W': (0xFD, 0xF5, 0xE8, 255), # wall cream
    'w': (0xEE, 0xE0, 0xCC, 255), # wall shadow
    'L': (0xFF, 0xFA, 0xF2, 255), # wall highlight
    'D': (0x5C, 0x35, 0x18, 255), # door dark outline
    'd': (0x7A, 0x4E, 0x2E, 255), # door wood
    'K': (0xC4, 0x9A, 0x3C, 255), # door knob gold
    'k': (0xDD, 0xB8, 0x60, 255), # knob highlight
    'F': (0x6B, 0x50, 0x30, 255), # window frame dark
    'f': (0x8B, 0x6E, 0x48, 255), # window frame light
    'B': (0xA8, 0xDD, 0xF0, 255), # window glass
    'b': (0xC8, 0xEE, 0xFA, 255), # window glass light
    'P': (0x88, 0xCC, 0x44, 255), # plant green
    'p': (0xAA, 0xDD, 0x66, 255), # plant light
    'G': (0x5C, 0x3D, 0x1E, 255), # ground dark
    'g': (0x7A, 0x55, 0x30, 255), # ground mid
    'T': (0x90, 0x80, 0x60, 255), # ground path
    'E': (0x4A, 0x8C, 0x3A, 255), # grass
}

HOUSE = [
    "................................",  # 0
    ".............SSS................",  # 1  smoke puff
    "............SSSSS...............",  # 2
    "...........SS...S...............",  # 3
    "..........SSS..SS...............",  # 4
    ".............CCCC...............",  # 5  chimney
    "............CCCCCC..............",  # 6
    "............cccccc..............",  # 7
    "............cccccc..............",  # 8
    "................................",  # 9
    "............RRRRR...............",  # 10 roof peak
    "...........RRRRRRR..............",  # 11
    "..........RRRHhHRRRR............",  # 12
    ".........RRRHHhhHHRRR...........",  # 13
    "........RRRHHhhhhHHRRR..........",  # 14
    ".......ORRRHHHhhHHHRRRRO........",  # 15 roof bottom edge
    "......OORRRRRRRRRRRRRRRO........",  # 16
    ".....OOWWWWWWWWWWWWWWWWO.......",  # 17 wall top
    "....OOWWLLWWWWWWWWWWWWWO......",  # 18
    "...OOWWLwwwWWWWWWWWWWWWO......",  # 19
    "...OOWWWwWwwWWWWWWWfFfWO......",  # 20 window top
    "...OOWWWwbBBbWWWWWFfBfWO......",  # 21 window glass
    "...OOWWWwWwwWWWWWDDdDDDO......",  # 22 door top
    "...OOWWWWWWWWWWWWDdddDDDO......",  # 23
    "...OOWWWWWWWWWWWWWDdKkDO......",  # 24 door knob
    "...OOWWWWWWpPWWWWDDddDDDO......",  # 25 plant left of door
    "...OOWWWWWWPPWWWWWDDDDDDO......",  # 26
    "....OOWWWWWWWWWWWWWWWWWO.......",  # 27 wall bottom
    ".....OOWWWWWWWWWWWWWWWO........",  # 28
    "......OOWWWWWWWWWWWWWO.........",  # 29
    ".......OOOGGTTgGGOOO...........",  # 30 ground
    ".........EEEEEggEEEE...........",  # 31 grass
]

DOOR_GRID_X1, DOOR_GRID_X2 = 13, 18
DOOR_GRID_Y1, DOOR_GRID_Y2 = 22, 26
SCALE = 5

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

def generate_knock_wav(output_path):
    """Generate a short door-knock sound effect."""
    sample_rate = 22050
    duration = 0.18
    num_samples = int(sample_rate * duration)

    samples = []
    for i in range(num_samples):
        t = i / sample_rate

        knock1 = 0.0
        if 0.0 <= t < 0.06:
            envelope = math.exp(-t * 40)
            knock1 = envelope * math.sin(2 * math.pi * 180 * t) * 0.9

        knock2 = 0.0
        t2 = t - 0.08
        if t2 >= 0 and t2 < 0.06:
            envelope = math.exp(-t2 * 40)
            knock2 = envelope * math.sin(2 * math.pi * 200 * t2) * 0.85

        val = knock1 + knock2
        val = max(-1.0, min(1.0, val))
        samples.append(int(val * 32767))

    with wave.open(output_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f'<{len(samples)}h', *samples))

def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    scale = SCALE

    house = render_pixel_art(HOUSE, C, scale=scale)
    pet_path = os.path.join(output_dir, "house.png")
    house.save(pet_path, "PNG")
    print(f"House: {pet_path} ({house.width}x{house.height})")

    knock_path = os.path.join(output_dir, "knock.wav")
    generate_knock_wav(knock_path)
    print(f"Knock sound: {knock_path}")

if __name__ == "__main__":
    main()
