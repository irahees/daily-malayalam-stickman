# Daily Malayalam Stickman

A free-first automation project for creating vertical Malayalam stickman videos and preparing them for Instagram Reels, Instagram Stories, and YouTube Shorts.

## Current verified status

- The 2026-11-13 bulk-generation run completed successfully and created seven video files.
- That run's queue job reported seven Instagram Buffer posts as scheduled. A scheduled status is not proof that a post was ultimately published.
- The available run log did not confirm any YouTube uploads or Instagram Story publications.
- The two-way sync workflow in this branch is still a draft and has not completed an authenticated Buffer API test.
- Do not claim cross-platform sync is working until an authenticated test verifies the same source video, metadata, and publish result on both platforms.

## Production requirements

1. Generate new, distinct Malayalam topics. Check the content inventory before generating to avoid repeats.
2. Use Sarvam Bulbul v3 for Malayalam narration. Do not use Gemini or ElevenLabs.
3. Keep visuals 2D, vertical 1080x1920, 30 fps, with readable Malayalam text.
4. Save the MP4 and its metadata/caption/SEO/hashtag data together as an artifact.
5. Reuse each approved source MP4 for YouTube Shorts and Instagram Reels; do not independently regenerate platform copies.
6. Prepare a companion Instagram Story for each Reel where the connected publishing method supports it. If Buffer requires notification publishing for Story features, mark it as manual action required and never label it auto-published.
7. Keep a durable publishing ledger with source video ID, platform post IDs, URLs, scheduled/published timestamps, status, and errors. Do not treat a queued or notification-sent item as published.
8. Use relevant hashtags and platform-specific titles/descriptions. Never invent trends or analytics.
9. Publishing is separate from generation and must be explicitly approved before it is started.

## Workflow status and limitations

- `.github/workflows/weekly-bulk-reels.yml` generates seven videos and saves them as an artifact. It does not prove publishing.
- `.github/workflows/weekly-platform-sync.yml` is intended to compare Buffer history. It currently sees Buffer records only; manual posts outside Buffer are invisible.
- The sync script uses an assumed Buffer GraphQL shape and has not yet passed a real authenticated API test. Do not merge or enable it as a production automation until validated.
- YouTube API scheduled publishing requires a video to be uploaded with `privacyStatus=private` and a future `publishAt`; YouTube makes it public at that scheduled time. This is YouTube's normal scheduling mechanism, not a permanent private setting.
- Buffer supports Instagram Reels and Stories, but some Story features (text, links, stickers, music) require notification publishing and a final action in the Instagram app. A Buffer notification is not proof the Story is live.
- Instagram automatic publishing requires an eligible Professional account and supported post settings.
- YouTube uploads require valid Google OAuth credentials and YouTube Data API access.
- GitHub Actions artifacts are temporary storage, not permanent media hosting.
- Never commit API keys, OAuth tokens, passwords, or private account data.

## Required secrets

- `SARVAM_API_KEY` — required for Malayalam Bulbul v3 narration.
- `BUFFER_API_KEY` — required for Buffer publishing and history checks.
- `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` — required only after the YouTube publisher is implemented and verified.
- `BUFFER_ORGANIZATION_ID` — optional only when the Buffer account has multiple organizations.

## Local test

Python 3.11+ and FFmpeg are required.

```bash
pip install -r requirements.txt
python src/create_video.py
```
