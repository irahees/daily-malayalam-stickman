# Daily Malayalam Stickman

A free-first automation project for creating vertical Malayalam stickman videos and preparing them for Instagram Reels and YouTube Shorts.

## Current stage

This repository is the project foundation. It does **not** publish anything yet.

### Planned pipeline
1. Generate an original Malayalam story and narration.
2. Create a vertical 1080x1920 stickman storyboard.
3. Generate Malayalam voice audio and timed subtitles.
4. Render an MP4 with FFmpeg.
5. Prepare platform-specific captions and metadata.
6. Review the output, then connect Instagram and YouTube publishing.
7. Track available performance metrics and improve future content.

## Important limitations
- GitHub Actions is the scheduler and runner, not permanent video storage.
- Public-repository GitHub-hosted standard runners have usage limits and scheduled jobs can be delayed.
- Free AI and text-to-speech services have quotas and may change or stop working.
- Instagram publishing requires an eligible professional account and Meta permissions.
- YouTube uploads require Google OAuth and YouTube Data API access.
- Automatic publishing will remain disabled until credentials are configured and a test upload is approved.
- Never commit API keys, OAuth tokens, passwords, or private account data.

## Local test
Python 3.11+ and FFmpeg are required.

```bash
pip install -r requirements.txt
python src/create_video.py
```

The initial renderer creates a sample vertical stickman video. It is a foundation, not yet the finished daily AI workflow.

## GitHub Actions
The workflow can be started manually from the Actions tab. A daily schedule will be enabled after the render pipeline is tested.

## Secrets
Do not add secrets until the relevant integration is implemented. Use GitHub repository Settings → Secrets and variables → Actions.
