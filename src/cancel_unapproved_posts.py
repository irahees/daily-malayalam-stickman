from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request

# These are the seven exact posts created by the pre-approval workflow run
# 43440353185. Do not broaden this list to other Buffer content.
POST_IDS = [
    "6af71bec4f78da1d8ba8f47e",
    "6af71bed1cbca7cd9c3ecca7",
    "6af71bedf2fe4518f4cf86f5",
    "6af71bee4c4c3b5e92676876",
    "6af71bef22fdd0eb2edde247",
    "6af71bf0f2fe4518f4cf87fe",
    "6af71bf049bae9df2d0ebd99",
]

def graphql(key: str, query: str, variables: dict) -> dict:
    request = urllib.request.Request(
        "https://api.buffer.com",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
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
        typename = result.get("__typename")
        if typename != "DeletePostSuccess":
            raise RuntimeError(
                f"Buffer did not confirm deletion for {post_id}: "
                f"{json.dumps(result, ensure_ascii=False)}"
            )
        print(f"CANCELLED {post_id}")
    print(f"Confirmed cancellation of {len(POST_IDS)} unapproved scheduled posts.")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"::error::{error}")
        sys.exit(1)
