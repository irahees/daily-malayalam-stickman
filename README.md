# Daily Malayalam Stickman

A free-first automation project for creating vertical Malayalam stickman videos and preparing them for Instagram Reels, Instagram Stories, and YouTube Shorts.

## Current verified status

- The 2026-11-13 bulk-generation run completed successfully and created seven video files.
- That run's queue job reported seven Instagram Buffer posts as scheduled. A scheduled status is not proof that a post was ultimately published.
- The available run log did not confirm any YouTube uploads or Instagram Story publications.
- The Buffer batch publisher in this branch now targets both the active Instagram and YouTube channels, using the same MP4 URL for each; it checks for existing Buffer posts before creating new ones.
- The Buffer parity audit now compares scheduled pairs separately from already-published pairs. Its authenticated live run has not yet been verified in this PR.
- A pull-request validation workflow runs syntax/unit checks and a read-only Buffer audit when GitHub Actions executes it; no successful run is confirmed yet.
- Do not claim cross-platform sync is working until an authenticated test verifies the same source video, metadata, and publish result on both platforms.

## Production requirements

1. Generate new, distinct Malayalam topics. Check the content inventory before generating to avoid repeats.
2. Use Sarvam Bulbul v3 for Malayalam narration. Do not use Gemini or ElevenLabs.
3. Keep visuals 2D, vertical 1080x1920, 30 fps, with readable Malayalam text.
4. Save the MP4 and its metadata/caption/SEO/hashtag data together as an artifact.
5. Reuse each approved source MP4 for YouTube Shorts and Instagram Reels; do not independently regenerate platform copies.
6. Companion Instagram Stories are not yet included in the batch publisher. If added later and Buffer requires notification publishing, mark the final Instagram action as manual; never label a notification as a published Story.
7. Keep a durable publishing ledger with source video ID, platform post IDs, URLs, scheduled/published timestamps, status, and errors. Do not treat a queued or notification-sent item as published.
8. Use relevant hashtags and platform-specific titles/descriptions. Never invent trends or analytics.
9. Publishing is separate from generation and must be explicitly approved before it is started.

## Workflow status and limitations

- `.github/workflows/weekly-bulk-reels.yml` generates seven videos and saves them as an artifact. It does not prove publishing.
- `.github/workflows/weekly-platform-sync.yml` compares Buffer history only; manual posts outside Buffer are invisible.
- `src/sync_platform_posts.py` compares sent and scheduled Buffer records separately, but its cross-platform matching is still a heuristic based on media URLs and title/date similarity. It is not yet a durable source-video-ID ledger.
- `src/publish_batch_buffer.py` queues the same public MP4 URL to Instagram Reels and YouTube through Buffer, with a duplicate check for the exact URL and a public-URL reachability check. The first authenticated live run still needs to pass before this is considered production-ready.
- The YouTube Data API helper is not part of the publishing path; Buffer handles the connected YouTube channel.
- YouTube API scheduled publishing requires a video to be uploaded with `privacyStatus=private` and a future `publishAt`; YouTube makes it public at that scheduled time. This is YouTube's normal scheduling mechanism, not a permanent private setting.
- Buffer supports Instagram Reels and Stories, but some Story features (text, links, stickers, music) require notification publishing and a final action in the Instagram app. A Buffer notification is not proof the Story is live.
- Instagram automatic publishing requires an eligible Professional account and supported post settings.
- YouTube publishing through this project uses the connected Buffer YouTube channel; separate YouTube Data API OAuth credentials are not required for that path.
- GitHub Actions artifacts are temporary storage, not permanent media hosting.
- Never commit API keys, OAuth tokens, passwords, or private account data.

## Required secrets

- `SARVAM_API_KEY` — required for Malayalam Bulbul v3 narration.
- `BUFFER_API_KEY` — required for Buffer publishing and history checks.
- `BUFFER_ORGANIZATION_ID` — optional only when the Buffer account has multiple organizations.

## Local test

Python 3.11+ and FFmpeg are required.

```bash
pip install -r requirements.txt
python src/create_video.py
```
