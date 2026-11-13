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


def draw_story_background(draw, index: int, line: str, title: str, frame: int, phase: float, camera: int) -> str:
    """Draw a story-matched illustrated location and meaningful props for each scene."""
    text = (title + " " + line).lower()
    ink = (48, 39, 42)
    cream = (255, 239, 202)
    gold = any(k in text for k in ("സ്വർണ്ണ", "സ്വർണം", "പവൻ", "gold", "jewellery", "ആഭരണം"))
    battery = any(k in text for k in ("ബാറ്ററി", "ചാർജ്", "ഫോൺ", "മൊബൈൽ"))
    internet = any(k in text for k in ("ഇന്റർനെറ്റ്", "നെറ്റ്വർക്ക്", "ഓൺലൈൻ", "ഡിജിറ്റൽ"))
    rain = any(k in text for k in ("മഴ", "മഴത്തുള്ളി", "വെള്ളം", "മണ്ണ്", "കടൽ"))
    fuel = any(k in text for k in ("പെട്രോൾ", "ഇന്ധന", "വാഹന", "യാത്ര"))
    shop = any(k in text for k in ("കട", "വില", "വാങ്ങ", "സാധന", "വിതരണ"))
    night = index == 5

    # Warm illustrated environments with visible floors, wall depth and scene-specific architecture.
    if gold:
        labels = ["NEWS STUDIO", "GOLD SHOP", "PRICE BOARD", "GOLD LOAN BANK", "HOME", "THE BIG QUESTION"]
        if index == 0:
            draw.rectangle((0, 0, 720, 1280), fill=(31, 35, 58))
            draw.rectangle((0, 780, 720, 1280), fill=(72, 48, 47))
            draw.rounded_rectangle((45, 220, 675, 690), radius=22, fill=(12, 27, 58), outline=(241, 177, 67), width=8)
            draw.rectangle((65, 240, 655, 310), fill=(192, 40, 32))
            draw.text((92, 254), "BREAKING NEWS", font=get_font(34, True), fill=(255,255,255))
            draw.text((90, 355), "1 പവൻ = ₹1 ?", font=get_font(48, True), fill=(255,220,90), stroke_width=2, stroke_fill=(50,20,20))
            draw.line((100, 520, 620, 520), fill=(245,190,60), width=6)
            draw.text((130, 560), "GOLD PRICE SHOCK", font=get_font(28, True), fill=cream)
            # News desk and microphone.
            draw.rounded_rectangle((90, 820, 630, 1010), radius=18, fill=(117,65,43), outline=ink, width=7)
            draw.rectangle((115, 845, 605, 890), fill=(163,91,55))
            draw.ellipse((540, 745, 570, 775), fill=(220,220,220), outline=ink, width=4)
            draw.line((555, 770, 555, 825), fill=ink, width=8)
        elif index in (1, 2):
            draw.rectangle((0,0,720,1280), fill=(128,47,37))
            draw.rectangle((0,900,720,1280), fill=(91,47,39))
            draw.rectangle((48,230,672,870), fill=(153,55,43), outline=(68,35,32), width=8)
            draw.rectangle((72,260,648,835), fill=(88,31,33), outline=(238,177,79), width=6)
            for row in range(2):
                y=365+row*225
                draw.rectangle((95,y,625,y+12), fill=(232,173,68))
                for col in range(5):
                    cx=145+col*108
                    draw.arc((cx-28,y-92,cx+28,y+12), 0, 180, fill=(255,211,112), width=8)
                    draw.ellipse((cx-16,y-86,cx+16,y-54), fill=(255,209,104), outline=(80,42,25), width=3)
                    draw.line((cx,y-53,cx,y-5), fill=(255,211,112), width=6)
            draw.rounded_rectangle((80,875,640,1010), radius=18, fill=(121,69,43), outline=ink, width=7)
            if index == 2:
                draw.rounded_rectangle((185,105,535,210), radius=15, fill=(255,239,202), outline=(70,42,30), width=5)
                draw.text((225,130), "1 പവൻ = ₹1", font=get_font(38,True), fill=(174,35,28))
        elif index == 3:
            draw.rectangle((0,0,720,1280), fill=(191,211,219))
            draw.rectangle((0,880,720,1280), fill=(116,92,73))
            draw.rectangle((45,190,675,880), fill=(228,225,207), outline=ink, width=7)
            draw.rectangle((75,230,645,310), fill=(196,47,34))
            draw.text((180,246), "GOLD LOAN", font=get_font(42,True), fill=(255,229,156))
            draw.rectangle((90,430,630,490), fill=(125,77,48), outline=ink, width=5)
            draw.rectangle((125,490,160,865), fill=(96,59,42))
            draw.rectangle((560,490,595,865), fill=(96,59,42))
            draw.rounded_rectangle((220,560,500,720), radius=12, fill=(250,247,233), outline=ink, width=5)
            draw.text((255,590), "LOAN VALUE", font=get_font(26,True), fill=(65,65,65))
            draw.text((280,635), "₹1 ?", font=get_font(48,True), fill=(186,38,30))
            draw.ellipse((530,350,620,440), fill=(83,91,102), outline=ink, width=6)
            draw.line((575,395,575,350), fill=(45,49,58), width=8)
            draw.line((575,395,615,415), fill=(45,49,58), width=8)
        elif index == 4:
            draw.rectangle((0,0,720,1280), fill=(247,224,180))
            draw.rectangle((0,900,720,1280), fill=(145,85,55))
            draw.rectangle((70,260,650,900), fill=(255,241,211), outline=ink, width=7)
            draw.rectangle((120,340,310,560), fill=(111,166,194), outline=ink, width=7)
            draw.line((215,340,215,560), fill=ink, width=5)
            draw.line((120,450,310,450), fill=ink, width=5)
            draw.rounded_rectangle((390,590,600,790), radius=18, fill=(128,75,49), outline=ink, width=6)
            draw.text((420,635), "SAVINGS", font=get_font(26,True), fill=cream)
            draw.ellipse((455,690,535,770), fill=(255,205,76), outline=ink, width=5)
            draw.text((476,706), "₹", font=get_font(42,True), fill=(80,45,20))
        else:
            draw.rectangle((0,0,720,1280), fill=(255,192,65))
            for k in range(9):
                xx=360+k*100*math.cos(k*math.tau/9)
                yy=600+k*100*math.sin(k*math.tau/9)
                draw.line((360,610,xx,yy), fill=(255,226,139), width=8)
            draw.ellipse((245,365,475,595), fill=(255,220,120), outline=(108,75,36), width=9)
            draw.text((295,410), "1", font=get_font(130,True), fill=(122,74,25))
            draw.rounded_rectangle((120,760,600,920), radius=25, fill=(255,247,224), outline=ink, width=6)
            draw.text((170,795), "നിങ്ങൾ എന്ത് വാങ്ങും?", font=get_font(34,True), fill=(70,45,35))
        return labels[index]

    if battery:
        labels=["PHONE PROBLEM","SCREEN BRIGHTNESS","GAMING & VIDEO","LOW SIGNAL","BATTERY SETTINGS","QUICK TIP"]
        draw.rectangle((0,0,720,1280), fill=(235,220,191))
        draw.rectangle((0,900,720,1280), fill=(130,85,58))
        if index in (0,1,2,5):
            # Oversized smartphone with a readable battery illustration.
            draw.rounded_rectangle((220,250,500,850), radius=42, fill=(32,38,48), outline=(20,20,25), width=10)
            draw.rounded_rectangle((242,290,478,810), radius=20, fill=(177,211,224))
            draw.rounded_rectangle((305,325,415,380), radius=12, fill=(242,245,238), outline=ink, width=3)
            draw.rectangle((330,342,390,363), fill=(65,174,91))
            if index == 1:
                draw.ellipse((290,470,430,610), fill=(255,214,93), outline=ink, width=5)
                draw.text((330,510), "☀", font=get_font(62,True), fill=(110,75,35))
            elif index == 2:
                draw.rectangle((260,430,460,650), fill=(50,78,130))
                draw.polygon([(330,480),(330,600),(415,540)], fill=(255,255,255))
            elif index == 5:
                draw.text((280,500), "BATTERY", font=get_font(28,True), fill=(35,55,65))
                draw.text((320,560), "100%", font=get_font(48,True), fill=(35,125,70))
        elif index == 3:
            draw.line((560,300,560,890), fill=(65,65,68), width=14)
            for yy in (390,470,550):
                draw.arc((410,yy-70,710,yy+70),200,340,fill=(62,130,180),width=9)
            draw.ellipse((530,260,590,320), fill=(220,70,60), outline=ink, width=4)
        else:
            draw.rounded_rectangle((100,420,620,760), radius=24, fill=(47,65,79), outline=ink, width=6)
            draw.text((165,480), "BATTERY USAGE", font=get_font(36,True), fill=cream)
            for k,ww in enumerate((330,250,180)):
                yy=560+k*55
                draw.rounded_rectangle((165,yy,165+ww,yy+22), radius=10, fill=(77,190,125))
        return labels[index]

    if internet:
        labels=["NO INTERNET","MESSAGES","ONLINE PAYMENT","NETWORK TOWER","OFFLINE PLAN","STAY CONNECTED"]
        draw.rectangle((0,0,720,1280), fill=(193,218,231))
        draw.rectangle((0,900,720,1280), fill=(111,137,103))
        if index in (0,1,2,4,5):
            draw.rounded_rectangle((210,250,510,830), radius=40, fill=(32,38,48), outline=ink, width=8)
            draw.rounded_rectangle((232,290,488,790), radius=20, fill=(235,242,235))
            if index == 1:
                for k in range(3):
                    draw.rounded_rectangle((260,390+k*95,450,445+k*95), radius=15, fill=(130,190,220))
            elif index == 2:
                draw.text((285,420), "UPI", font=get_font(70,True), fill=(40,120,90))
                draw.text((280,540), "₹ 250", font=get_font(45,True), fill=(45,55,65))
            else:
                draw.text((275,430), "OFFLINE", font=get_font(35,True), fill=(45,65,80))
                draw.line((280,540,440,540), fill=(205,70,60), width=8)
        elif index == 3:
            draw.line((550,250,550,900), fill=(62,67,75), width=14)
            for yy in (390,500,610):
                draw.arc((390,yy-90,710,yy+90),200,340,fill=(55,135,190),width=10)
        else:
            draw.rectangle((80,420,640,800), fill=(220,235,235), outline=ink, width=6)
        return labels[index]

    if rain:
        labels=["RAIN CLOUD","ROOFTOP","SOIL","GROUNDWATER","RIVER","SAVE WATER"]
        draw.rectangle((0,0,720,1280), fill=(164,202,220))
        draw.rectangle((0,900,720,1280), fill=(107,139,91))
        if index == 0:
            for cx in (210,330,450):
                draw.ellipse((cx-100,330,cx+80,490), fill=(90,112,132))
            for k in range(9):
                xx=100+k*65
                draw.line((xx,510,xx-18,590), fill=(60,135,205), width=8)
        elif index == 1:
            draw.rectangle((90,450,630,850), fill=(225,188,137), outline=ink, width=6)
            draw.polygon([(50,470),(360,250),(670,470)], fill=(150,72,50), outline=ink)
            for k in range(5):
                xx=150+k*95
                draw.line((xx,470,xx-15,560), fill=(70,150,210), width=7)
        elif index in (2,3):
            draw.rectangle((0,500,720,910), fill=(116,78,50))
            for k in range(8):
                xx=40+k*90
                draw.ellipse((xx,620+(k%2)*65,xx+55,675+(k%2)*65), fill=(83,58,40))
            if index == 3:
                draw.rectangle((0,760,720,900), fill=(67,143,190))
                for k in range(7):
                    draw.arc((k*110,770,k*110+90,815),0,180,fill=(185,225,240),width=4)
        elif index == 4:
            draw.polygon([(0,600),(180,540),(360,620),(540,550),(720,600),(720,950),(0,950)], fill=(55,142,188))
            for k in range(8):
                xx=(k*97+frame*2)%720
                draw.arc((xx,700,xx+90,730),0,180,fill=(190,226,238),width=4)
        else:
            draw.ellipse((210,330,510,630), fill=(77,167,209), outline=ink, width=8)
            draw.text((290,420), "SAVE", font=get_font(58,True), fill=(255,255,255))
        return labels[index]

    if fuel:
        labels=["PETROL PUMP","FUEL DELIVERY","TRANSPORT","ELECTRIC VEHICLE","SUPPLY CHAIN","YOUR CHOICE"]
        draw.rectangle((0,0,720,1280), fill=(202,218,221))
        draw.rectangle((0,900,720,1280), fill=(87,100,88))
        if index in (0,1,2,3,4):
            draw.rectangle((65,300,655,850), fill=(235,230,208), outline=ink, width=7)
            draw.rectangle((65,300,655,390), fill=(194,42,35))
            draw.text((170,320), "FUEL STATION", font=get_font(38,True), fill=(255,238,190))
            draw.rounded_rectangle((180,470,340,760), radius=20, fill=(52,62,70), outline=ink, width=6)
            draw.rectangle((210,510,310,600), fill=(90,180,190))
            draw.line((340,560,440,680), fill=ink, width=12)
            draw.rounded_rectangle((430,650,485,820), radius=14, fill=(194,48,38), outline=ink, width=5)
        return labels[index]

    if shop:
        # Six distinct story beats for a shop/supply-chain story. Keep the same
        # simple outlined 2D-cartoon language as the existing renderer.
        labels=["CLOSED STREET SHOP","DAILY ESSENTIALS","WAREHOUSE","DELIVERY TRUCK","SUPPLY CHAIN","AT HOME"]
        draw.rectangle((0,0,720,1280), fill=(244,216,173))
        draw.rectangle((0,900,720,1280), fill=(142,94,58))
        if index == 0:
            # Kerala street with a closed rolling shutter and signboard.
            draw.rectangle((0,610,720,930), fill=(178,197,183))
            draw.rectangle((65,280,655,840), fill=(236,205,157), outline=ink, width=8)
            draw.rectangle((65,280,655,390), fill=(180,48,38), outline=ink, width=5)
            draw.text((205,310), "LOCAL SHOP", font=get_font(38,True), fill=(255,239,196))
            draw.rectangle((125,420,595,790), fill=(132,139,145), outline=ink, width=7)
            for yy in range(455,780,38):
                draw.line((140,yy,580,yy), fill=(75,83,91), width=5)
            draw.rounded_rectangle((260,800,460,850), radius=12, fill=(86,55,39), outline=ink, width=5)
        elif index == 1:
            # Grocery interior: shelves and essential goods.
            draw.rectangle((45,230,675,890), fill=(250,235,205), outline=ink, width=7)
            for yy in (430,635,825):
                draw.rectangle((85,yy,635,yy+16), fill=(105,65,42), outline=ink, width=3)
            goods=[(226,102,63),(87,160,99),(234,186,72),(105,151,190)]
            for row,yy in enumerate((340,545,735)):
                for col in range(6):
                    xx=112+col*84
                    draw.rounded_rectangle((xx,yy,xx+54,yy+82), radius=9, fill=goods[(row+col)%4], outline=ink, width=4)
            draw.ellipse((475,260,575,360), fill=(255,242,205), outline=ink, width=4)
            draw.text((490,286), "MILK", font=get_font(20,True), fill=(60,70,75))
        elif index == 2:
            # Warehouse racks and stacked cartons.
            draw.rectangle((40,250,680,890), fill=(207,221,224), outline=ink, width=7)
            draw.rectangle((65,300,655,350), fill=(83,100,111))
            for xx in (100,320,540):
                draw.rectangle((xx,360,xx+18,860), fill=(77,83,88))
            for row,yy in enumerate((390,600,790)):
                for col in range(3):
                    xx=125+col*165
                    draw.rectangle((xx,yy,xx+125,yy+115), fill=[(207,151,91),(184,119,75),(222,178,112)][(row+col)%3], outline=ink, width=5)
                    draw.line((xx+62,yy,xx+62,yy+115), fill=(119,78,48), width=3)
        elif index == 3:
            # Delivery truck on a road.
            draw.rectangle((0,700,720,930), fill=(89,105,100))
            draw.line((0,815,720,815), fill=(245,222,151), width=8)
            draw.rounded_rectangle((90,490,475,760), radius=28, fill=(74,145,176), outline=ink, width=8)
            draw.rectangle((475,565,615,760), fill=(220,91,66), outline=ink, width=8)
            draw.polygon([(500,585),(575,585),(600,650),(500,650)], fill=(184,224,233), outline=ink)
            for cx in (205,525):
                draw.ellipse((cx-52,720,cx+52,824), fill=(38,43,48), outline=ink, width=5)
                draw.ellipse((cx-23,749,cx+23,795), fill=(220,220,210), outline=ink, width=4)
            draw.text((170,575), "DELIVERY", font=get_font(30,True), fill=(255,255,255))
        elif index == 4:
            # Connected supply chain: warehouse, vehicle and storefront.
            draw.rectangle((55,340,250,660), fill=(215,178,127), outline=ink, width=6)
            draw.polygon([(35,355),(150,260),(270,355)], fill=(153,83,57), outline=ink)
            for xx in (90,155):
                draw.rectangle((xx,435,xx+48,510), fill=(191,133,82), outline=ink, width=3)
            draw.rounded_rectangle((300,445,435,560), radius=18, fill=(72,139,169), outline=ink, width=6)
            draw.ellipse((320,535,365,580), fill=(45,48,52), outline=ink, width=4)
            draw.ellipse((405,535,450,580), fill=(45,48,52), outline=ink, width=4)
            draw.rectangle((500,360,665,665), fill=(235,205,157), outline=ink, width=6)
            draw.rectangle((500,360,665,425), fill=(180,48,38))
            draw.text((515,378), "SHOP", font=get_font(25,True), fill=(255,239,196))
            draw.line((260,495,300,495), fill=(58,119,89), width=9)
            draw.polygon([(292,480),(312,495),(292,510)], fill=(58,119,89))
            draw.line((450,495,500,495), fill=(58,119,89), width=9)
            draw.polygon([(492,480),(512,495),(492,510)], fill=(58,119,89))
        else:
            # Home kitchen counter with everyday essentials.
            draw.rectangle((55,260,665,900), fill=(255,241,211), outline=ink, width=7)
            draw.rectangle((95,690,625,790), fill=(139,83,53), outline=ink, width=5)
            draw.rectangle((135,510,230,680), fill=(238,230,205), outline=ink, width=4)
            draw.text((145,565), "RICE", font=get_font(22,True), fill=(65,65,60))
            draw.rounded_rectangle((285,545,380,680), radius=14, fill=(239,239,223), outline=ink, width=4)
            draw.text((302,590), "MILK", font=get_font(22,True), fill=(65,65,60))
            draw.ellipse((445,565,545,665), fill=(217,67,55), outline=ink, width=4)
            draw.ellipse((535,580,610,655), fill=(88,155,82), outline=ink, width=4)
        return labels[index]

    # General scene-specific fallback: indoor room, street, classroom, or outdoor landscape.
    labels=["INTRO","EXPLANATION","HOW IT WORKS","REAL-LIFE EFFECT","SOLUTION","FINAL QUESTION"]
    if index in (0,1,2):
        draw.rectangle((0,0,720,1280), fill=(239,219,181))
        draw.rectangle((0,900,720,1280), fill=(137,91,60))
        draw.rectangle((65,230,655,900), fill=(250,238,210), outline=ink, width=7)
        draw.rectangle((105,300,300,520), fill=(133,184,204), outline=ink, width=6)
        draw.line((200,300,200,520), fill=ink, width=4)
        draw.line((105,410,300,410), fill=ink, width=4)
        draw.rounded_rectangle((365,610,600,790), radius=15, fill=(139,83,53), outline=ink, width=5)
    else:
        draw.rectangle((0,0,720,1280), fill=(170,207,222))
        draw.rectangle((0,900,720,1280), fill=(89,135,92))
        draw.polygon([(0,780),(150,660),(310,760),(500,640),(720,760),(720,930),(0,930)], fill=(104,153,110))
    return labels[index]


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

    sky = Image.new("RGB", (WIDTH, HEIGHT), (238, 218, 185))
    draw = ImageDraw.Draw(sky)
    scene_label = draw_story_background(draw, index, line, title, frame, phase, camera)

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
    # Six distinct character identities. Each scene keeps its own face, hair and outfit
    # stable across every frame, while the acting/movement remains animated.
    character_styles = [
        {"skin": (224,157,112), "light": (246,190,145), "shirt": (37,116,146), "accent": (66,157,178), "pants": (43,51,70), "hair": (48,38,36), "hair_style": 0, "face": 0},
        {"skin": (170,112,78), "light": (205,148,111), "shirt": (151,73,53), "accent": (218,132,91), "pants": (61,57,67), "hair": (31,27,26), "hair_style": 1, "face": 1},
        {"skin": (239,190,145), "light": (255,215,178), "shirt": (74,111,74), "accent": (132,169,104), "pants": (65,75,94), "hair": (91,57,37), "hair_style": 2, "face": 2},
        {"skin": (133,86,62), "light": (177,123,93), "shirt": (117,79,151), "accent": (174,135,206), "pants": (48,55,76), "hair": (27,24,25), "hair_style": 3, "face": 1},
        {"skin": (205,151,111), "light": (239,190,148), "shirt": (191,139,45), "accent": (237,190,81), "pants": (74,63,53), "hair": (75,48,32), "hair_style": 4, "face": 0},
        {"skin": (111,72,54), "light": (157,107,82), "shirt": (52,111,102), "accent": (93,165,147), "pants": (40,49,64), "hair": (24,23,26), "hair_style": 5, "face": 2},
    ]
    style = character_styles[index % len(character_styles)]
    skin, skin_light = style["skin"], style["light"]
    outline = (38, 35, 43)
    shirt, shirt_light, trousers = style["shirt"], style["accent"], style["pants"]
    hair_colour = style["hair"]

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
    face_variant = style["face"]
    face_left = x - (57 if face_variant == 1 else 53)
    face_right = x + (57 if face_variant == 1 else 53)
    draw.ellipse((x-66, face_y-8, x-34, face_y+42), fill=outline)
    draw.ellipse((x+34, face_y-8, x+66, face_y+42), fill=outline)
    if face_variant == 0:
        draw.rounded_rectangle((face_left, face_y-12, face_right, face_y+105), radius=39, fill=outline)
        draw.rounded_rectangle((face_left+7, face_y-6, face_right-7, face_y+98), radius=34, fill=skin_light)
    elif face_variant == 1:
        draw.ellipse((face_left, face_y-12, face_right, face_y+112), fill=outline)
        draw.ellipse((face_left+7, face_y-6, face_right-7, face_y+105), fill=skin_light)
    else:
        draw.ellipse((face_left-3, face_y-12, face_right+3, face_y+108), fill=outline)
        draw.ellipse((face_left+5, face_y-6, face_right-5, face_y+101), fill=skin_light)

    # Scene-specific hairstyles: short fringe, curls, side-part, long hair, bun and afro.
    hair_style = style["hair_style"]
    if hair_style == 0:
        draw.pieslice((x-60, face_y-42, x+60, face_y+70), 180, 360, fill=hair_colour)
        draw.polygon([(x-57,face_y+8),(x-44,face_y-16),(x-28,face_y+3),(x-10,face_y-19),
                      (x+8,face_y+1),(x+27,face_y-14),(x+48,face_y+8),(x+52,face_y+24),
                      (x-53,face_y+24)], fill=hair_colour)
    elif hair_style == 1:
        for hx,hy,rad in ((-43,-10,24),(-18,-25,25),(12,-23,25),(39,-8,25),(-52,12,18),(51,12,18)):
            draw.ellipse((x+hx-rad,face_y+hy-rad,x+hx+rad,face_y+hy+rad),fill=hair_colour)
        draw.rectangle((x-52,face_y+2,x+52,face_y+24),fill=hair_colour)
    elif hair_style == 2:
        draw.pieslice((x-59,face_y-42,x+59,face_y+65),180,360,fill=hair_colour)
        draw.polygon([(x-58,face_y+8),(x-38,face_y-22),(x-4,face_y-29),
                      (x+34,face_y-16),(x+55,face_y+8),(x+48,face_y+23),(x-52,face_y+23)],fill=hair_colour)
        draw.arc((x-8,face_y-42,x+58,face_y+25),190,300,fill=(125,83,53),width=5)
    elif hair_style == 3:
        draw.pieslice((x-63,face_y-45,x+63,face_y+72),180,360,fill=hair_colour)
        draw.rounded_rectangle((x-62,face_y+4,x-38,face_y+125),radius=12,fill=hair_colour)
        draw.rounded_rectangle((x+38,face_y+4,x+62,face_y+125),radius=12,fill=hair_colour)
        draw.polygon([(x-60,face_y+10),(x-38,face_y-24),(x,face_y-34),(x+43,face_y-15),
                      (x+60,face_y+15),(x+48,face_y+28),(x-52,face_y+28)],fill=hair_colour)
    elif hair_style == 4:
        draw.pieslice((x-58,face_y-39,x+58,face_y+68),180,360,fill=hair_colour)
        draw.ellipse((x+22,face_y-52,x+68,face_y-6),fill=hair_colour)
        draw.polygon([(x-56,face_y+12),(x-35,face_y-17),(x-10,face_y-23),
                      (x+19,face_y-13),(x+50,face_y+11),(x+49,face_y+25),(x-52,face_y+25)],fill=hair_colour)
    else:
        for hx,hy,rad in ((-42,-14,25),(-20,-34,26),(8,-37,28),(36,-24,25),(52,-1,22),(-53,8,21)):
            draw.ellipse((x+hx-rad,face_y+hy-rad,x+hx+rad,face_y+hy+rad),fill=hair_colour)
        draw.rectangle((x-48,face_y-4,x+48,face_y+24),fill=hair_colour)
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
    draw.text((535, 151), scene_label, font=get_font(18, True), fill=(255, 213, 125))
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
                    "style": "Speak clearly and naturally in Malayalam with a warm, engaging Kerala Malayalam narration style. Use a confident, conversational explainer delivery at a moderate pace. Pronounce every Malayalam word accurately. Treat each paragraph as the next scene and make a short natural pause between paragraphs. Do not translate, paraphrase, or add any words."
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


