import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(os.path.dirname(os.path.realpath(__file__)))

font_size = 96
font = ImageFont.truetype((ROOT_DIR / "build" / "PreFiraCode-VF.ttf").as_posix(), font_size)
padding = font_size
dataset = [
    # Alphabet
    ["a", "b", "c", "d", "e", "f", "g", "h", "i"],
    ["j", "k", "l", "m", "n", "o", "p", "q", "r"],
    ["s", "t", "u", "v", "w", "x", "y", "z"],
    # Korean
    ["가", "나", "다", "라", "마", "바", "사"],
    ["아", "자", "차", "카", "타", "파", "하"],
    ["다", "람", "쥐", "헌", "쳇", "바", "퀴", "에", "타", "고", "파"],
    ["abcdefghijklmn"],
    ["다람쥐헌쳇바퀴에타고파"],
    ["다A람B쥐C헌D쳇E바"],
    # Fira Code Ligatures
    ["++", "--"],
    ["->", "=>", "__"],
    ["==", "===", "!=", "!=="],
    # cv02
    ["g", "\u011d", "\u011f", "\u0121", "\u0123"],
    # ss01
    ["r"],
    #ss02
    ["<=", ">="],
    # ss03
    ["&", "&&"],
    # ss05
    ["@", "~@"],
]
line_len = [sum(len(word) for word in line) + len(line) - 1 for line in dataset]

width = max(line_len) * font_size + padding * 2
height = len(dataset) * font_size + padding * 2
img = Image.new('RGB', (width, height), "white")

draw = ImageDraw.Draw(img)

for i, line in enumerate(dataset):
    top = padding + i * font_size
    left = font_size / 2
    for word in line:
        l, t, r, b = font.getbbox(word)
        draw.text((left, top), word, "black", font)
        left += (r - l) + font_size

img.show()
