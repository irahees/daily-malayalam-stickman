from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
FRAMES = OUT / "frames"
WIDTH, HEIGHT = 1080, 1920
FPS = 30

# Temporary sample script. AI story generation is a separate next stage.
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


def create_voice(text: str, destination: Path) -> None:
    """Generate Malayalam narration using the Gemini TTS Interactions REST API."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it as a GitHub Actions repository secret."
        )

    model = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
    voice = os.getenv("GEMINI_TTS_VOICE", "Kore")
    style = os.getenv(
        "GEMINI_TTS_STYLE",
        "Speak natural, conversational Malayalam as a skilled Kerala storyteller. "
        "Use clear Malayalam pronunciation, a warm human-like voice, lively but not childish "
        "delivery, varied pacing, and natural pauses. Keep the spoken words exactly as written."
    )

    payload = {
        "model": model,
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": style
                }]
            }]
        }],
        "response_format": {"type": "audio"},
        "generation_config": {
            "speech_config": [{"voice": voice}]
        }
    }

    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini TTS API returned HTTP {error.code}: {details[:1200]}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach Gemini TTS API: {error}") from error

    audio_data = (result.get("output_audio") or {}).get("data")
    if not audio_data:
        raise RuntimeError(
            "Gemini TTS response did not contain output_audio.data: "
            + json.dumps(result, ensure_ascii=False)[:1200]
        )

    audio_bytes = base64.b64decode(audio_data)
    if len(audio_bytes) < 1024 or not audio_bytes.startswith(b"RIFF"):
        raise RuntimeError(
            "Gemini TTS did not return a valid WAV file. "
            "Check the selected model and API response format."
        )

    destination.write_bytes(audio_bytes)
    print(f"Gemini TTS audio saved. Model={model}, voice={voice}, bytes={len(audio_bytes)}")


def main():
    if not shutil.which("ffmpeg"):
        raise SystemExit("FFmpeg is required. Install it and retry.")
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    OUT.mkdir(exist_ok=True)

    for i, line in enumerate(LINES):
        draw_scene(i, line, TITLE)

    narration = " ".join(LINES)
    audio = OUT / "narration.wav"
    create_voice(narration, audio)

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
    subprocess.run([
        "ffmpeg", "-y", "-i", str(silent_video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
        "-c:a", "aac", "-shortest", str(final_video)
    ], check=True)

    print(f"Created: {final_video}")


if __name__ == "__main__":
    main()
