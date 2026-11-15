from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Exact Tuesday/Thursday overflow posts from the explicitly approved batch.
# Keep Sunday, Monday, Wednesday and Friday slots: four posts per week per platform.
POST_IDS = [
    "6af83a6bd16af15d4d0b4f45",  # Instagram, 2026-11-17
    "6af83a6bd16af15d4d0b4f6d",  # YouTube, 2026-11-17
    "6af83a6dbb36d0090903bd3b",  # Instagram, 2026-11-19
    "6af83a6dbb36d0090903bec5",  # YouTube, 2026-11-19
]


def graphql(key: str, query: str, variables: dict) -> dict:
    request = urllib.request.Request(
        "https://api.buffer.com",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Buffer API HTTP {error.code}: "
            f"{error.read().decode('utf-8', errors='replace')[:800]}"
        ) from error
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False)[:1200])
    return result.get("data") or {}


def main() -> None:
    key = os.getenv("BUFFER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("BUFFER_API_KEY is missing.")
    mutation = """
      mutation DeleteUnscheduledOverflow($input: DeletePostInput!) {
        deletePost(input: $input) { __typename }
      }
    """
    for post_id in POST_IDS:
        data = graphql(key, mutation, {"input": {"id": post_id}})
        result = data.get("deletePost") or {}
        if result.get("__typename") != "DeletePostSuccess":
            raise RuntimeError(
                f"Buffer did not confirm deletion for {post_id}: "
                f"{json.dumps(result, ensure_ascii=False)}"
            )
        print(f"CANCELLED {post_id}")
    print(f"Confirmed cancellation of all {len(POST_IDS)} Tuesday/Thursday overflow posts.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error::{error}")
        sys.exit(1)
