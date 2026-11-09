from __future__ import annotations

import base64
import json
import math
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
FRAMES = OUT / "frames"
WIDTH, HEIGHT = 720, 1280
FPS = 24

TITLE = ""
LINES: list[str] = []


def open_with_retries(request: urllib.request.Request, timeout: int, label: str):
    """Retry transient Gemini overloads, connection failures, and socket timeouts."""
    retryable = {429, 500, 502, 503, 504}
    max_attempts = 7
    for attempt in range(max_attempts):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if error.code not in retryable or attempt == max_attempts - 1:
                raise RuntimeError(
                    f"{label} API HTTP {error.code} after {attempt + 1} attempt(s): {details[:1200]}"
                ) from error
            delay = min(60, 2 ** (attempt + 1))
            print(f"{label} API temporarily returned HTTP {error.code}; retrying in {delay}s...")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
            if attempt == max_attempts - 1:
                raise RuntimeError(
                    f"{label} API connection timed out or failed after {max_attempts} attempts: {error}"
                ) from error
            delay = min(60, 2 ** (attempt + 1))
            print(f"{label} API connection/timeout issue; retrying in {delay}s...")
            time.sleep(delay)


def generate_story() -> tuple[str, list[str]]:
    """Create a fresh, structured Malayalam mini-story with Gemini before narration."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for AI story generation.")
    model = os.getenv("GEMINI_STORY_MODEL", "gemini-3.8-flash")
    prompt = """
