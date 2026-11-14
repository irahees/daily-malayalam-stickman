from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://api.buffer.com"
PAGE_SIZE = 100
BATCH_SIZE = 6
IST = ZoneInfo("Asia/Kolkata")
ACTIVE_STATUSES = {"draft", "needs_approval", "scheduled", "sending", "sent"}
VERIFIED_STATUSES = {"scheduled", "sending", "sent"}
TRACKER_COLUMNS = [
    "batch_date_ist", "video", "platform", "title",
    "scheduled_date_ist", "scheduled_time_ist", "status", "buffer_post_id",
    "views", "watch_time_seconds", "average_watch_time_seconds", "reach",
    "shares", "sends", "saves", "follows", "notes",
]


def graphql(key: str, query: str, variables: dict | None = None) -> dict:
    request = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Buffer HTTP {error.code}: {detail[:1000]}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Buffer connection failed: {error}") from error
    if result.get("errors"):
        messages = "; ".join(str(item.get("message", "unknown")) for item in result["errors"])
        raise RuntimeError(f"Buffer GraphQL error: {messages}")
    if "data" not in result:
        raise RuntimeError("Buffer returned no data.")
    return result["data"]


def next_slots(service: str, now: datetime, count: int) -> list[datetime]:
    slots: list[datetime] = []
    day = now.astimezone(IST).date()
    while len(slots) < count:
        weekend = day.weekday() >= 5
        if service == "instagram":
            hour, minute = (12, 0) if weekend else (19, 30)
        elif service == "youtube":
            hour, minute = (13, 0) if weekend else (18, 30)
        else:
            raise ValueError(f"Unsupported service: {service}")
        slot = datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)
        if slot > now.astimezone(IST):
            slots.append(slot)
        day += timedelta(days=1)
    return slots


def as_utc_iso(local_slot: datetime) -> str:
    return local_slot.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_posts(key: str, organization_id: str, channel_id: str) -> list[dict]:
    query = """
      query ExistingPosts($first: Int!, $after: String, $input: PostsInput!) {
        posts(first: $first, after: $after, input: $input) {
          pageInfo { hasNextPage endCursor }
          edges {
            node {
              id text status dueAt channelId
              assets { source mimeType }
            }
          }
        }
      }
    """
    result: list[dict] = []
    cursor = None
    for _ in range(100):
        data = graphql(key, query, {
            "first": PAGE_SIZE,
            "after": cursor,
            "input": {
                "organizationId": organization_id,
                "filter": {"channelIds": [channel_id]},
            },
        })
        connection = data.get("posts") or {}
        result.extend(edge.get("node") or {} for edge in connection.get("edges") or [])
        page = connection.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return result
        next_cursor = page.get("endCursor")
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError("Buffer pagination did not advance; refusing to queue duplicates.")
        cursor = next_cursor
    raise RuntimeError("Buffer returned over 10,000 posts; refusing to continue with incomplete duplicate detection.")


def verify_public_video_url(url: str) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "DailyMalayalamStickman/1.0"}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            if response.status != 200:
                raise RuntimeError(f"Video host returned HTTP {response.status} for the public media URL.")
            length = response.headers.get("Content-Length")
            if length and int(length) < 100_000:
                raise RuntimeError("Public video URL points to an unexpectedly small file.")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Buffer cannot fetch the public video URL (HTTP {error.code}).") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Could not verify the public video URL: {error}") from error


def asset_urls(post: dict) -> set[str]:
    return {
        str(asset.get("source")).strip()
        for asset in post.get("assets") or []
        if str(asset.get("source") or "").startswith("https://")
    }


