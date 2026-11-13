from __future__ import annotations
import json, shutil
from pathlib import Path
from create_brief import STORIES
import create_video

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
BATCH = OUT / "batch"

def main():
    if len(STORIES) < 7:
        raise RuntimeError("Seven scripts are required for a weekly batch.")
    BATCH.mkdir(parents=True, exist_ok=True)
    for old in BATCH.iterdir():
        shutil.rmtree(old) if old.is_dir() else old.unlink()
    for i, story in enumerate(STORIES[:7], 1):
        story_path = OUT / "story.json"
        story_path.write_text(json.dumps({"title": story["title"], "scenes": story["scenes"]}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Generating video {i}/7: {story['title']}")
        create_video.main()
        src = OUT / "daily_malayalam_stickman.mp4"
        if not src.is_file() or src.stat().st_size < 100_000:
            raise RuntimeError(f"Video {i} failed validation.")
        shutil.copy2(src, BATCH / f"{i:02d}.mp4")
        shutil.copy2(story_path, BATCH / f"{i:02d}.json")
    if len(list(BATCH.glob("*.mp4"))) != 7:
        raise RuntimeError("The seven-video batch is incomplete.")
    print("Seven-video batch generated successfully.")

if __name__ == "__main__":
    main()