Write ONE original, highly engaging Malayalam short story for a 45-60 second vertical stickman video.
Audience: Malayalam-speaking teens and families in Kerala. Use natural spoken Kerala Malayalam,
not textbook Malayalam. Genre: clever mystery/thriller with emotional payoff OR grounded comedy
with a genuinely clever twist. Avoid childish nonsense, random magic, copied plots, filler,
repeated jokes, and predictable endings. The opening must create curiosity in the first sentence.
Every event must have a clear cause and effect. Plant a clue before the reveal. End with a satisfying
twist or emotional reveal, then a short audience question. Create exactly 6 scene narration lines.
Each line should be concise enough for subtitles and spoken narration. Make all dialogue/story text
Malayalam. Give a short Malayalam title. Return valid JSON only:
{"title":"...","scenes":["...","...","...","...","...","..."]}
Do not add markdown fences or explanations.
"""
    schema = {
        "type": "OBJECT",
        "properties": {
            "title": {"type": "STRING"},
            "scenes": {"type": "ARRAY", "items": {"type": "STRING"}}
        },
        "required": ["title", "scenes"]
    }
    payload = {
        "model": model,
        "input": prompt,
        "generation_config": {"temperature": 0.95},
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema
        }
    }
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST"
    )
    with open_with_retries(request, timeout=300, label="Gemini story") as response:
        result = json.loads(response.read().decode("utf-8"))

    raw = result.get("output_text")
    if not raw:
        try:
            raw = next(
                part["text"]
                for step in result.get("steps", [])
                if step.get("type") == "model_output"
                for part in step.get("content", [])
                if part.get("type") == "text" and part.get("text")
            )
        except (StopIteration, AttributeError, TypeError, KeyError) as error:
            raise RuntimeError("Gemini Interactions API returned no story text.") from error
    try:
        story = json.loads(raw)
        title = str(story["title"]).strip()
        scenes = [str(item).strip() for item in story["scenes"]]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise RuntimeError("Gemini returned an invalid story JSON structure.") from error
    if not title or len(scenes) != 6 or any(not line for line in scenes):
        raise RuntimeError("Story validation failed: expected a title and exactly 6 non-empty scenes.")
    if any(len(line) > 240 for line in scenes):
        raise RuntimeError("Story validation failed: each scene must be concise (240 characters max).")
    story_file = OUT / "story.json"
    story_file.write_text(json.dumps({"title": title, "scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated fresh Malayalam story: {title}")
    return title, scenes


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


def draw_scene_frame(index: int, line: str, title: str, frame: int, scene_frames: int, output_frame: int):
    """Draw one animated 2D frame; the character stays visually consistent."""
    phase = (frame / max(scene_frames, 1)) * math.tau
    bob = int(5 * math.sin(phase * 2))
    walk = 18 * math.sin(phase * 2)
    x = int(355 + 48 * math.sin(phase) + walk)
    head_y = 710 + bob

    sky = Image.new("RGB", (WIDTH, HEIGHT), (157, 211, 226))
    draw = ImageDraw.Draw(sky)
    draw.rectangle((0, 850, WIDTH, HEIGHT), fill=(112, 165, 104))
    cloud_x = int((frame * 1.1 + index * 95) % (WIDTH + 180)) - 90
    for cx, cy, r in [(cloud_x, 145, 34), (cloud_x + 38, 132, 43), (cloud_x + 78, 150, 30)]:
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(246, 249, 245))

    wall = (238, 205, 155) if index % 2 == 0 else (224, 190, 145)
    draw.rectangle((70, 535, 650, 925), fill=wall, outline=(79, 59, 46), width=6)
    draw.polygon([(35, 555), (360, 345), (685, 555)], fill=(125, 65, 48), outline=(79, 45, 38))
    draw.rectangle((265, 700, 405, 925), fill=(108, 70, 49), outline=(65, 47, 38), width=5)
    draw.rectangle((105, 650, 225, 770), fill=(145, 202, 218), outline=(75, 60, 48), width=5)
    draw.line((165, 650, 165, 770), fill=(75, 60, 48), width=4)
    draw.line((105, 710, 225, 710), fill=(75, 60, 48), width=4)

    draw.line((610, 830, 580, 440), fill=(105, 75, 49), width=15)
    for angle in [-2.7, -2.1, -1.55, -0.95, -0.35]:
        ex = 580 + int(180 * math.cos(angle))
        ey = 440 + int(100 * math.sin(angle))
        draw.line((580, 440, ex, ey), fill=(39, 111, 66), width=13)

    draw.ellipse((x-90, 1125, x+90, 1160), fill=(89, 132, 79))
    ink = (28, 35, 42)
    draw.ellipse((x-48, head_y-48, x+48, head_y+48), fill=(255, 224, 184), outline=ink, width=8)
    draw.ellipse((x-18, head_y-10, x-8, head_y+2), fill=ink)
    draw.ellipse((x+8, head_y-10, x+18, head_y+2), fill=ink)
    draw.arc((x-17, head_y+1, x+17, head_y+25), 5, 175, fill=ink, width=4)

    shoulder_y = head_y + 52
    hip_y = head_y + 230
    draw.line((x, shoulder_y, x, hip_y), fill=ink, width=12)
    arm_swing = int(38 * math.sin(phase * 2))
    if index == 1:
        draw.line((x, shoulder_y+35, x-62, shoulder_y+85), fill=ink, width=10)
        draw.line((x, shoulder_y+35, x+112, shoulder_y-35+arm_swing), fill=ink, width=10)
    else:
        draw.line((x, shoulder_y+35, x-92, shoulder_y+115-arm_swing), fill=ink, width=10)
        draw.line((x, shoulder_y+35, x+92, shoulder_y+115+arm_swing), fill=ink, width=10)
    leg_swing = int(30 * math.sin(phase * 2))
    draw.line((x, hip_y, x-62+leg_swing, hip_y+145), fill=ink, width=12)
    draw.line((x, hip_y, x+62-leg_swing, hip_y+145), fill=ink, width=12)

    if index == 1:
        draw.rounded_rectangle((420, 560, 625, 665), radius=12, fill=(246, 230, 179), outline=(67, 52, 39), width=5)
        draw.text((440, 590), "ചായക്കട", font=get_font(25), fill=(50, 42, 35))

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
    sky.save(FRAMES / f"frame_{output_frame:06d}.png", optimize=True)


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
    with open_with_retries(request, timeout=300, label="Gemini TTS") as response:
        result = json.loads(response.read().decode("utf-8"))

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

    global TITLE, LINES
    TITLE, LINES = generate_story()
    narration = " ".join(LINES)
    audio = OUT / "narration.wav"
    create_voice(narration, audio)

    duration = probe_duration(audio)
    total_frames = max(int(math.ceil(duration * FPS)), FPS * len(LINES))
    base, remainder = divmod(total_frames, len(LINES))
    frame_number = 0
    for scene_index, line in enumerate(LINES):
        scene_frames = base + (1 if scene_index < remainder else 0)
        for local_frame in range(scene_frames):
            draw_scene_frame(scene_index, line, TITLE, local_frame, scene_frames, frame_number)
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