def create_post(key: str, channel: dict, video_url: str, title: str, caption: str, service: str, due_at: str) -> dict:
    if service == "instagram":
        metadata = {
            "instagram": {
                "type": "reel",
                "shouldShareToFeed": True,
                "isAiGenerated": True,
            }
        }
    elif service == "youtube":
        metadata = {
            "youtube": {
                "title": title[:100],
                "categoryId": "27",
                "privacy": "public",
                "notifySubscribers": True,
                "isAiGenerated": True,
            }
        }
    else:
        raise ValueError(f"Unsupported Buffer service: {service}")

    mutation = """
      mutation ScheduleApprovedVideo($input: CreatePostInput!) {
        createPost(input: $input) {
          ... on PostActionSuccess { post { id status dueAt channelId } }
          ... on MutationError { message }
        }
      }
    """
    data = graphql(key, mutation, {"input": {
        "text": caption,
        "channelId": channel["id"],
        "schedulingType": "automatic",
        "mode": "customScheduled",
        "dueAt": due_at,
        "assets": [{
            "video": {
                "url": video_url,
                "metadata": {"title": title[:100], "thumbnailOffset": 1200},
            }
        }],
        "metadata": metadata,
        "aiAssisted": True,
    }})
    result = data.get("createPost") or {}
    if result.get("message"):
        raise RuntimeError(f"Buffer rejected {service} post: {result['message']}")
    post = result.get("post") or {}
    if not post.get("id"):
        raise RuntimeError(f"Buffer did not confirm the {service} post.")
    return post