def create_voice_elevenlabs(text: str, destination: Path) -> None:
    """Secondary Malayalam narration provider, used only if Gemini is unavailable."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        raise RuntimeError(
            "Gemini TTS failed and ElevenLabs fallback is not configured: "
            "ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID repository secrets are required."
        )

    import urllib.parse
    url = "https://api.elevenlabs.io/v1/text-to-speech/" + urllib.parse.quote(voice_id, safe="")
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.75}
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "xi-api-key": api_key
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            audio_bytes = response.read()
    except urllib.error.HTTPError as error:
        # Do not print response bodies; they may contain provider diagnostics.
        raise RuntimeError(f"ElevenLabs fallback HTTP {error.code}.") from error
    if not audio_bytes or len(audio_bytes) < 1024:
        raise RuntimeError("ElevenLabs fallback returned empty or invalid audio.")

    mp3_path = destination.with_suffix(".elevenlabs.mp3")
    try:
        mp3_path.write_bytes(audio_bytes)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3_path), "-ac", "1", "-ar", "24000", str(destination)],
            check=True, capture_output=True, text=True
        )
    finally:
        if mp3_path.exists():
            mp3_path.unlink()
    if not destination.is_file() or destination.stat().st_size < 1024:
        raise RuntimeError("ElevenLabs audio conversion did not produce a valid WAV file.")
    with destination.open("rb") as audio_file:
        header = audio_file.read(12)
    if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise RuntimeError("ElevenLabs fallback output is not a valid WAV file.")
    print(f"ElevenLabs fallback audio saved. Model=eleven_multilingual_v2, bytes={destination.stat().st_size}")


def create_voice(text: str, destination: Path) -> None:
    """Use Gemini first; use ElevenLabs only after a retryable Gemini failure."""
    try:
        create_voice_gemini(text, destination)
    except RuntimeError as error:
        message = str(error)
        retryable = (
            "Gemini TTS HTTP 429" in message
            or any(f"Gemini TTS HTTP {status}" in message for status in (500, 502, 503, 504))
            or "Gemini TTS connection failed" in message
        )
        if not retryable:
            raise
        print("Gemini TTS unavailable after retries; attempting configured ElevenLabs secondary provider.")
        create_voice_elevenlabs(text, destination)

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
    # One Gemini TTS call for the complete six-scene narration. Paragraph breaks
    # encourage a natural pause between scenes while keeping the daily request count low.
    narration_text = "\n\n".join(LINES)
    audio = OUT / "narration.wav"
    create_voice(narration_text, audio)
    total_duration = probe_duration(audio)

    # Estimate each scene's visual duration from its spoken word count. The single
    # narration track remains continuous; this avoids six separate TTS API requests.
    scene_weights = [max(len(line.split()), 1) for line in LINES]
    total_weight = sum(scene_weights)
    scene_durations = [total_duration * weight / total_weight for weight in scene_weights]

    frame_number = 0
    for scene_index, (line, scene_duration) in enumerate(zip(LINES, scene_durations)):
        scene_frames = max(int(math.ceil(scene_duration * FPS)), FPS * 2)
        for local_frame in range(scene_frames):
            draw_scene_frame(scene_index, line, TITLE, local_frame, scene_frames, frame_number)
            frame_number += 1
        print(f"Rendered scene {scene_index + 1}/{len(LINES)}: estimated {scene_duration:.1f}s")

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
