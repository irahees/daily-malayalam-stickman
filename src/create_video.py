from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
FRAMES = OUT / "frames"
WIDTH, HEIGHT = 720, 1280
FPS = 15

TITLE = ""
LINES: list[str] = []


def generate_story() -> tuple[str, list[str]]:
    """Load the locally selected Malayalam script; no text-generation API is called."""
    story_path = OUT / "story.json"
    if not story_path.is_file():
        raise RuntimeError("Local Malayalam story is missing. Run src/create_brief.py first.")
    try:
        story = json.loads(story_path.read_text(encoding="utf-8"))
        title = str(story["title"]).strip()
        scenes = [str(item).strip() for item in story["scenes"]]
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError("Local Malayalam story JSON is invalid.") from error
    if not title or len(scenes) != 6 or any(not line for line in scenes):
        raise RuntimeError("Story validation failed: expected a title and exactly 6 non-empty scenes.")
    if any(len(line) > 240 for line in scenes):
        raise RuntimeError("Story validation failed: each scene must be 240 characters max.")
    print(f"Loaded offline Malayalam story: {title}")
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


@lru_cache(maxsize=32)
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
    # Smoother cinematic camera drift and a more expressive, continuously moving actor.
    camera = int(16 * math.sin(phase * 0.45) + 7 * math.sin(phase * 0.9))
    bob = int(8 * math.sin(phase * 2) + 2 * math.sin(phase * 4))
    walk = 31 * math.sin(phase * 1.65)
    x = int(350 + 46 * math.sin(phase * 0.72) + walk)
    head_y = 680 + bob
    body_lean = int(8 * math.sin(phase * 1.1))
    action_pulse = (0.5 + 0.5 * math.sin(phase * 1.5))
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
    for radius in range(260, 0, -16):
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

    # Floating dust/firefly particles add depth and motion between scene cuts.
    for particle in range(9):
        px = int((particle * 67 + frame * (1.2 + (particle % 3) * 0.35)) % WIDTH)
        py = int(280 + (particle * 83 + frame * (0.45 + (particle % 2) * 0.2)) % 560)
        radius = 2 + (particle % 3)
        glow = int(125 + 90 * (0.5 + 0.5 * math.sin(phase + particle)))
        draw.ellipse((px-radius, py-radius, px+radius, py+radius), fill=(glow, min(245, glow+22), 170))

    # Polished 2D cartoon host: rounded silhouette, layered hair, expressive face,
    # outlined clothes, hands and shoes. Subtle motion keeps the character alive.
    shadow_width = int(76 + 12 * action_pulse)
    draw.ellipse((x-shadow_width, 1110, x+shadow_width, 1152), fill=(30, 42, 48))
    skin = (224, 157, 112)
    skin_light = (246, 190, 145)
    outline = (38, 35, 43)
    shirt = (37, 116, 146)
    shirt_light = (66, 157, 178)
    trousers = (43, 51, 70)

    # Legs and rounded shoes.
    leg_swing = int(24 * math.sin(phase * 1.65))
    draw.line((x-20, 900, x-38+leg_swing, 1082), fill=outline, width=34)
    draw.line((x+20, 900, x+40-leg_swing, 1082), fill=outline, width=34)
    draw.line((x-20, 900, x-38+leg_swing, 1080), fill=trousers, width=25)
    draw.line((x+20, 900, x+40-leg_swing, 1080), fill=trousers, width=25)
    draw.rounded_rectangle((x-77+leg_swing, 1068, x-20+leg_swing, 1100), radius=14, fill=outline)
    draw.rounded_rectangle((x+18-leg_swing, 1068, x+78-leg_swing, 1100), radius=14, fill=outline)
    draw.rounded_rectangle((x-72+leg_swing, 1065, x-25+leg_swing, 1091), radius=11, fill=(239, 231, 215))
    draw.rounded_rectangle((x+23-leg_swing, 1065, x+73-leg_swing, 1091), radius=11, fill=(239, 231, 215))

    # Neck and shirt torso.
    draw.rounded_rectangle((x-24, 730+bob, x+24, 805+bob), radius=13, fill=outline)
    draw.rounded_rectangle((x-18, 735+bob, x+18, 800+bob), radius=10, fill=skin)
    draw.rounded_rectangle((x-83+body_lean, 780+bob, x+83+body_lean, 950+bob), radius=42, fill=outline)
    draw.rounded_rectangle((x-73+body_lean, 790+bob, x+73+body_lean, 940+bob), radius=35, fill=shirt)
    draw.arc((x-48+body_lean, 788+bob, x+48+body_lean, 852+bob), 5, 175, fill=shirt_light, width=7)
    draw.line((x-48+body_lean, 850+bob, x-60+body_lean, 915+bob), fill=shirt_light, width=4)

    # Arms with rounded sleeves and hands; gestures vary by scene.
    arm_wave = int(28 * math.sin(phase * 1.8))
    if index in (1, 5):
        left_hand = (x-122, 880+arm_wave)
        right_hand = (x+112, 748-arm_wave)
    elif index == 3:
        left_hand = (x-116, 885-arm_wave)
        right_hand = (x+118, 870+arm_wave)
    else:
        left_hand = (x-120, 884-arm_wave)
        right_hand = (x+120, 884+arm_wave)
    for side, hand in ((-1, left_hand), (1, right_hand)):
        shoulder = (x+side*61+body_lean, 815+bob)
        elbow = (int((shoulder[0]+hand[0])/2), int((shoulder[1]+hand[1])/2))
        draw.line((shoulder, elbow), fill=outline, width=35)
        draw.line((shoulder, elbow), fill=shirt, width=25)
        draw.line((elbow, hand), fill=outline, width=27)
        draw.line((elbow, hand), fill=skin, width=18)
        hx, hy = hand
        draw.ellipse((hx-15, hy-15, hx+15, hy+15), fill=outline)
        draw.ellipse((hx-11, hy-11, hx+11, hy+11), fill=skin_light)

    # Ears, face and hair silhouette.
    face_y = 665 + bob
    draw.ellipse((x-66, face_y-8, x-34, face_y+42), fill=outline)
    draw.ellipse((x+34, face_y-8, x+66, face_y+42), fill=outline)
    draw.ellipse((x-60, face_y-12, x+60, face_y+112), fill=outline)
    draw.ellipse((x-53, face_y-7, x+53, face_y+104), fill=skin_light)
    # Hair cap with a softly jagged fringe.
    draw.pieslice((x-60, face_y-36, x+60, face_y+70), 180, 360, fill=outline)
    draw.polygon([
        (x-57, face_y+7), (x-45, face_y-14), (x-29, face_y+2),
        (x-11, face_y-17), (x+7, face_y+1), (x+27, face_y-13),
        (x+47, face_y+8), (x+52, face_y+24), (x-53, face_y+24)
    ], fill=(48, 38, 36))
    # Large animated eyes and eyebrows.
    eye_y = face_y+40
    blink = 0.18 if (int(phase*3) % 19 == 0) else 1.0
    for eye_x in (x-23, x+23):
        draw.ellipse((eye_x-14, eye_y-15*blink, eye_x+14, eye_y+15*blink), fill=(255,255,255), outline=outline, width=4)
        if blink > 0.5:
            pupil_x = eye_x + int(3*math.sin(phase))
            draw.ellipse((pupil_x-6, eye_y-8, pupil_x+6, eye_y+8), fill=(42, 48, 60))
            draw.ellipse((pupil_x-2, eye_y-6, pupil_x+1, eye_y-2), fill=(255,255,255))
        draw.arc((eye_x-17, eye_y-31, eye_x+17, eye_y-12), 195, 345, fill=outline, width=5)
    # Nose and talking mouth; mouth opens rhythmically for a lively narrator.
    draw.ellipse((x-4, face_y+62, x+4, face_y+70), fill=(190, 116, 87))
    mouth_open = int(5 + 5 * (0.5 + 0.5 * math.sin(phase*5)))
    if index in (0, 5):
        draw.ellipse((x-11, face_y+78, x+11, face_y+78+mouth_open*2), fill=(112, 48, 55), outline=outline, width=3)
    else:
        draw.arc((x-14, face_y+72, x+14, face_y+94), 5, 175, fill=(112, 48, 55), width=4)
    draw.ellipse((x-37, face_y+67, x-25, face_y+73), fill=(231, 139, 127))
    draw.ellipse((x+25, face_y+67, x+37, face_y+73), fill=(231, 139, 127))

    # Brief action accents make important beats read clearly even on a phone screen.
    if index in (0, 3, 5) and action_pulse > 0.82:
        draw.arc((x-78, head_y-84, x+78, head_y+72), 205, 330, fill=(255, 219, 132), width=4)
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
    sky.save(FRAMES / f"frame_{output_frame:06d}.jpg", quality=84, optimize=False)

