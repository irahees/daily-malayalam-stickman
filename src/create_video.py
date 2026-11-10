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
    max_attempts = 4
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

    # If the primary Flash model is temporarily overloaded (HTTP 503), try
    # stable fallback models instead of failing the whole daily render.
    fallback_models = [
        item.strip()
        for item in os.getenv(
            "GEMINI_STORY_FALLBACK_MODELS",
            "gemini-3.7-flash,gemini-3.5-flash"
        ).split(",")
        if item.strip() and item.strip() != model
    ]
    result = None
    models_to_try = [model, *fallback_models]
    for model_name in models_to_try:
        payload["model"] = model_name
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST"
        )
        try:
            with open_with_retries(request, timeout=300, label=f"Gemini story ({model_name})") as response:
                result = json.loads(response.read().decode("utf-8"))
            print(f"Story generated using model: {model_name}")
            break
        except RuntimeError as error:
            if "HTTP 503" not in str(error) or model_name == models_to_try[-1]:
                raise
            print(f"{model_name} is overloaded; trying the next fallback model...")
    if result is None:
        raise RuntimeError("Gemini story generation failed: no model returned a response.")

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
    """Render a cinematic scene with a location change, parallax, character acting and subtitles."""
    phase = (frame / max(scene_frames, 1)) * math.tau
    progress = frame / max(scene_frames - 1, 1)
    camera = int(10 * math.sin(phase * 0.5))
    bob = int(5 * math.sin(phase * 2))
    walk = 24 * math.sin(phase * 2)
    x = int(350 + 38 * math.sin(phase) + walk)
    head_y = 690 + bob
    ink = (28, 35, 42)

    # Six distinct locations create a clear visual progression through the story.
    scenes = [
        {"sky": (26, 39, 70), "ground": (43, 67, 65), "wall": (79, 87, 111), "roof": (42, 48, 70), "name": "NIGHT"},
        {"sky": (247, 177, 113), "ground": (116, 158, 95), "wall": (239, 202, 145), "roof": (130, 65, 48), "name": "TEA SHOP"},
        {"sky": (132, 196, 215), "ground": (77, 143, 88), "wall": (224, 205, 166), "roof": (113, 65, 46), "name": "VILLAGE ROAD"},
        {"sky": (75, 104, 145), "ground": (45, 80, 78), "wall": (102, 117, 133), "roof": (48, 57, 72), "name": "BUS STOP"},
        {"sky": (246, 166, 107), "ground": (83, 132, 80), "wall": (229, 188, 135), "roof": (117, 61, 46), "name": "RIVERSIDE"},
        {"sky": (31, 37, 64), "ground": (39, 70, 61), "wall": (78, 83, 108), "roof": (39, 44, 65), "name": "THE REVEAL"},
    ][index % 6]

    sky = Image.new("RGB", (WIDTH, HEIGHT), scenes["sky"])
    draw = ImageDraw.Draw(sky)
    # Atmospheric sky glow and horizon.
    for radius in range(260, 0, -8):
        alpha = (260 - radius) / 260
        color = tuple(int(scenes["sky"][c] * (1-alpha) + (255, 205, 143)[c] * alpha * 0.30) for c in range(3))
        draw.ellipse((470-radius, 300-radius, 470+radius, 300+radius), fill=color)
    draw.rectangle((0, 835, WIDTH, HEIGHT), fill=scenes["ground"])

    # Parallax palms and distant hills.
    draw.polygon([(0, 830), (0, 735), (110, 690), (230, 760), (360, 700), (520, 765), (720, 700), (720, 850)], fill=tuple(max(0, c-18) for c in scenes["ground"]))
    for palm_x in (-20, 680):
        sway = int(12 * math.sin(phase + palm_x))
        draw.line((palm_x, 850, palm_x+22, 430), fill=(91, 66, 47), width=14)
        crown = (palm_x+22, 430)
        for a in (-2.8, -2.25, -1.7, -1.15, -0.6):
            ex = crown[0] + int(135 * math.cos(a) + sway)
            ey = crown[1] + int(78 * math.sin(a))
            draw.line((crown[0], crown[1], ex, ey), fill=(35, 105, 66), width=12)

    # Location-specific architecture and props.
    if index in (0, 5):
        draw.rectangle((65-camera, 510, 655-camera, 925), fill=scenes["wall"], outline=(55, 48, 51), width=6)
        draw.polygon([(28-camera, 530), (360-camera, 325), (692-camera, 530)], fill=scenes["roof"], outline=(48, 42, 46))
        draw.rectangle((270-camera, 690, 410-camera, 925), fill=(85, 57, 47), outline=(42, 35, 34), width=5)
        draw.rectangle((105-camera, 650, 220-camera, 760), fill=(115, 171, 193), outline=(50, 46, 44), width=5)
        draw.line((162-camera, 650, 162-camera, 760), fill=(50, 46, 44), width=4)
        draw.line((105-camera, 705, 220-camera, 705), fill=(50, 46, 44), width=4)
    elif index == 1:
        draw.rectangle((55-camera, 545, 665-camera, 925), fill=scenes["wall"], outline=(65, 51, 42), width=6)
        draw.polygon([(25-camera, 550), (360-camera, 355), (695-camera, 550)], fill=scenes["roof"])
        draw.rectangle((95-camera, 725, 625-camera, 780), fill=(99, 58, 40))
        draw.rectangle((145-camera, 620, 220-camera, 740), fill=(104, 67, 48))
        draw.rounded_rectangle((420-camera, 580, 625-camera, 670), radius=12, fill=(248, 227, 172), outline=(67, 52, 39), width=4)
        draw.text((442-camera, 606), "ചായക്കട", font=get_font(25), fill=(50, 42, 35))
        # Steam from a tea glass.
        for s in range(3):
            sx = 510 + s*14 + int(4*math.sin(phase*2+s))
            draw.arc((sx, 520, sx+18, 570), 70, 260, fill=(245, 238, 220), width=3)
    elif index == 2:
        draw.line((0, 820, 720, 820), fill=(210, 190, 151), width=90)
        draw.rectangle((55-camera, 580, 245-camera, 810), fill=(229, 191, 143), outline=(80, 62, 47), width=5)
        draw.polygon([(35-camera, 590), (150-camera, 490), (265-camera, 590)], fill=(126, 65, 48))
        draw.rectangle((480-camera, 640, 650-camera, 820), fill=(189, 205, 175), outline=(65, 74, 56), width=5)
        draw.ellipse((525-camera, 700, 565-camera, 740), fill=(244, 212, 131))
    elif index == 3:
        draw.rectangle((65-camera, 670, 655-camera, 710), fill=(57, 67, 78))
        draw.rectangle((90-camera, 705, 120-camera, 925), fill=(48, 52, 60))
        draw.rectangle((600-camera, 705, 630-camera, 925), fill=(48, 52, 60))
        draw.rounded_rectangle((150-camera, 560, 570-camera, 665), radius=16, fill=(46, 59, 76), outline=(220, 193, 146), width=4)
        draw.text((190-camera, 592), "BUS STOP", font=get_font(30, True), fill=(255, 238, 190))
        draw.line((0, 850, 720, 850), fill=(185, 173, 147), width=7)
    else:
        draw.polygon([(0, 810), (170, 770), (360, 830), (540, 760), (720, 810), (720, 930), (0, 930)], fill=(47, 109, 112))
        for ripple in range(5):
            rx = int((frame*3 + ripple*145) % 760)
            draw.arc((rx-45, 825+ripple*13, rx+45, 845+ripple*13), 0, 180, fill=(161, 209, 195), width=3)
        draw.rectangle((60-camera, 570, 260-camera, 830), fill=scenes["wall"], outline=(62, 52, 48), width=5)
        draw.polygon([(35-camera, 580), (160-camera, 475), (285-camera, 580)], fill=scenes["roof"])

    # Character shadow and expressive stick-figure actor with a consistent costume.
    draw.ellipse((x-75, 1110, x+85, 1150), fill=(35, 53, 47))
    draw.ellipse((x-48, head_y-48, x+48, head_y+48), fill=(255, 222, 181), outline=ink, width=8)
    # Hair and eyebrows.
    draw.arc((x-47, head_y-57, x+47, head_y+15), 185, 350, fill=(45, 35, 30), width=12)
    eye_y = head_y - 7
    draw.ellipse((x-19, eye_y, x-9, eye_y+12), fill=ink)
    draw.ellipse((x+9, eye_y, x+19, eye_y+12), fill=ink)
    if index in (0, 5):
        draw.arc((x-18, head_y+9, x+18, head_y+36), 195, 345, fill=ink, width=4)
    else:
        draw.arc((x-17, head_y+3, x+17, head_y+27), 5, 175, fill=ink, width=4)

    shoulder_y = head_y + 52
    hip_y = head_y + 225
    draw.line((x, shoulder_y, x, hip_y), fill=(27, 42, 59), width=18)
    draw.line((x, shoulder_y+15, x, hip_y-5), fill=(61, 147, 181), width=11)
    arm = int(42 * math.sin(phase * 2))
    if index in (1, 5):
        draw.line((x, shoulder_y+28, x-62, shoulder_y+100+arm), fill=ink, width=11)
        draw.line((x, shoulder_y+28, x+100, shoulder_y-40-arm), fill=ink, width=11)
    elif index == 3:
        draw.line((x, shoulder_y+28, x-75, shoulder_y+100-arm), fill=ink, width=11)
        draw.line((x, shoulder_y+28, x+78, shoulder_y+95+arm), fill=ink, width=11)
    else:
        draw.line((x, shoulder_y+28, x-88, shoulder_y+110-arm), fill=ink, width=11)
        draw.line((x, shoulder_y+28, x+88, shoulder_y+110+arm), fill=ink, width=11)
    leg = int(34 * math.sin(phase * 2))
    draw.line((x, hip_y, x-62+leg, hip_y+145), fill=ink, width=13)
    draw.line((x, hip_y, x+62-leg, hip_y+145), fill=ink, width=13)
    # Small story cue prop to make actions more readable.
    if index in (1, 4):
        draw.rounded_rectangle((x+65, head_y+115, x+112, head_y+178), radius=8, fill=(239, 187, 77), outline=ink, width=3)

    # Cinematic scene marker, title and high-contrast Malayalam subtitles.
    title_font = get_font(30, bold=True)
    body_font = get_font(31, bold=True)
    draw.rounded_rectangle((28, 30, 692, 124), radius=22, fill=(17, 27, 43), outline=(246, 190, 87), width=3)
    draw.text((48, 54), title, font=title_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=(17, 27, 43))
    draw.rounded_rectangle((515, 142, 680, 190), radius=14, fill=(17, 27, 43))
    draw.text((535, 151), scenes["name"], font=get_font(18, True), fill=(255, 213, 125))
    accent_colors = [(255, 202, 82), (102, 220, 231), (255, 132, 119), (160, 232, 164), (255, 202, 82), (190, 166, 255)]
    accent = accent_colors[index % len(accent_colors)]
    draw.rounded_rectangle((24, 1038, 696, 1238), radius=25, fill=(15, 24, 37), outline=accent, width=4)
    draw.rounded_rectangle((52, 1058, 112, 1067), radius=4, fill=accent)
    rows = wrap_text(draw, line, body_font, 575)
    y = 1087
    for row in rows[:3]:
        draw.text((58, y), row, font=body_font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(10, 15, 23))
        y += 44

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
    # Generate each scene's Malayalam narration separately so visual cuts and subtitles
    # follow the actual spoken duration instead of splitting one long recording evenly.
    scene_audio = []
    for scene_index, line in enumerate(LINES):
        clip = OUT / f"narration_scene_{scene_index + 1:02d}.wav"
        create_voice(line, clip)
        scene_audio.append(clip)

    concat_list = OUT / "audio_concat.txt"
    concat_list.write_text(
        "".join(f"file '{clip.as_posix()}'\n" for clip in scene_audio),
        encoding="utf-8"
    )
    audio = OUT / "narration.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:a", "pcm_s16le", str(audio)
    ], check=True)

    frame_number = 0
    for scene_index, (line, clip) in enumerate(zip(LINES, scene_audio)):
        scene_duration = probe_duration(clip)
        scene_frames = max(int(math.ceil(scene_duration * FPS)), FPS * 2)
        for local_frame in range(scene_frames):
            draw_scene_frame(scene_index, line, TITLE, local_frame, scene_frames, frame_number)
            frame_number += 1
        print(f"Rendered scene {scene_index + 1}/{len(LINES)}: {scene_duration:.1f}s")

    silent_video = OUT / "silent.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS), "-i",
        str(FRAMES / "frame_%06d.png"),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", str(silent_video)
    ], check=True)

    final_video = OUT / "daily_malayalam_stickman.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(silent_video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", "scale=1080:1920:flags=lanczos,setsar=1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-movflags", "+faststart", str(final_video)
    ], check=True)
    print(f"Created 1080x1920 animated video: {final_video} ({frame_number} frames at {FPS} fps)")


if __name__ == "__main__":
    main()
