from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Exact posts created without approval by publisher run 43588025568.
# Only these eight IDs are in scope; previously approved posts are untouched.
POST_IDS = [
    "6af83fef81e1228421ff62e0",
    "6af83ff0d16af15d4d0d3391",
    "6af83ff0d16af15d4d0d33de",
    "6af83ff1d8bd2962e42491fc",
    "6af83ff2d8bd2962e4249226",
    "6af83ff2d8bd2962e4249254",
    "6af83ff3d8bd2962e4249282",
    "6af83ff4bb36d0090905a368",
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
      mutation DeleteUnapprovedPost($input: DeletePostInput!) {
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
    print(f"Confirmed cancellation of all {len(POST_IDS)} exact unapproved Buffer posts.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error::{error}")
        sys.exit(1)
