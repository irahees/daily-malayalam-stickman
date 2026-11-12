from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.buffer.com"


def graphql(api_key: str, query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Buffer API HTTP {error.code}: {details[:1200]}") from error
    if result.get("errors"):
        raise RuntimeError("Buffer GraphQL error: " + json.dumps(result["errors"], ensure_ascii=False)[:1600])
    return result.get("data") or {}


def main() -> None:
    api_key = os.getenv("BUFFER_API_KEY", "").strip()
    video_url = os.getenv("BUFFER_VIDEO_URL", "").strip()
    if not api_key:
        raise RuntimeError("BUFFER_API_KEY is missing in GitHub Actions secrets.")
    if not video_url.startswith("https://"):
        raise RuntimeError("BUFFER_VIDEO_URL must be a stable public HTTPS video URL.")

    artifact_dir = Path(os.getenv("VIDEO_ARTIFACT_DIR", "video-artifact"))
    video_files = list(artifact_dir.rglob("*.mp4"))
    story_files = list(artifact_dir.rglob("story.json"))
    if len(video_files) != 1:
        raise RuntimeError(f"Expected exactly one MP4 in the downloaded artifact; found {len(video_files)}.")
    if not story_files:
        raise RuntimeError("story.json was not found in the downloaded video artifact.")
    story = json.loads(story_files[0].read_text(encoding="utf-8"))
    title = str(story.get("title") or "Malayalam Short").strip()[:100]
    scenes = story.get("scenes") or []
    question = str(scenes[-1]).strip() if scenes else "നിങ്ങളുടെ അഭിപ്രായം കമന്റിൽ പറയൂ."
    hashtags = "#Malayalam #Kerala #Knowledge #Reels #Shorts"
    caption = f"{title}\n\n{question}\n\n{hashtags}"
    description = f"{title}\n\n" + "\n".join(str(line).strip() for line in scenes)
    description += f"\n\n{hashtags}\n\n#YouTubeShorts"

    org_data = graphql(api_key, """
      query GetOrganizations {
        account {
          organizations { id name }
        }
      }
    """)
    organizations = (org_data.get("account") or {}).get("organizations") or []
    if not organizations:
        raise RuntimeError("No Buffer organization is connected to this API key.")

    channels = []
    for organization in organizations:
        channel_data = graphql(api_key, """
          query GetChannels($organizationId: OrganizationId!) {
            channels(input: { organizationId: $organizationId }) {
              id name displayName service isDisconnected isLocked isQueuePaused
            }
          }
        """, {"organizationId": organization["id"]})
        channels.extend(channel_data.get("channels") or [])

    targets = {}
    for service in ("instagram", "youtube"):
        matches = [
            channel for channel in channels
            if str(channel.get("service", "")).lower() == service
            and not channel.get("isDisconnected")
            and not channel.get("isLocked")
        ]
        if len(matches) > 1:
            names = ", ".join(str(item.get("name")) for item in matches)
            raise RuntimeError(f"More than one active {service} channel found ({names}); refusing to guess.")
        if not matches:
            raise RuntimeError(f"No active {service} channel found in the connected Buffer organizations.")
        targets[service] = matches[0]

    def create_post(service: str, channel: dict) -> None:
        if service == "instagram":
            text = caption
            metadata = {
                "instagram": {
                    "type": "reel",
                    "shouldShareToFeed": True,
                    "isAiGenerated": True,
                }
            }
        else:
            text = description
            metadata = {
                "youtube": {
                    "title": title,
                    "categoryId": "27",
                    "isAiGenerated": True,
                }
            }

        mutation = """
          mutation CreateVideoPost($input: CreatePostInput!) {
            createPost(input: $input) {
              ... on PostActionSuccess {
                post { id status dueAt channelId }
              }
              ... on MutationError { message }
            }
          }
        """
        variables = {
            "input": {
                "text": text,
                "channelId": channel["id"],
                "schedulingType": "automatic",
                "mode": "shareNow",
                "assets": [{
                    "video": {
                        "url": video_url,
                        "metadata": {"thumbnailOffset": 1200},
                    }
                }],
                "metadata": metadata,
                "aiAssisted": True,
            }
        }
        result = graphql(api_key, mutation, variables)
        action = result.get("createPost") or {}
        if action.get("message"):
            raise RuntimeError(f"Buffer rejected the {service} post: {action['message']}")
        post = action.get("post")
        if not post or not post.get("id"):
            raise RuntimeError(f"Buffer returned no successful post for {service}: {json.dumps(action)[:1000]}")
        print(f"BUFFER_{service.upper()}_POST_ID={post['id']}")
        print(f"BUFFER_{service.upper()}_STATUS={post.get('status', 'unknown')}")

    for service in ("instagram", "youtube"):
        channel = targets[service]
        print(f"Publishing to {service}: {channel.get('name') or channel.get('displayName') or channel['id']}")
        create_post(service, channel)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error::{error}")
        sys.exit(1)
