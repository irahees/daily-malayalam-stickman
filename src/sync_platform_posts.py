from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

API = "https://api.buffer.com"
REPORT_DIR = Path("output/platform-sync")
SERVICES = ("instagram", "youtube")
PAGE_SIZE = 50


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(
        API,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Buffer API HTTP {exc.code}: {detail[:900]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Buffer API connection failed: {exc}") from exc
    if result.get("errors"):
        raise RuntimeError("Buffer GraphQL error: " + "; ".join(
            str(item.get("message", "unknown")) for item in result["errors"]
        ))
    if "data" not in result:
        raise RuntimeError("Buffer returned no data.")
    return result["data"]


def clean_text(value: str) -> str:
    value = re.sub(r"https?://\S+", " ", value.lower())
    value = re.sub(r"#[\w\u0D00-\u0D7F]+", " ", value)
    value = re.sub(r"[^\w\u0D00-\u0D7F]+", " ", value)
    return " ".join(value.split())


def title_key(post: dict) -> str:
    text = str(post.get("text") or "").strip()
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return clean_text(first)


def media_url(post: dict) -> str:
    for asset in post.get("assets") or []:
        mime = str(asset.get("mimeType") or "").lower()
        source = str(asset.get("source") or "").strip()
        if source.startswith("https://") and ("video" in mime or not mime):
            return source
    return ""


def parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def match_score(a: dict, b: dict) -> float:
    ua, ub = media_url(a), media_url(b)
    if ua and ub and ua == ub:
        return 1.0
    ka, kb = title_key(a), title_key(b)
    if not ka or not kb:
        return 0.0
    text_score = SequenceMatcher(None, ka, kb).ratio()
    da, db = parse_date(a.get("createdAt")), parse_date(b.get("createdAt"))
    if da and db:
        days = abs((da - db).total_seconds()) / 86400
        if days > 7 and text_score < 0.94:
            return 0.0
        if days <= 2:
            text_score = min(1.0, text_score + 0.08)
    return text_score


def get_posts(token: str, organization_id: str, channel_id: str) -> list[dict]:
    query_template = """
      query SyncPosts {
        posts(
          first: __FIRST__,
          after: __AFTER__,
          input: { organizationId: __ORG__, filter: { channelIds: [__CHANNEL__] } }
        ) {
          pageInfo { hasNextPage endCursor }
          edges {
            node {
              id text createdAt dueAt status channelId
              assets { source mimeType thumbnail }
            }
          }
        }
      }
    """
    all_posts: list[dict] = []
    cursor = None
    for _ in range(100):
        after_value = json.dumps(cursor) if cursor else "null"
        query = (query_template
                 .replace("__FIRST__", str(PAGE_SIZE))
                 .replace("__AFTER__", after_value)
                 .replace("__ORG__", json.dumps(organization_id))
                 .replace("__CHANNEL__", json.dumps(channel_id)))
        data = gql(token, query)
        connection = data.get("posts") or {}
        all_posts.extend(edge.get("node") or {} for edge in connection.get("edges") or [])
        page = connection.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return all_posts
        next_cursor = page.get("endCursor")
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError("Buffer pagination did not advance; refusing an incomplete sync report.")
        cursor = next_cursor
    raise RuntimeError("Buffer returned more than 5,000 posts; refusing to silently truncate the sync check.")


def choose_matches(insta: list[dict], youtube: list[dict]) -> tuple[list[tuple[dict, dict, float]], list[dict], list[dict]]:
    candidates = []
    for i, a in enumerate(insta):
        for j, b in enumerate(youtube):
            score = match_score(a, b)
            if score >= 0.78:
                candidates.append((score, i, j))
    candidates.sort(reverse=True)
    used_i, used_y, matches = set(), set(), []
    for score, i, j in candidates:
        if i in used_i or j in used_y:
            continue
        used_i.add(i)
        used_y.add(j)
        matches.append((insta[i], youtube[j], score))
    return matches, [p for i, p in enumerate(insta) if i not in used_i], [p for j, p in enumerate(youtube) if j not in used_y]


def create_draft(token: str, channel: dict, source_post: dict, target_service: str) -> str:
    url = media_url(source_post)
    if not url or urlparse(url).scheme != "https":
        raise RuntimeError(f"Cannot safely reuse the source video for post {source_post.get('id')}: no HTTPS video asset URL.")
    title = next((line.strip() for line in str(source_post.get("text") or "").splitlines() if line.strip()), "Malayalam video")
    source_text = str(source_post.get("text") or "").strip()
    if target_service == "instagram":
        metadata = {"instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": True}}
        text = source_text[:2200]
    else:
        metadata = {"youtube": {"title": title[:100], "categoryId": "27", "isAiGenerated": True}}
        text = source_text[:5000]
    mutation = """
      mutation CreateSyncDraft($input: CreatePostInput!) {
        createPost(input: $input) {
          ... on PostActionSuccess { post { id status } }
          ... on MutationError { message }
        }
      }
    """
    result = gql(token, mutation, {"input": {
        "channelId": channel["id"],
        "text": text,
        "assets": [{"video": {"url": url, "metadata": {"thumbnailOffset": 1200}}}],
        "metadata": metadata,
        "schedulingType": "automatic",
        "mode": "addToQueue",
        "saveToDraft": True,
        "aiAssisted": True,
    }}).get("createPost") or {}
    if result.get("message"):
        raise RuntimeError(f"Buffer rejected the {target_service} draft: {result['message']}")
    post = result.get("post") or {}
    if not post.get("id"):
        raise RuntimeError(f"Buffer did not confirm the {target_service} draft.")
    return str(post["id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-approved", action="store_true",
                        help="Create Buffer drafts for missing counterparts; never publish.")
    args = parser.parse_args()
    token = os.getenv("BUFFER_API_KEY", "").strip()
    if not token:
        raise RuntimeError("BUFFER_API_KEY is missing.")

    org_data = gql(token, "query { account { organizations { id name } } }")
    organizations = (org_data.get("account") or {}).get("organizations") or []
    selected_id = os.getenv("BUFFER_ORGANIZATION_ID", "").strip()
    if selected_id:
        organizations = [o for o in organizations if o.get("id") == selected_id]
    if len(organizations) != 1:
        raise RuntimeError(f"Expected exactly one selected Buffer organization; found {len(organizations)}. Set BUFFER_ORGANIZATION_ID if needed.")
    organization = organizations[0]

    channel_data = gql(token, """
      query SyncChannels($input: ChannelsInput!) {
        channels(input: $input) { id name displayName service isDisconnected isLocked }
      }
    """, {"input": {"organizationId": organization["id"]}})
    channels = [c for c in channel_data.get("channels") or []
                if not c.get("isDisconnected") and not c.get("isLocked")]
    selected = {}
    for service in SERVICES:
        found = [c for c in channels if str(c.get("service", "")).lower() == service]
        if len(found) != 1:
            raise RuntimeError(f"Expected exactly one active {service} channel; found {len(found)}. Refusing to guess.")
        selected[service] = found[0]

    insta_posts = get_posts(token, organization["id"], selected["instagram"]["id"])
    youtube_posts = get_posts(token, organization["id"], selected["youtube"]["id"])
    # Compare all retained Buffer records, but only sent posts are treated as published sources.
    insta_sent = [p for p in insta_posts if str(p.get("status", "")).lower() == "sent"]
    youtube_sent = [p for p in youtube_posts if str(p.get("status", "")).lower() == "sent"]
    pending_statuses = {"draft", "scheduled", "queued", "pending"}
    insta_other = [p for p in insta_posts if str(p.get("status", "")).lower() in pending_statuses]
    youtube_other = [p for p in youtube_posts if str(p.get("status", "")).lower() in pending_statuses]

    matches, missing_instagram, missing_youtube = choose_matches(insta_sent, youtube_sent)

    # A pending/scheduled/draft counterpart is already in progress; do not suggest a duplicate.
    def already_pending(source: dict, pending: list[dict]) -> bool:
        return any(match_score(source, candidate) >= 0.78 for candidate in pending)

    missing_instagram = [p for p in missing_instagram if not already_pending(p, insta_other)]
    missing_youtube = [p for p in missing_youtube if not already_pending(p, youtube_other)]

    created = []
    if args.apply_approved:
        for service, missing, channel in (
            ("instagram", missing_instagram, selected["instagram"]),
            ("youtube", missing_youtube, selected["youtube"]),
        ):
            for source in missing:
                draft_id = create_draft(token, channel, source, service)
                created.append({"target": service, "source_post_id": source.get("id"), "draft_id": draft_id})

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "organization": organization.get("name"),
        "channels": {k: v.get("displayName") or v.get("name") for k, v in selected.items()},
        "buffer_history_only": True,
        "note": "This audit sees posts recorded by Buffer. Posts published manually outside Buffer are not visible here. Buffer retains sent/failed posts for two years.",
        "counts": {
            "instagram_sent": len(insta_sent),
            "youtube_sent": len(youtube_sent),
            "matched_pairs": len(matches),
            "missing_on_instagram": len(missing_instagram),
            "missing_on_youtube": len(missing_youtube),
            "drafts_created": len(created),
        },
        "matches": [{"instagram_post_id": a.get("id"), "youtube_post_id": b.get("id"), "score": round(s, 3)} for a, b, s in matches],
        "missing_on_instagram": [{"source_post_id": p.get("id"), "title": title_key(p), "video_url_available": bool(media_url(p))} for p in missing_instagram],
        "missing_on_youtube": [{"source_post_id": p.get("id"), "title": title_key(p), "video_url_available": bool(media_url(p))} for p in missing_youtube],
        "drafts_created": created,
    }
    (REPORT_DIR / "sync-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# YouTube ↔ Instagram Sync Report",
        "",
        f"- Generated: {report['generated_at_utc']}",
        f"- Instagram sent posts scanned: {len(insta_sent)}",
        f"- YouTube sent posts scanned: {len(youtube_sent)}",
        f"- Matched pairs: {len(matches)}",
        f"- Missing on Instagram: {len(missing_instagram)}",
        f"- Missing on YouTube: {len(missing_youtube)}",
        f"- Buffer drafts created: {len(created)}",
        "",
        "> Scope: Buffer history only. Posts published manually outside Buffer are not visible. Review possible title/date matches before approving drafts.",
        "",
        "## Missing on Instagram",
    ]
    lines += [f"- {title_key(p) or p.get('id')} — source post {p.get('id')}; video asset {'available' if media_url(p) else 'not available'}" for p in missing_instagram] or ["- None detected."]
    lines += ["", "## Missing on YouTube"]
    lines += [f"- {title_key(p) or p.get('id')} — source post {p.get('id')}; video asset {'available' if media_url(p) else 'not available'}" for p in missing_youtube] or ["- None detected."]
    if created:
        lines += ["", "## Buffer drafts created (not published)"]
        lines += [f"- {item['target']}: draft {item['draft_id']} from {item['source_post_id']}" for item in created]
    (REPORT_DIR / "sync-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"::error::{exc}")
        sys.exit(1)
