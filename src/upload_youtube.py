from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

VIDEO = Path("output/daily_malayalam_stickman.mp4")
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def request_json(url: str, data: bytes, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google API HTTP {exc.code}: {detail[:1000]}") from exc


def get_access_token() -> str:
    client_id = os.environ["YOUTUBE_CLIENT_ID"]
    client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]
    refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]
    form = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    result = request_json(
        TOKEN_URL, form,
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = result.get("access_token")
    if not token:
        raise RuntimeError("Google did not return an access token.")
    return token


def main() -> None:
    if not VIDEO.is_file():
        raise SystemExit(f"Video file not found: {VIDEO}")
    token = get_access_token()
    size = VIDEO.stat().st_size

    # Every automated test upload is forced to Private.
    metadata = {
        "snippet": {
            "title": "Malayalam Stickman Story | Daily Malayalam",
            "description": (
                "An original Malayalam stickman story.\n"
                "Created with the Daily Malayalam Stickman project."
            ),
            "categoryId": "22",
        },
        "status": {"privacyStatus": "private"},
    }
    query = urllib.parse.urlencode({"uploadType": "resumable", "part": "snippet,status"})
    init_req = urllib.request.Request(
        f"{UPLOAD_URL}?{query}",
        data=json.dumps(metadata).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(size),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(init_req, timeout=60) as response:
            upload_uri = response.headers.get("Location")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"YouTube upload initialization failed (HTTP {exc.code}): {detail[:1000]}") from exc
    if not upload_uri:
        raise RuntimeError("YouTube did not return a resumable upload URL.")

    put_req = urllib.request.Request(
        upload_uri,
        data=VIDEO.read_bytes(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(size),
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(put_req, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"YouTube video upload failed (HTTP {exc.code}): {detail[:1000]}") from exc

    video_id = result.get("id")
    if not video_id:
        raise RuntimeError("YouTube response did not contain a video ID.")
    print(f"Private YouTube test upload succeeded. Video ID: {video_id}")
    print(f"Review in YouTube Studio: https://studio.youtube.com/video/{video_id}/edit")


if __name__ == "__main__":
    try:
        main()
    except KeyError as exc:
        print(f"Missing required GitHub Actions secret: {exc}", file=sys.stderr)
        raise SystemExit(1)
