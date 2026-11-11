from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.buffer.com"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(
        API,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Buffer API HTTP {exc.code}: {detail[:700]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Buffer API connection failed: {exc}") from exc
    if result.get("errors"):
        messages = "; ".join(str(e.get("message", "GraphQL error")) for e in result["errors"])
        raise RuntimeError(f"Buffer GraphQL error: {messages}")
    if "data" not in result:
        raise RuntimeError("Buffer API returned no data.")
    return result["data"]


def main() -> None:
    token = os.getenv("BUFFER_API_KEY", "").strip()
    if not token:
        raise RuntimeError("BUFFER_API_KEY is missing from GitHub Actions secrets.")

    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    account = gql(token, """
      query GetBufferOrganizations {
        account {
          organizations { id name }
        }
      }
    """)
    organizations = account["account"]["organizations"]
    if not organizations:
        raise RuntimeError("No Buffer organization is available for this API key.")
    if len(organizations) > 1:
        selected = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
        organizations = [o for o in organizations if o["id"] == selected]
        if len(organizations) != 1:
            raise RuntimeError(
                "Multiple Buffer organizations found. Set BUFFER_ORGANIZATION_ID "
                "as a GitHub Actions secret/variable to select the intended one."
            )

    org = organizations[0]
    channel_data = gql(token, """
      query GetBufferChannels($input: ChannelsInput!) {
        channels(input: $input) {
          id name displayName service isDisconnected isLocked
        }
      }
    """, {"input": {"organizationId": org["id"]}})
    channels = channel_data["channels"]
    print(f"Buffer authentication OK. Organization: {org['name']}")
    for channel in channels:
        print(
            "Channel found: "
            f"{channel.get('displayName') or channel['name']} "
            f"({channel['service']}); disconnected={channel['isDisconnected']}; "
            f"locked={channel['isLocked']}"
        )

    if mode != "draft":
        print("Verification-only run: no Buffer posts were created.")
        return

    video_url = os.getenv("PUBLIC_VIDEO_URL", "").strip()
    if not video_url.startswith("https://"):
        raise RuntimeError("PUBLIC_VIDEO_URL is missing or is not HTTPS.")
    story_path = OUT / "story.json"
    if not story_path.is_file():
        raise RuntimeError("output/story.json is missing.")
    story = json.loads(story_path.read_text(encoding="utf-8"))
    title = str(story.get("title", "")).strip()
    if not title:
        raise RuntimeError("Story title is missing.")

    caption = (
        f"{title}\n\n"
        "ഇതിനെക്കുറിച്ച് നിങ്ങളുടെ അഭിപ്രായം കമന്റ് ചെയ്യൂ!\n\n"
        "#Malayalam #Kerala #MalayalamShorts #Reels #Shorts"
    )
    targets = []
    for channel in channels:
        service = str(channel.get("service", "")).lower()
        if channel["isDisconnected"] or channel["isLocked"]:
            continue
        if service == "instagram":
            targets.append((channel, "instagram"))
        elif service == "youtube":
            targets.append((channel, "youtube"))

    if not targets:
        raise RuntimeError(
            "No active Instagram or YouTube channel is connected to this Buffer organization."
        )

    mutation = """
      mutation CreateBufferDraft($input: CreatePostInput!) {
        createPost(input: $input) {
          ... on PostActionSuccess {
            post { id text status channelId }
          }
          ... on MutationError {
            message
          }
        }
      }
    """
    created = 0
    for channel, service in targets:
        post_input = {
            "channelId": channel["id"],
            "text": caption,
            "assets": [{"video": {"url": video_url, "metadata": {"thumbnailOffset": 1000}}}],
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "saveToDraft": True,
            "aiAssisted": True,
        }
        if service == "instagram":
            post_input["metadata"] = {
                "instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": True}
            }
        else:
            post_input["metadata"] = {
                "youtube": {
                    "title": title[:100],
                    "categoryId": "27",
                    "privacy": "private",
                    "madeForKids": False,
                    "isAiGenerated": True,
                }
            }

        result = gql(token, mutation, {"input": post_input})["createPost"]
        if result.get("message"):
            raise RuntimeError(
                f"Buffer rejected the {service} draft for "
                f"{channel.get('displayName') or channel['name']}: {result['message']}"
            )
        post = result.get("post")
        if not post or not post.get("id"):
            raise RuntimeError(f"Buffer did not confirm creation of the {service} draft.")
        created += 1
        print(
            f"Created Buffer draft for {service}: "
            f"{channel.get('displayName') or channel['name']} "
            f"(status={post.get('status', 'draft')}, id={post['id']})"
        )

    print(f"Buffer draft creation complete: {created} draft(s). Nothing was published.")


if __name__ == "__main__":
    main()
