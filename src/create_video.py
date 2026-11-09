from __future__ import annotations

import base64
import json
import math
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
WIDTH, HEIGHT = 720, 1280
FPS = 24

TITLE = "അടഞ്ഞ ലൈബ്രറിയിലെ രഹസ്യം"
LINES = [
    "ഗ്രാമത്തിലെ അടഞ്ഞ ലൈബ്രറിയിൽ... എല്ലാ രാത്രിയും കൃത്യം ഒൻപത് മണിക്ക് വെളിച്ചം തെളിയും.",
    "വാതിൽ പൂട്ടിയിരിക്കും. പക്ഷേ ഓരോ രാവിലെയും ഒരു പുസ്തകം മാത്രം സ്ഥാനം മാറിയിരിക്കും.",
    "കാവൽക്കാരൻ ക്യാമറ വെച്ചു. ദൃശ്യത്തിൽ കണ്ടത് ഒരു നിഴൽ... മുഖം ആരും കണ്ടില്ല.",
    "അടുത്ത രാത്രി ഒരു കുട്ടി ഒളിച്ചുനിന്നു. അകത്ത് കയറിയത് പഴയ ലൈബ്രേറിയനായിരുന്നു.",
    "വിരമിച്ച ദിവസം ലൈബ്രറി അടഞ്ഞു. അതിനുശേഷം കീറിയ പുസ്തകങ്ങൾ നന്നാക്കാൻ അദ്ദേഹം രാത്രിയിൽ വരികയായിരുന്നു.",
    "പിറ്റേന്ന് വാതിലിൽ ഒരു കുറിപ്പ്: സാർ, ലൈബ്രറി വീണ്ടും തുറക്കണം... ഞങ്ങൾ കാത്തിരിക്കുന്നു."
]


def find_font(bold: bool = False) -> str | None:
    candidates = []
    if bold:
        candidates += ["/usr/share/fonts/truetype/noto/NotoSansMalayalam-Bold.ttf"]
    candidates += [
        "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMalayalam[wght].ttf",
        "/usr/share/fonts/truetype/NotoSansMalayalam-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def get_font(size: int, bold: bool = False):
    path = find_font(bold)
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


def draw_scene_frame(index: int, line: str, title: str, frame: int, scene_frames: int):
    """Draw one animated 2D frame; the character stays visually consistent."""
    t = frame / FPS
    phase = (frame / max(scene_frames, 1)) * math.tau
    bob = int(5 * math.sin(phase * 2))
    walk = 18 * math.sin(phase * 2)
    x = int(355 + 48 * math.sin(phase) + walk)
    head_y = 710 + bob

    # Warm Kerala daylight with a gentle moving-cloud/parallax feel.
    sky = Image.new("RGB", (WIDTH, HEIGHT), (157, 211, 226))
    draw = ImageDraw.Draw(sky)
    draw.rectangle((0, 850, WIDTH, HEIGHT), fill=(112, 165, 104))
    cloud_x = int((frame * 1.1 + index * 95) % (WIDTH + 180)) - 90
    for cx, cy, r in [(cloud_x, 145, 34), (cloud_x + 38, 132, 43), (cloud_x + 78, 150, 30)]:
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(246, 249, 245))

    # Kerala tiled-roof house / tea shop, with small scene-to-scene variation.
    wall = (238, 205, 155) if index % 2 == 0 else (224, 190, 145)
    draw.rectangle((70, 535, 650, 925), fill=wall, outline=(79, 59, 46), width=6)
    draw.polygon([(35, 555), (360, 345), (685, 555)], fill=(125, 65, 48), outline=(79, 45, 38))
    draw.rectangle((265, 700, 405, 925), fill=(108, 70, 49), outline=(65, 47, 38), width=5)
    draw.rectangle((105, 650, 225, 770), fill=(145, 202, 218), outline=(75, 60, 48), width=5)
    draw.line((165, 650, 165, 770), fill=(75, 60, 48), width=4)
    draw.line((105, 710, 225, 710), fill=(75, 60, 48), width=4)

    # Coconut tree silhouette on the right.
    draw.line((610, 830, 580, 440), fill=(105, 75, 49), width=15)
    for angle in [-2.7, -2.1, -1.55, -0.95, -0.35]:
        ex = 580 + int(180 * math.cos(angle))
        ey = 440 + int(100 * math.sin(angle))
        draw.line((580, 440, ex, ey), fill=(39, 111, 66), width=13)

    # Ground and soft character shadow.
    draw.ellipse((x-90, 1125, x+90, 1160), fill=(89, 132, 79))
    ink = (28, 35, 42)
    # Head, eyes and changing expression.
    draw.ellipse((x-48, head_y-48, x+48, head_y+48), fill=(255, 224, 184), outline=ink, width=8)
    draw.ellipse((x-18, head_y-10, x-8, head_y+2), fill=ink)
    draw.ellipse((x+8, head_y-10, x+18, head_y+2), fill=ink)
    if index == 1:
        draw.arc((x-17, head_y+3, x+17, head_y+27), 5, 175, fill=ink, width=4)
    else:
        draw.arc((x-17, head_y+1, x+17, head_y+25), 5, 175, fill=ink, width=4)

    # Torso and animated limbs.
    shoulder_y = head_y + 52
    hip_y = head_y + 230
    draw.line((x, shoulder_y, x, hip_y), fill=ink, width=12)
    arm_swing = int(38 * math.sin(phase * 2))
    if index == 1:
        # Point toward the talking shop sign.
        draw.line((x, shoulder_y+35, x-62, shoulder_y+85), fill=ink, width=10)
        draw.line((x, shoulder_y+35, x+112, shoulder_y-35+arm_swing), fill=ink, width=10)
    else:
        draw.line((x, shoulder_y+35, x-92, shoulder_y+115-arm_swing), fill=ink, width=10)
        draw.line((x, shoulder_y+35, x+92, shoulder_y+115+arm_swing), fill=ink, width=10)
    leg_swing = int(30 * math.sin(phase * 2))
    draw.line((x, hip_y, x-62+leg_swing, hip_y+145), fill=ink, width=12)
    draw.line((x, hip_y, x+62-leg_swing, hip_y+145), fill=ink, width=12)

    # Signboard makes the tea-shop scene easier to read.
    if index == 1:
        draw.rounded_rectangle((420, 560, 625, 665), radius=12, fill=(246, 230, 179), outline=(67, 52, 39), width=5)
        sign_font = get_font(25)
        draw.text((440, 590), "ചായക്കട", font=sign_font, fill=(50, 42, 35))

    # Bold Malayalam typography with a dark caption panel and scene-colour accents.
    title_font = get_font(31, bold=True)
    body_font = get_font(30, bold=True)
    draw.rounded_rectangle((28, 34, 692, 125), radius=22, fill=(22, 34, 47), outline=(247, 190, 82), width=3)
    draw.text((49, 57), title, font=title_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=(22, 34, 47))
    accent_colors = [(255, 202, 82), (102, 220, 231), (255, 132, 119), (160, 232, 164), (255, 202, 82), (190, 166, 255)]
    accent = accent_colors[index % len(accent_colors)]
    draw.rounded_rectangle((28, 1040, 692, 1238), radius=25, fill=(18, 27, 39), outline=accent, width=4)
    draw.rounded_rectangle((52, 1060, 112, 1068), radius=4, fill=accent)
    rows = wrap_text(draw, line, body_font, 575)
    y = 1090
    for row in rows[:3]:
        draw.text((58, y), row, font=body_font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(10, 15, 23))
        y += 43

    FRAMES.mkdir(parents=True, exist_ok=True)
    sky.save(FRAMES / f"frame_{frame:06d}.png", optimize=True)