def create_voice_gemini(text: str, destination: Path) -> None:
    """Generate Malayalam narration as WAV using Gemini 3.8 Flash TTS."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from GitHub Actions repository secrets.")

    model = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
    # Charon is an informative narration voice. Malayalam is detected from the
    # transcript; the style request asks for clear, natural Kerala Malayalam.
    payload = {
        "model": model,
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": "Speak clearly and naturally in Malayalam with a warm, engaging Kerala Malayalam narration style. Use a confident, conversational explainer delivery at a moderate pace. Pronounce every Malayalam word accurately. Do not translate, paraphrase, or add any words."
                }]
            }]
        }],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": "Charon"}]}
    }
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "Accept": "application/json"
        },
        method="POST"
    )

    audio_bytes = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                result = json.loads(response.read().decode("utf-8"))
            # Gemini Interactions API returns generated audio inside
            # steps[].content[].data (not output_audio.data).
            encoded = None
            for step in result.get("steps", []):
                for item in step.get("content", []):
                    if item.get("type") == "audio" and item.get("data"):
                        encoded = item["data"]
                        break
                    if item.get("data") and item.get("mime_type", "").startswith("audio/"):
                        encoded = item["data"]
                        break
                if encoded:
                    break
            # Be tolerant of response variants that omit the content type.
            if not encoded:
                for step in result.get("steps", []):
                    for item in step.get("content", []):
                        if item.get("data"):
                            encoded = item["data"]
                            break
                    if encoded:
                        break
            if not encoded:
                raise RuntimeError(
                    "Gemini TTS completed but no audio data was found in steps[].content[].data: "
                    + json.dumps(result, ensure_ascii=False)[:1200]
                )
            import base64
            audio_bytes = base64.b64decode(encoded, validate=True)
            break
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f"Gemini TTS HTTP {error.code}: {details[:1200]}") from error
            delay = min(60, 2 ** (attempt + 1))
            print(f"Gemini TTS temporarily returned HTTP {error.code}; retrying in {delay}s.")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise RuntimeError(f"Gemini TTS connection failed: {error}") from error
            delay = min(30, 2 ** (attempt + 1))
            print(f"Gemini TTS connection issue; retrying in {delay}s.")
            time.sleep(delay)

    if not audio_bytes or len(audio_bytes) < 1024:
        raise RuntimeError("Gemini TTS returned an empty or invalid WAV response.")
    destination.write_bytes(audio_bytes)
    if not destination.exists() or destination.stat().st_size < 1024:
        raise RuntimeError("Gemini TTS WAV file could not be saved.")
    if audio_bytes[:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        raise RuntimeError("Gemini TTS response was not a valid WAV file (RIFF/WAVE header missing).")
    print(f"Gemini TTS audio saved. Model={model}, voice=Charon, bytes={destination.stat().st_size}")


def create_voice(text: str, destination: Path) -> None:
    """Gemini TTS is the sole voice-generation provider."""
    create_voice_gemini(text, destination)

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

    final_video = OUT / "daily_malayalam_stickman.mp4"
    # Encode the image sequence with narration in one pass (avoid a second full video encode).
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS), "-i",
        str(FRAMES / "frame_%06d.jpg"), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", "scale=1080:1920:flags=bicubic,setsar=1",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart", str(final_video)
    ], check=True)
    print(f"Created 1080x1920 animated video: {final_video} ({frame_number} frames at {FPS} fps)")


if __name__ == "__main__":
    main()
