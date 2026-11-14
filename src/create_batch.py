from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from create_brief import STORIES
import create_video

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
BATCH = OUT / "batch"
TRACKER = ROOT / "tracking" / "07_tracker.csv"
BATCH_SIZE = 6
IST = ZoneInfo("Asia/Kolkata")
TRACKER_COLUMNS = [
    "batch_date_ist", "video", "platform", "title",
    "scheduled_date_ist", "scheduled_time_ist", "status", "buffer_post_id",
    "views", "watch_time_seconds", "average_watch_time_seconds", "reach",
    "shares", "sends", "saves", "follows", "notes",
]


def hashtags_for(story: dict) -> list[str]:
    text = " ".join((str(story.get("topic", "")), str(story.get("title", "")))).lower()
    tags = ["#Malayalam", "#MalayalamShorts", "#Kerala"]
    if any(word in text for word in ("ഫോൺ", "ബാറ്ററി", "ഇന്റർനെറ്റ്", "മൊബൈൽ", "ഡിജിറ്റൽ")):
        tags.append("#MalayalamTech")
    elif any(word in text for word in ("മഴ", "മണ്ണ്", "കടൽ", "വെള്ളം")):
        tags.append("#KeralaNature")
    elif any(word in text for word in ("കട", "പെട്രോൾ", "പണം", "രൂപ")):
        tags.append("#KeralaLife")
    else:
        tags.append("#StickmanAnimation")
    return tags[:4]


def build_metadata(story: dict, batch_date: str) -> dict:
    title = str(story["title"]).strip()
    hook = str(story["hook"]).strip()
    scenes = list(story["scenes"])
    closing = str(scenes[-1]).strip() if scenes else "നിങ്ങളുടെ അഭിപ്രായം കമന്റിൽ പറയൂ."
    tags = hashtags_for(story)
    base_caption = f"{hook}\n\n{title}\n\n{closing}"
    instagram_caption = f"{base_caption}\n\n{' '.join(tags)} #Reels"
    youtube_description = f"{base_caption}\n\n{' '.join(tags)} #Shorts"
    seo_keywords = list(dict.fromkeys([
        "Malayalam Shorts",
        "Malayalam stickman animation",
        "Malayalam explainer",
        "Kerala",
        str(story.get("topic", "")).strip(),
        title,
    ]))
    return {
        "batch_date_ist": batch_date,
        "topic": story.get("topic", ""),
        "angle": story.get("angle", ""),
        "hook": hook,
        "title": title,
        "scenes": scenes,
        "caption": base_caption,
        "instagram_caption": instagram_caption,
        "youtube_description": youtube_description,
        "hashtags": tags,
        "seo_keywords": seo_keywords,
    }


def read_tracker() -> list[dict]:
    TRACKER.parent.mkdir(parents=True, exist_ok=True)
    if not TRACKER.exists():
        return []
    with TRACKER.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != TRACKER_COLUMNS:
            raise RuntimeError("tracking/07_tracker.csv has an unexpected schema; refusing to overwrite history.")
        return list(reader)


def write_tracker(rows: list[dict]) -> None:
    with TRACKER.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRACKER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if len(STORIES) < BATCH_SIZE:
        raise RuntimeError(f"At least {BATCH_SIZE} distinct scripts are required.")
    now_ist = datetime.now(IST)
    batch_date = now_ist.date().isoformat()
    start = now_ist.date().toordinal() % len(STORIES)
    selected_stories = [STORIES[(start + offset) % len(STORIES)] for offset in range(BATCH_SIZE)]

    BATCH.mkdir(parents=True, exist_ok=True)
    for old in BATCH.iterdir():
        shutil.rmtree(old) if old.is_dir() else old.unlink()

    tracker_rows = read_tracker()
    known_rows = {
        (row.get("batch_date_ist"), row.get("video"), row.get("platform"))
        for row in tracker_rows
    }

    for index, story in enumerate(selected_stories, 1):
        metadata = build_metadata(story, batch_date)
        story_path = OUT / "story.json"
        story_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Generating video {index}/{BATCH_SIZE}: {story['title']} | hook: {story['hook']}")
        create_video.main()

        source = OUT / "daily_malayalam_stickman.mp4"
        if not source.is_file() or source.stat().st_size < 100_000:
            raise RuntimeError(f"Video {index} failed validation.")
        video_name = f"{index:02d}.mp4"
        shutil.copy2(source, BATCH / video_name)
        (BATCH / f"{index:02d}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        for platform in ("instagram", "youtube"):
            key = (batch_date, video_name, platform)
            if key not in known_rows:
                tracker_rows.append({
                    "batch_date_ist": batch_date,
                    "video": video_name,
                    "platform": platform,
                    "title": metadata["title"],
                    "scheduled_date_ist": "",
                    "scheduled_time_ist": "",
                    "status": "awaiting_approval",
                    "buffer_post_id": "",
                    "views": "",
                    "watch_time_seconds": "",
                    "average_watch_time_seconds": "",
                    "reach": "",
                    "shares": "",
                    "sends": "",
                    "saves": "",
                    "follows": "",
                    "notes": "",
                })
                known_rows.add(key)

    if len(list(BATCH.glob("*.mp4"))) != BATCH_SIZE:
        raise RuntimeError("The six-video batch is incomplete.")

    write_tracker(tracker_rows)
    shutil.copy2(TRACKER, BATCH / "07_tracker.csv")
    if len(list(BATCH.glob("*.json"))) != BATCH_SIZE:
        raise RuntimeError("The six metadata files are incomplete.")
    print("Six distinct Malayalam videos, captions, SEO keywords, hashtags and append-only tracker saved. Nothing has been published.")


if __name__ == "__main__":
    main()