def create_voice(text: str, destination: Path) -> None:
    """Generate Malayalam narration using the Gemini TTS Interactions REST API."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it as a GitHub Actions repository secret.")

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
        "input": [{"type": "user_input", "content": [{
            "type": "text", "text": text,
            "annotations": [{"type": "speech_metadata", "style": style}]
        }]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]}
    }
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini TTS API returned HTTP {error.code}: {details[:1200]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach Gemini TTS API: {error}") from error

    audio_data = (result.get("output_audio") or {}).get("data")
    if not audio_data:
        for step in result.get("steps", []):
            for item in step.get("content", []):
                if item.get("type") in (None, "audio") and item.get("data"):
                    audio_data = item["data"]
                    break
            if audio_data:
                break
    if not audio_data:
        raise RuntimeError("Gemini TTS response did not contain audio data.")
    audio_bytes = base64.b64decode(audio_data)
    if len(audio_bytes) < 1024 or not audio_bytes.startswith(b"RIFF"):
        raise RuntimeError("Gemini TTS did not return a valid WAV file.")
    destination.write_bytes(audio_bytes)
    print(f"Gemini TTS audio saved. Model={model}, voice={voice}, bytes={len(audio_bytes)}")


def probe_duration(audio: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
        check=True, capture_output=True, text=True
    )
    return max(float(result.stdout.strip()), 1.0)


def main():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("FFmpeg and ffprobe are required.")
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    OUT.mkdir(exist_ok=True)

    narration = " ".join(LINES)
    audio = OUT / "narration.wav"
    create_voice(narration, audio)

    # Render a real animated frame sequence, timed to the generated narration.
    duration = probe_duration(audio)
    total_frames = max(int(math.ceil(duration * FPS)), FPS * len(LINES))
    base, remainder = divmod(total_frames, len(LINES))
    frame_number = 0
    for scene_index, line in enumerate(LINES):
        scene_frames = base + (1 if scene_index < remainder else 0)
        for local_frame in range(scene_frames):
            draw_scene_frame(scene_index, line, TITLE, local_frame, scene_frames)
            frame_number += 1
        print(f"Rendered animated scene {scene_index + 1}/{len(LINES)}")

    silent_video = OUT / "silent.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS), "-i",
        str(FRAMES / "frame_%06d.png"),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(silent_video)
    ], check=True)

    final_video = OUT / "daily_malayalam_stickman.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(silent_video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(final_video)
    ], check=True)
    print(f"Created animated video: {final_video} ({frame_number} frames at {FPS} fps)")


if __name__ == "__main__":
    main()
