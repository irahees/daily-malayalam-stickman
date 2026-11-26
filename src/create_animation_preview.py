from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "preview_output"
FRAMES = OUT / "frames"
W, H, FPS = 720, 1280, 24
DURATION = 6
TOTAL = FPS * DURATION


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMalayalam[wght].ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for item in candidates:
        if item and Path(item).exists():
            return ImageFont.truetype(item, size)
    return ImageFont.load_default()


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def draw_frame(frame: int) -> Image.Image:
    t = frame / TOTAL
    phase = t * math.tau * 1.4
    img = Image.new("RGB", (W, H), (183, 218, 231))
    d = ImageDraw.Draw(img)

    # Soft sky, distant hills and coconut palms with slow parallax.
    d.rectangle((0, 0, W, H), fill=(185, 220, 232))
    d.ellipse((520, 105, 650, 235), fill=(255, 220, 137))
    d.polygon([(0, 590), (150, 420), (300, 575), (470, 400), (720, 560), (720, 920), (0, 920)], fill=(117, 164, 133))
    d.polygon([(0, 690), (180, 540), (360, 685), (540, 520), (720, 660), (720, 950), (0, 950)], fill=(91, 143, 112))

    # Street and Kerala-style shopfronts.
    d.rectangle((0, 850, W, H), fill=(202, 177, 139))
    d.rectangle((0, 1000, W, H), fill=(105, 119, 105))
    d.line((0, 1080, W, 1080), fill=(241, 221, 173), width=8)
    for x in (34, 505):
        d.rectangle((x, 570, x + 175, 875), fill=(239, 211, 166), outline=(65, 56, 52), width=7)
        d.rectangle((x, 570, x + 175, 635), fill=(165, 54, 43))
        d.rectangle((x + 24, 675, x + 150, 850), fill=(118, 133, 136), outline=(65, 56, 52), width=5)
        for yy in range(700, 845, 28):
            d.line((x + 32, yy, x + 142, yy), fill=(75, 86, 91), width=4)

    # Palm trunks shift slightly to create depth without clutter.
    sway = int(5 * math.sin(phase * 0.5))
    for px in (250, 455):
        d.line((px, 600, px + 14, 285), fill=(106, 75, 48), width=15)
        cx, cy = px + 14, 300
        for ang in (-155, -125, -95, -65, -35, 5):
            rad = math.radians(ang + sway)
            ex = cx + int(105 * math.cos(rad))
            ey = cy + int(58 * math.sin(rad))
            d.line((cx, cy, ex, ey), fill=(49, 112, 72), width=12)
            d.ellipse((ex - 13, ey - 8, ex + 13, ey + 8), fill=(56, 125, 77))

    # Ground shadow and gently eased character bob.
    bob = 8 * math.sin(phase * 1.6)
    step = 12 * math.sin(phase * 1.1)
    cx = 360 + int(18 * math.sin(phase * 0.55))
    shadow = int(70 + 5 * math.sin(phase))
    d.ellipse((cx - shadow, 1090, cx + shadow, 1120), fill=(75, 92, 83))

    # Legs with a small alternating walk cycle.
    leg = int(18 * math.sin(phase * 1.5))
    d.line((cx - 20, 900 + bob, cx - 35 + leg, 1070), fill=(35, 39, 48), width=31)
    d.line((cx + 20, 900 + bob, cx + 36 - leg, 1070), fill=(35, 39, 48), width=31)
    d.line((cx - 20, 900 + bob, cx - 35 + leg, 1070), fill=(48, 54, 68), width=22)
    d.line((cx + 20, 900 + bob, cx + 36 - leg, 1070), fill=(48, 54, 68), width=22)
    d.rounded_rectangle((cx - 75 + leg, 1054, cx - 20 + leg, 1090), radius=13, fill=(34, 37, 42))
    d.rounded_rectangle((cx + 18 - leg, 1054, cx + 76 - leg, 1090), radius=13, fill=(34, 37, 42))

    # Torso and neck.
    d.rounded_rectangle((cx - 22, 720 + bob, cx + 22, 800 + bob), radius=13, fill=(132, 83, 59))
    d.rounded_rectangle((cx - 82, 775 + bob, cx + 82, 950 + bob), radius=38, fill=(38, 35, 43))
    d.rounded_rectangle((cx - 73, 785 + bob, cx + 73, 940 + bob), radius=32, fill=(145, 68, 48))
    d.arc((cx - 48, 790 + bob, cx + 48, 855 + bob), 5, 175, fill=(191, 111, 83), width=6)

    # Alternating explanatory gestures: one hand rises, then returns smoothly.
    gesture = ease((math.sin(phase * 0.75) + 1) / 2)
    for side in (-1, 1):
        shoulder = (cx + side * 58, 815 + int(bob))
        if side == 1:
            hand = (cx + 125, int(760 - 75 * gesture))
        else:
            hand = (cx - 122, int(880 + 15 * math.sin(phase)))
        elbow = ((shoulder[0] + hand[0]) // 2, (shoulder[1] + hand[1]) // 2 + 12)
        d.line((shoulder, elbow), fill=(38, 35, 43), width=34)
        d.line((shoulder, elbow), fill=(145, 68, 48), width=24)
        d.line((elbow, hand), fill=(38, 35, 43), width=27)
        d.line((elbow, hand), fill=(132, 83, 59), width=18)
        d.ellipse((hand[0] - 14, hand[1] - 14, hand[0] + 14, hand[1] + 14), fill=(177, 121, 91), outline=(38, 35, 43), width=3)

    # Head, curly hair, blinking eyes and speaking mouth.
    fy = int(660 + bob)
    d.ellipse((cx - 65, fy - 12, cx + 65, fy + 118), fill=(38, 35, 43))
    d.ellipse((cx - 57, fy - 5, cx + 57, fy + 110), fill=(177, 121, 91))
    for hx, hy, r in ((-43, -10, 24), (-18, -25, 25), (12, -23, 25), (39, -8, 25), (-52, 12, 18), (51, 12, 18)):
        d.ellipse((cx + hx - r, fy + hy - r, cx + hx + r, fy + hy + r), fill=(25, 22, 23))
    d.rectangle((cx - 52, fy + 2, cx + 52, fy + 23), fill=(25, 22, 23))

    blink = 0.12 if frame % 97 in (0, 1, 2) else 1.0
    for ex in (cx - 23, cx + 23):
        d.ellipse((ex - 13, fy + 38 - int(13 * blink), ex + 13, fy + 38 + int(13 * blink)), fill=(255, 255, 255), outline=(38, 35, 43), width=3)
        if blink > 0.5:
            d.ellipse((ex - 4, fy + 33, ex + 4, fy + 43), fill=(42, 48, 60))
    mouth = 5 + int(6 * (0.5 + 0.5 * math.sin(phase * 5)))
    d.ellipse((cx - 10, fy + 78, cx + 10, fy + 78 + mouth), fill=(102, 42, 49), outline=(38, 35, 43), width=2)

    # Clean title and caption safe-area treatment.
    d.rounded_rectangle((28, 32, 692, 132), radius=24, fill=(17, 27, 43), outline=(246, 190, 87), width=3)
    d.text((52, 62), "WHAT IF INTERNET DISAPPEARED?", font=font(25, True), fill=(255, 255, 255))
    d.rounded_rectangle((34, 1140, 686, 1245), radius=22, fill=(15, 24, 37), outline=(102, 220, 231), width=3)
    d.text((58, 1174), "ഒരു ദിവസം ഇന്റർനെറ്റ് ഇല്ലാതായാൽ?", font=font(28, True), fill=(255, 255, 255), stroke_width=1, stroke_fill=(10, 15, 23))
    return img


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("FFmpeg is required.")
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    for frame in range(TOTAL):
        draw_frame(frame).save(FRAMES / f"frame_{frame:04d}.jpg", quality=90)
    target = OUT / "animation_sample_2d.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS), "-i", str(FRAMES / "frame_%04d.jpg"),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(target)
    ], check=True)
    print(f"Preview rendered: {target}")


if __name__ == "__main__":
    main()
