from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "output"
MODEL = os.getenv("OPENAI_STORY_MODEL", "gpt-4o-mini")

PROMPT = """Act as the creative director for a Malayalam Shorts channel for Kerala viewers.
Choose one original, compelling 45-60 second topic with a curiosity gap. Prefer surprising
Kerala/India what-if scenarios, everyday economics, science/technology curiosities, or useful facts.
Clearly label hypotheticals; never present them as real events. Do not invent current trends,
statistics, dates, or factual claims. Return ONLY valid JSON with exactly three non-empty string
fields: topic, angle, hook. Write all three in natural Malayalam. The hook must work in the
first 1.2 seconds. No markdown."""


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a creative director. Return valid JSON only."},
            {"role": "user", "content": PROMPT},
        ],
        "temperature": 0.9,
        "max_completion_tokens": 700,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.loads(response.read().decode("utf-8"))
            brief = json.loads(result["choices"][0]["message"]["content"])
            if not all(isinstance(brief.get(k), str) and brief[k].strip() for k in ("topic", "angle", "hook")):
                raise ValueError("Brief must contain non-empty topic, angle, and hook.")
            OUT.mkdir(parents=True, exist_ok=True)
            path = OUT / "opencode_brief.json"
            path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Creative brief generated with {MODEL}: {brief['topic']}")
            return
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f"OpenAI brief API HTTP {error.code}: {details[:1000]}") from error
            delay = min(30, 2 ** (attempt + 1))
            print(f"OpenAI brief request temporarily failed ({error.code}); retrying in {delay}s.")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise RuntimeError(f"OpenAI brief API connection failed: {error}") from error
            delay = min(30, 2 ** (attempt + 1))
            print(f"OpenAI brief connection issue; retrying in {delay}s.")
            time.sleep(delay)


if __name__ == "__main__":
    main()
