# Daily Malayalam Stickman

A free-first automation project for creating vertical Malayalam stickman videos and preparing them for Instagram Reels and YouTube Shorts.

## Current stage

The daily workflow generates a Malayalam video, saves a review artifact, hosts a public media copy as a GitHub Release asset, and sends it to the connected Instagram and YouTube channels through Buffer. A separate manual workflow can also publish a previously generated artifact.

### Planned pipeline
1. Generate an original Malayalam story and narration.
2. Create a vertical 1080x1920 stickman storyboard.
3. Generate Malayalam voice audio and timed subtitles.
4. Render an MP4 with FFmpeg.
5. Prepare platform-specific captions and metadata.
6. Publish the generated video to connected Instagram Reels and YouTube Shorts through Buffer after a successful generation run.

## Important limitations
- GitHub Actions is the scheduler and runner, not permanent video storage.
- Public-repository GitHub-hosted standard runners have usage limits and scheduled jobs can be delayed.
- Free AI and text-to-speech services have quotas and may change or stop working.
- Instagram publishing requires an eligible professional account and Meta permissions.
- YouTube uploads require Google OAuth and YouTube Data API access.
- The daily workflow includes an automatic Buffer publishing job. It runs only after video generation and artifact validation succeed.
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

The daily workflow automatically sends a successfully generated video to Buffer. The `Publish Existing Malayalam Video` workflow is also available for manually sending a selected previous artifact.

1. Add the Buffer personal API key as the repository Actions secret `BUFFER_API_KEY` (never commit the key).
2. Add `SARVAM_API_KEY` for Malayalam Bulbul v3 TTS, or keep `GEMINI_API_KEY` configured as the preferred TTS provider.
3. The daily workflow publishes after video generation. It creates a unique public GitHub Release asset URL because Buffer fetches video files from public HTTPS URLs.
4. The manual workflow can publish a previous successful artifact by run ID.

The MP4 in each GitHub Release is publicly accessible. The publisher requires exactly one Instagram channel and one YouTube channel in the Buffer account; it stops rather than guessing if either is missing or duplicated. AI-generated-content disclosure is enabled in both channel metadata. Buffer must have permission to publish to both channels, and channel-specific publishing restrictions still apply.
