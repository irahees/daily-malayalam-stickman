from __future__ import annotations
import json, os, sys, urllib.error, urllib.request
from pathlib import Path

def graphql(key, query, variables=None):
    req = urllib.request.Request(
        "https://api.buffer.com",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Buffer HTTP {e.code}: {e.read().decode(errors='replace')[:1000]}") from e
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"])[:1200])
    return result.get("data") or {}

def hashtags_for(story):
    text = " ".join([str(story.get("topic", "")), str(story.get("title", ""))]).lower()
    tags = ["#malayalamcomedy", "#keralareels", "#malayalamreels"]
    if any(word in text for word in ("ഫോൺ", "ബാറ്ററി", "ഇന്റർനെറ്റ്", "മൊബൈൽ", "ഡിജിറ്റൽ")):
        tags.append("#malayalamtech")
    elif any(word in text for word in ("മഴ", "മണ്ണ്", "കടൽ", "വെള്ളം")):
        tags.append("#keralanature")
    elif any(word in text for word in ("കട", "പെട്രോൾ", "പണം", "രൂപ")):
        tags.append("#keralalife")
    else:
        tags.append("#stickmananimation")
    return " ".join(tags[:4])

def main():
    key = os.getenv("BUFFER_API_KEY", "").strip()
    base = os.getenv("BUFFER_VIDEO_BASE_URL", "").rstrip("/")
    folder = Path(os.getenv("VIDEO_ARTIFACT_DIR", "video-artifact"))
    if not key or not base.startswith("https://"):
        raise RuntimeError("Buffer key or public video URL is missing.")
    videos = sorted(folder.glob("*.mp4"))
    if len(videos) != 7:
        raise RuntimeError(f"Expected 7 reviewed videos; found {len(videos)}.")
    orgs = graphql(key, "query { account { organizations { id name } } }").get("account", {}).get("organizations", [])
    channels = []
    for org in orgs:
        d = graphql(key, "query GetChannels($organizationId: OrganizationId!) { channels(input: { organizationId: $organizationId }) { id name displayName service isQueuePaused } }", {"organizationId": org["id"]})
        channels.extend(d.get("channels") or [])
    matches = [c for c in channels if str(c.get("service", "")).lower() == "instagram"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one Instagram channel; found {len(matches)}.")
    channel = matches[0]
    if channel.get("isQueuePaused"):
        raise RuntimeError("Buffer Instagram queue is paused.")
    mutation = """mutation QueueReel($input: CreatePostInput!) { createPost(input:$input) { ... on PostActionSuccess { post { id status dueAt } } ... on MutationError { message } } }"""
    # The growth plan is four posts per week; keep the other three as reserves.
    for video in videos[:4]:
        story = json.loads(video.with_suffix(".json").read_text(encoding="utf-8"))
        title = str(story.get("title") or "Malayalam Short")[:100]
        hook = str(story.get("hook") or title).strip()
        if len(hook) > 124:
            hook = hook[:121].rstrip() + "…"
        scenes = story.get("scenes") or []
        closing = str(scenes[-1]) if scenes else "നിങ്ങളുടെ അഭിപ്രായം കമന്റിൽ പറയൂ."
        caption = f"{hook}\n\n{title} — Malayalam stickman animation.\n\n{closing}\n\n{hashtags_for(story)}"
        inp = {
            "text": caption,
            "channelId": channel["id"],
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [{"video": {"url": f"{base}/{video.name}", "metadata": {"thumbnailOffset": 1200}}}],
            "metadata": {"instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": True}},
            "aiAssisted": True,
        }
        post = graphql(key, mutation, {"input": inp}).get("createPost") or {}
        if post.get("message"):
            raise RuntimeError(f"Buffer rejected {video.name}: {post['message']}")
        item = post.get("post")
        if not item or not item.get("id"):
            raise RuntimeError(f"No Buffer post returned for {video.name}.")
        print(f"QUEUED {video.name} | {item.get('id')} | {item.get('status')} | {item.get('dueAt')}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
