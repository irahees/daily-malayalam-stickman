from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "output"
MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
PROMPT = """Act as the creative director for a Malayalam Shorts channel for Kerala viewers.
Choose one original, compelling 45-60 second topic with a curiosity gap. Prefer surprising
Kerala/India what-if scenarios, everyday economics, science/technology curiosities, or useful facts.
Clearly label hypotheticals; never present them as real events. Do not invent current trends,
statistics, dates, or factual claims. Return ONLY valid JSON with exactly three non-empty string
fields: topic, angle, hook. Write all three in natural Malayalam. The hook must work in the
first 1.2 seconds. No markdown."""


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from GitHub Actions secrets.")
    payload = {
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 700,
            "responseMimeType": "application/json"
        }
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            brief = json.loads(content)
            if not all(isinstance(brief.get(k), str) and brief[k].strip() for k in ("topic", "angle", "hook")):
                raise ValueError("Brief must contain non-empty topic, angle, and hook.")
            OUT.mkdir(parents=True, exist_ok=True)
            path = OUT / "creative_brief.json"
            path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Creative brief generated with Gemini model {MODEL}: {brief['topic']}")
            return
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f"Gemini brief API HTTP {error.code}: {details[:1000]}") from error
            delay = min(30, 2 ** (attempt + 1))
            print(f"Gemini brief request returned HTTP {error.code}; retrying in {delay}s.")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise RuntimeError(f"Gemini brief API connection failed: {error}") from error
            delay = min(30, 2 ** (attempt + 1))
            print(f"Gemini brief connection issue; retrying in {delay}s.")
            time.sleep(delay)


if __name__ == "__main__":
    main()
