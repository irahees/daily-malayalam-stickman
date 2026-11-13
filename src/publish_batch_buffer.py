from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.buffer.com"
PAGE_SIZE = 100
WEEKLY_POSTS = 4


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


def hashtags_for(story: dict) -> str:
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
    return " ".join(tags[:4])


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
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DailyMalayalamStickman/1.0"},
        method="HEAD",
    )
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


def create_post(key: str, channel: dict, video_url: str, title: str, caption: str,
                service: str) -> dict:
    if service == "instagram":
        metadata = {
            "instagram": {
                "type": "reel",
                "shouldShareToFeed": True,
                "isAiGenerated": True,
            }
        }
        text = caption
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
        text = caption
    else:
        raise ValueError(f"Unsupported Buffer service: {service}")

    mutation = """
      mutation QueueApprovedVideo($input: CreatePostInput!) {
        createPost(input: $input) {
          ... on PostActionSuccess { post { id status dueAt channelId } }
          ... on MutationError { message }
        }
      }
    """
    data = graphql(key, mutation, {"input": {
        "text": text,
        "channelId": channel["id"],
        "schedulingType": "automatic",
        "mode": "addToQueue",
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


def main() -> None:
    key = os.getenv("BUFFER_API_KEY", "").strip()
    base = os.getenv("BUFFER_VIDEO_BASE_URL", "").rstrip("/")
    folder = Path(os.getenv("VIDEO_ARTIFACT_DIR", "video-artifact"))
    if not key or not base.startswith("https://"):
        raise RuntimeError("BUFFER_API_KEY or public HTTPS video URL is missing.")

    videos = sorted(folder.glob("*.mp4"))
    if len(videos) != 7:
        raise RuntimeError(f"Expected 7 reviewed videos; found {len(videos)}.")

    account = graphql(key, "query { account { organizations { id name } } }").get("account") or {}
    organizations = account.get("organizations") or []
    selected_id = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
    if selected_id:
        organizations = [org for org in organizations if org.get("id") == selected_id]
    if len(organizations) != 1:
        raise RuntimeError(
            f"Expected exactly one selected Buffer organization; found {len(organizations)}. "
            "Set BUFFER_ORGANIZATION_ID if the account has multiple organizations."
        )
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

    # Fetch existing posts before creating anything. This makes a rerun idempotent
    # for the same release-asset URL and prevents duplicate scheduled uploads.
    existing = {
        service: load_posts(key, organization["id"], channel["id"])
        for service, channel in selected.items()
    }
    in_progress = {"draft", "needs_approval", "scheduled", "sending", "sent"}
    scheduled_urls = {
        service: {
            url
            for post in existing[service]
            if str(post.get("status", "")).lower() in in_progress
            for url in asset_urls(post)
        }
        for service in selected
    }

    queued = []
    skipped = []
    # Four posts per week; the remaining three approved videos stay as reserves.
    for video in videos[:WEEKLY_POSTS]:
        story_path = video.with_suffix(".json")
        if not story_path.is_file():
            raise RuntimeError(f"Metadata file is missing for {video.name}.")
        story = json.loads(story_path.read_text(encoding="utf-8"))
        title = str(story.get("title") or "Malayalam Short").strip()[:100]
        hook = str(story.get("hook") or title).strip()
        if len(hook) > 124:
            hook = hook[:121].rstrip() + "…"
        scenes = story.get("scenes") or []
        closing = str(scenes[-1]).strip() if scenes else "നിങ്ങളുടെ അഭിപ്രായം കമന്റിൽ പറയൂ."
        tags = hashtags_for(story)
        video_url = f"{base}/{video.name}"
        verify_public_video_url(video_url)
        instagram_caption = (
            f"{hook}\n\n{title}\n\n{closing}\n\n{tags} #Reels"
        )
        youtube_description = (
            f"{hook}\n\n{title}\n\n{closing}\n\n{tags} #Shorts"
        )

        for service in ("instagram", "youtube"):
            if video_url in scheduled_urls[service]:
                skipped.append(f"{service}: {video.name} already exists in Buffer")
                print(f"SKIP {service} {video.name}: existing Buffer post uses this exact video URL")
                continue
            caption = instagram_caption if service == "instagram" else youtube_description
            post = create_post(
                key, selected[service], video_url, title, caption, service
            )
            queued.append({
                "service": service,
                "video": video.name,
                "post_id": post["id"],
                "status": post.get("status"),
                "due_at": post.get("dueAt"),
            })
            scheduled_urls[service].add(video_url)
            print(
                f"QUEUED {service} {video.name} | {post['id']} | "
                f"{post.get('status')} | {post.get('dueAt')}"
            )

    if not queued and not skipped:
        raise RuntimeError("No Buffer posts were created or skipped; inspect the batch input.")
    print(
        f"Buffer batch complete: {len(queued)} new posts queued across both channels; "
        f"{len(skipped)} duplicates safely skipped. No YouTube Data API upload was used."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error::{error}")
        sys.exit(1)
