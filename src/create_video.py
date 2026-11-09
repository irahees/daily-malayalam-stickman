from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
FRAMES = OUT / "frames"
WIDTH, HEIGHT = 1080, 1920
FPS = 30

# Sample placeholder narration. Replace with generated story content in the next stage.
TITLE = "കേരളത്തിലെ ഒരു രസകരമായ ദിവസം"
LINES = [
    "ഒരു ദിവസം നമ്മുടെ നാട്ടിൽ ഒരു വിചിത്ര സംഭവം നടന്നു.",
    "ചായക്കടയിലെ ബോർഡ് തന്നെ ആളുകളോട് സംസാരിക്കാൻ തുടങ്ങി.",
    "ആദ്യം എല്ലാവരും പേടിച്ചു... പിന്നെ ചായ സൗജന്യമാണെന്ന് കേട്ട് തിരക്കായി.",
    "നിങ്ങളുടെ നാട്ടിൽ ഇങ്ങനെ സംഭവിച്ചാൽ എന്ത് ചെയ്യും?"
]

def find_font() -> str | None:
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMalayalam[wght].ttf",
        "/usr/share/fonts/truetype/NotoSansMalayalam-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None

def get_font(size: int):
    path = find_font()
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()

def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int):
    words = text.split()
    rows, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                rows.append(current)
            current = word
    if current:
        rows.append(current)
    return rows

def draw_scene(index: int, line: str, title: str):
    image = Image.new("RGB", (WIDTH, HEIGHT), (248, 244, 232))
    draw = ImageDraw.Draw(image)

    # Simple Kerala-inspired setting and consistent stickman character.
    draw.rectangle((0, 1320, WIDTH, HEIGHT), fill=(222, 232, 207))
    draw.rectangle((90, 900, 990, 1330), fill=(222, 190, 145), outline=(65, 54, 46), width=8)
    draw.polygon([(55, 920), (540, 650), (1025, 920)], fill=(125, 76, 57), outline=(65, 54, 46))
    draw.rectangle((420, 1050, 660, 1330), fill=(120, 82, 58), outline=(65, 54, 46), width=6)

    # Character position varies slightly by scene; design remains consistent.
    x = 270 + (index % 2) * 520
    head_y = 1110
    draw.ellipse((x - 70, head_y - 70, x + 70, head_y + 70), outline=(25, 25, 25), width=13)
    draw.line((x, head_y + 70, x, head_y + 300), fill=(25, 25, 25), width=15)
    draw.line((x, head_y + 140, x - 105, head_y + 230), fill=(25, 25, 25), width=13)
    draw.line((x, head_y + 140, x + 105, head_y + 230), fill=(25, 25, 25), width=13)
    draw.line((x, head_y + 300, x - 95, head_y + 455), fill=(25, 25, 25), width=14)
    draw.line((x, head_y + 300, x + 95, head_y + 455), fill=(25, 25, 25), width=14)

    title_font = get_font(58)
    body_font = get_font(54)
    draw.rounded_rectangle((55, 75, 1025, 260), radius=35, fill=(255, 255, 255), outline=(30, 30, 30), width=5)
    draw.text((90, 115), title, font=title_font, fill=(20, 20, 20), stroke_width=0)

    draw.rounded_rectangle((55, 1580, 1025, 1845), radius=32, fill=(255, 255, 255), outline=(20, 20, 20), width=5)
    rows = wrap_text(draw, line, body_font, 850)
    y = 1625
    for row in rows[:3]:
        draw.text((95, y), row, font=body_font, fill=(10, 10, 10), stroke_width=0)
        y += 72

    FRAMES.mkdir(parents=True, exist_ok=True)
    image.save(FRAMES / f"scene_{index:03d}.png")

async def create_voice(text: str, destination: Path):
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, "ml-IN-SobhanaNeural", rate="+0%")
        await communicate.save(str(destination))
        return True
    except Exception as exc:
        print(f"TTS unavailable: {exc}")
        return False

def main():
    if not shutil.which("ffmpeg"):
        raise SystemExit("FFmpeg is required. Install it and retry.")
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    OUT.mkdir(exist_ok=True)

    for i, line in enumerate(LINES):
        draw_scene(i, line, TITLE)

    narration = " ".join(LINES)
    audio = OUT / "narration.mp3"
    has_audio = asyncio.run(create_voice(narration, audio))

    # Each still is shown for 4 seconds in this first test render.
    concat = OUT / "frames.txt"
    with concat.open("w", encoding="utf-8") as handle:
        for i in range(len(LINES)):
            handle.write(f"file '{(FRAMES / f'scene_{i:03d}.png').as_posix()}'\n")
            handle.write("duration 4\n")
        handle.write(f"file '{(FRAMES / f'scene_{len(LINES)-1:03d}.png').as_posix()}'\n")

    silent_video = OUT / "silent.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", f"scale={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent_video)
    ], check=True)

    final_video = OUT / "daily_malayalam_stickman.mp4"
    if has_audio:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(silent_video), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
            "-c:a", "aac", "-shortest", str(final_video)
        ], check=True)
    else:
        shutil.copy2(silent_video, final_video)

    print(f"Created: {final_video}")

if __name__ == "__main__":
    main()
