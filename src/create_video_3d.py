from __future__ import annotations
import json, math, os, shutil, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"output"
RAW=OUT/"blender_raw_frames"
FINAL_FRAMES=OUT/"blender_final_frames"
FPS=30
WIDTH,HEIGHT=540,960

def main():
    import create_video
    title,scenes=create_video.generate_story()
    audio=OUT/"narration.wav"
    create_video.create_voice("\n\n".join(scenes),audio)
    duration=create_video.probe_duration(audio)
    weights=[max(len(s.split()),1) for s in scenes]
    total=sum(weights)
    scene_durations=[duration*w/total for w in weights]
    for path in (RAW,FINAL_FRAMES):
        if path.exists(): shutil.rmtree(path)
        path.mkdir(parents=True,exist_ok=True)
    config={"title":title,"scenes":scenes,"scene_durations":scene_durations,"duration":duration,"fps":FPS}
    config_path=OUT/"blender_story_config.json"
    config_path.write_text(json.dumps(config,ensure_ascii=False),encoding="utf-8")
    blender=shutil.which("blender")
    if not blender: raise RuntimeError("Blender executable is missing; refusing to fall back to 2D.")
    env=os.environ.copy()
    env["BLENDER_CONFIG"]=str(config_path)
    env["BLENDER_FRAMES"]=str(RAW)
    subprocess.run([blender,"--background","--factory-startup","--python",str(ROOT/"src/blender_full_renderer.py")],cwd=ROOT,env=env,check=True)
    raw_frames=sorted(RAW.glob("frame_*.png"))
    expected=max(1,int(math.ceil(duration*FPS)))
    if len(raw_frames)<expected-3: raise RuntimeError(f"3D render incomplete: {len(raw_frames)} frames, expected about {expected}.")
    # Malayalam captions are shaped by Pillow RAQM/HarfBuzz, not Blender's basic text renderer.
    from create_video import get_font, draw_text, wrap_text
    title_font=get_font(21,True); body_font=get_font(25,True)
    cumulative=[]; cursor=0.0
    for d in scene_durations:
        cursor+=d; cumulative.append(cursor)
    for i,path in enumerate(raw_frames):
        t=i/FPS
        scene_index=next((j for j,end in enumerate(cumulative) if t<end),len(scenes)-1)
        im=Image.open(path).convert("RGB")
        draw=ImageDraw.Draw(im)
        draw.rounded_rectangle((18,18,522,94),radius=16,fill=(17,27,43),outline=(246,190,87),width=2)
        title_rows=wrap_text(draw,title,title_font,455)
        title_y=30
        for title_row in title_rows[:2]:
            draw_text(draw,(32,title_y),title_row,font=title_font,fill=(255,255,255),stroke_width=1,stroke_fill=(17,27,43))
            title_y+=27
        draw.rounded_rectangle((18,790,522,940),radius=18,fill=(15,24,37),outline=(255,202,82),width=3)
        rows=wrap_text(draw,scenes[scene_index],body_font,450)
        y=815
        for row in rows[:3]:
            draw_text(draw,(38,y),row,font=body_font,fill=(255,255,255),stroke_width=1,stroke_fill=(10,15,23))
            y+=34
        im.save(FINAL_FRAMES/f"frame_{i+1:06d}.jpg",quality=91,subsampling=0,optimize=True)
        if i%150==0: print(f"Captioned 3D frames: {i+1}/{len(raw_frames)}")
    output=OUT/"daily_malayalam_stickman.mp4"
    subprocess.run([
        "ffmpeg","-y","-framerate",str(FPS),"-i",str(FINAL_FRAMES/"frame_%06d.jpg"),"-i",str(audio),
        "-map","0:v:0","-map","1:a:0","-vf","scale=1080:1920:flags=lanczos,setsar=1",
        "-c:v","libx264","-preset","medium","-crf","20","-r","30","-fps_mode","cfr",
        "-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(output)
    ],check=True)
    probe=subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_type,width,height","-show_entries","format=duration","-of","json",str(output)],check=True,capture_output=True,text=True)
    info=json.loads(probe.stdout)
    video=next((s for s in info["streams"] if s.get("codec_type")=="video"),{})
    audio_stream=next((s for s in info["streams"] if s.get("codec_type")=="audio"),None)
    if video.get("width")!=1080 or video.get("height")!=1920 or not audio_stream:
        raise RuntimeError("Final 3D MP4 validation failed: expected 1080x1920 video and an audio stream.")
    print(f"FULL 3D VIDEO READY: {output}; duration={info['format'].get('duration')}s; frames={len(raw_frames)}; Malayalam captions and narration included.")

if __name__=="__main__": main()