def update_tracker(outcomes: list[dict], tracker_path: Path) -> None:
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    if not tracker_path.is_file():
        raise RuntimeError("Persistent tracking/07_tracker.csv is missing; refusing to publish without a ledger.")
    with tracker_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != TRACKER_COLUMNS:
            raise RuntimeError("Tracking ledger schema mismatch; refusing to overwrite existing history.")
        rows = list(reader)

    indexed = {
        (row.get("batch_date_ist"), row.get("video"), row.get("platform")): row
        for row in rows
    }
    for outcome in outcomes:
        key = (outcome["batch_date_ist"], outcome["video"], outcome["service"])
        row = indexed.get(key)
        if row is None:
            raise RuntimeError(f"Tracking row is missing for {key}; refusing to publish without a ledger entry.")
        row["status"] = outcome["status"]
        row["buffer_post_id"] = outcome["post_id"]
        due_at = outcome.get("due_at")
        if due_at:
            due = datetime.fromisoformat(due_at.replace("Z", "+00:00")).astimezone(IST)
            row["scheduled_date_ist"] = due.date().isoformat()
            row["scheduled_time_ist"] = due.strftime("%H:%M")
        row["notes"] = "Buffer post verified; scheduled status is not proof of publication."
    with tracker_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRACKER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    key = os.getenv("BUFFER_API_KEY", "").strip()
    base = os.getenv("BUFFER_VIDEO_BASE_URL", "").rstrip("/")
    folder = Path(os.getenv("VIDEO_ARTIFACT_DIR", "video-artifact"))
    tracker_path = Path("tracking/07_tracker.csv")
    if not key or not base.startswith("https://"):
        raise RuntimeError("BUFFER_API_KEY or public HTTPS video URL is missing.")

    videos = sorted(folder.glob("*.mp4"))
    if len(videos) != BATCH_SIZE:
        raise RuntimeError(f"Expected {BATCH_SIZE} explicitly approved videos; found {len(videos)}.")

    stories = {}
    for video in videos:
        story_path = video.with_suffix(".json")
        if not story_path.is_file():
            raise RuntimeError(f"Metadata file is missing for {video.name}.")
        stories[video.name] = json.loads(story_path.read_text(encoding="utf-8"))
    batch_dates = {str(story.get("batch_date_ist", "")) for story in stories.values()}
    if len(batch_dates) != 1 or not next(iter(batch_dates)):
        raise RuntimeError("The approved batch metadata does not contain one consistent IST batch date.")

    account = graphql(key, "query { account { organizations { id name } } }").get("account") or {}
    organizations = account.get("organizations") or []
    selected_id = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
    if selected_id:
        organizations = [org for org in organizations if org.get("id") == selected_id]
    if len(organizations) != 1:
        raise RuntimeError(f"Expected exactly one selected Buffer organization; found {len(organizations)}.")
    organization = organizations[0]

    channel_data = graphql(
        key,
        """
          query GetChannels($input: ChannelsInput!) {
            channels(input: $input) {
              id name displayName service isDisconnected isLocked isQueuePaused
            }
          }
        """,
        {"input": {"organizationId": organization["id"]}},
    )
    active = [
        channel for channel in channel_data.get("channels") or []
        if not channel.get("isDisconnected") and not channel.get("isLocked")
    ]
    selected = {}
    for service in ("instagram", "youtube"):
        matches = [channel for channel in active if str(channel.get("service", "")).lower() == service]
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one active {service} channel; found {len(matches)}.")
        if matches[0].get("isQueuePaused"):
            raise RuntimeError(f"Buffer {service} queue is paused.")
        selected[service] = matches[0]

    existing = {
        service: load_posts(key, organization["id"], channel["id"])
        for service, channel in selected.items()
    }
    existing_by_url = {
        service: {
            url: post
            for post in existing[service]
            if str(post.get("status", "")).lower() in ACTIVE_STATUSES
            for url in asset_urls(post)
        }
        for service in selected
    }

    now = datetime.now(IST)
    slots = {
        service: next_slots(service, now, len(videos))
        for service in selected
    }
    outcomes: list[dict] = []
    newly_created: list[dict] = []
    already_present: list[dict] = []

    for index, video in enumerate(videos):
        story = stories[video.name]
        title = str(story.get("title") or "Malayalam Short").strip()[:100]
        tags = " ".join(str(tag) for tag in story.get("hashtags") or [])
        video_url = f"{base}/{video.name}"
        verify_public_video_url(video_url)

        for service in ("instagram", "youtube"):
            due_at = as_utc_iso(slots[service][index])
            if video_url in existing_by_url[service]:
                post = existing_by_url[service][video_url]
                outcome = {
                    "service": service,
                    "video": video.name,
                    "batch_date_ist": story["batch_date_ist"],
                    "post_id": post["id"],
                    "status": str(post.get("status", "")).lower(),
                    "due_at": post.get("dueAt") or due_at,
                }
                already_present.append(outcome)
                outcomes.append(outcome)
                print(f"SKIP {service} {video.name}: exact video URL already exists in Buffer as {outcome['status']}")
                continue

            if service == "instagram":
                caption = str(story.get("instagram_caption") or f"{story.get('hook', title)}\n\n{title}\n\n{tags} #Reels")
            else:
                caption = str(story.get("youtube_description") or f"{story.get('hook', title)}\n\n{title}\n\n{tags} #Shorts")
            post = create_post(key, selected[service], video_url, title, caption, service, due_at)
            outcome = {
                "service": service,
                "video": video.name,
                "batch_date_ist": story["batch_date_ist"],
                "post_id": post["id"],
                "status": str(post.get("status", "")).lower(),
                "due_at": post.get("dueAt") or due_at,
            }
            newly_created.append(outcome)
            outcomes.append(outcome)
            print(f"CREATED {service} {video.name} | {post['id']} | {outcome['status']} | {outcome['due_at']}")

    verified_posts: dict[str, dict[str, dict]] = {}
    for attempt in range(3):
        verified_posts = {
            service: {post["id"]: post for post in load_posts(key, organization["id"], channel["id"])}
            for service, channel in selected.items()
        }
        pending = [
            outcome for outcome in outcomes
            if str((verified_posts[outcome["service"]].get(outcome["post_id"]) or {}).get("status", "")).lower()
            not in VERIFIED_STATUSES
        ]
        if not pending:
            break
        if attempt < 2:
            time.sleep(2)

    for outcome in outcomes:
        post = verified_posts[outcome["service"]].get(outcome["post_id"])
        if not post:
            raise RuntimeError(f"Buffer verification failed: post {outcome['post_id']} was not found after creation.")
        status = str(post.get("status", "")).lower()
        if status not in VERIFIED_STATUSES:
            raise RuntimeError(f"Buffer post {outcome['post_id']} exists but is not scheduled/sent; current status: {status}.")
        outcome["status"] = status
        outcome["due_at"] = post.get("dueAt") or outcome["due_at"]
        print(f"VERIFIED {outcome['service']} {outcome['video']} | {outcome['post_id']} | {status} | {outcome['due_at']}")

    update_tracker(outcomes, tracker_path)
    print(
        f"Buffer verification complete: {len(newly_created)} new posts scheduled and verified; "
        f"{len(already_present)} exact-URL duplicates safely skipped. Scheduled is not published."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error::{error}")
        sys.exit(1)
