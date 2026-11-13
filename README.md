# Daily Malayalam Stickman

A free-first automation project for creating vertical Malayalam stickman videos and preparing them for Instagram Reels and YouTube Shorts.

## Current stage

The video workflows generate Malayalam videos and save review artifacts. Publishing is kept separate from generation and requires an explicit approval action. A weekly YouTube–Instagram sync audit compares posts recorded by Buffer and creates a report of missing counterparts. With the manual approval input enabled, it can create Buffer drafts for missing counterparts; it never publishes them automatically.

### Planned pipeline
1. Generate an original Malayalam story and narration.
2. Create a vertical 1080x1920 stickman storyboard.
3. Generate Malayalam voice audio and timed subtitles.
4. Render an MP4 with FFmpeg.
5. Prepare platform-specific captions and metadata.
6. After review and explicit approval, prepare the same approved video for Instagram Reels and YouTube Shorts through Buffer.

## Important limitations
- GitHub Actions is the scheduler and runner, not permanent video storage.
- Public-repository GitHub-hosted standard runners have usage limits and scheduled jobs can be delayed.
- Free AI and text-to-speech services have quotas and may change or stop working.
- Instagram publishing requires an eligible professional account and Meta permissions.
- YouTube uploads require Google OAuth and YouTube Data API access.
- Video generation does not publish. Publishing and cross-platform sync actions are separate and approval-gated.
- Never commit API keys, OAuth tokens, passwords, or private account data.

## Local test
Python 3.11+ and FFmpeg are required.

```bash
pip install -r requirements.txt
python src/create_video.py
```

The initial renderer creates a sample vertical stickman video. It is a foundation, not yet the finished daily AI workflow.

## GitHub Actions
The daily video-generation workflow runs on its own schedule. Publishing is a separate manual action in the Actions tab.

## Secrets
Do not add secrets until the relevant integration is implemented. Use GitHub repository Settings → Secrets and variables → Actions.


## Publish through Buffer (manual)

The daily workflow only generates and stores a video artifact. The separate publish workflows must be deliberately run after reviewing and approving the content. The weekly platform-sync audit reports missing counterparts and can create Buffer drafts only when its manual approval input is enabled.

1. Add the Buffer personal API key as the repository Actions secret `BUFFER_API_KEY` (never commit the key).
2. Add `SARVAM_API_KEY` for Malayalam Bulbul v3 TTS, or keep `GEMINI_API_KEY` configured as the preferred TTS provider.
3. The daily workflow publishes after video generation. It creates a unique public GitHub Release asset URL because Buffer fetches video files from public HTTPS URLs.
4. The manual workflow can publish a previous successful artifact by run ID.

The MP4 in each GitHub Release is publicly accessible. The publisher requires exactly one Instagram channel and one YouTube channel in the Buffer account; it stops rather than guessing if either is missing or duplicated. AI-generated-content disclosure is enabled in both channel metadata. Buffer must have permission to publish to both channels, and channel-specific publishing restrictions still apply.


## YouTube–Instagram sync

- `.github/workflows/weekly-platform-sync.yml` runs every Sunday at 19:00 IST and saves a sync report as a GitHub Actions artifact.
- The audit compares sent posts recorded by the connected Buffer organization. Posts published manually outside Buffer are not visible to this audit.
- Matching uses the shared first-line title, posting date, and asset URL when available. Review uncertain matches before acting.
- To create missing counterparts as Buffer drafts, manually run **Weekly YouTube Instagram Sync Audit** and set `create_missing_drafts=true`.
- This creates drafts only. It does not publish or schedule posts. Review each draft in Buffer and publish it yourself.
- If the Buffer account has multiple organizations, set the GitHub Actions secret `BUFFER_ORGANIZATION_ID` to the intended organization ID.
