from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Exact unapproved posts created by auto-publish run 43472096446.
# These IDs are intentionally scoped; do not broaden this list.
POST_IDS = [
    "6af7478538f9934c19ff8d75",
    "6af7478538f9934c19ff8da8",
    "6af7478638f9934c19ff8e0b",
    "6af7478760bde15261f58afb",
    "6af7478822cd418aa2de310a",
    "6af747884d5a2b44bea079ca",
    "6af747894d5a2b44bea07a23",
    "6af7478938f9934c19ff8f71",
    "6af7478a22cd418aa2de3235",
    "6af7478b38f9934c19ff920d",
    "6af7478c0234d2352e23cf0f",
    "6af7478c60bde15261f58c85",
    "6af7478d60bde15261f58d0c",
    "6af7478e22cd418aa2de34c6",
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
