# Blender 3D renderer (preview stage)

This repository has an isolated Blender preview pipeline. It does not replace the daily publisher or change upload settings.

## What it renders
- A portrait 3D Kerala petrol-station environment: shop facade, canopy, three fuel dispensers, coconut palms, road and a moving car.
- A rounded 3D presenter built from separate meshes, with animation, perspective camera and area lighting.
- 90 frames at 30 fps, encoded to a 720x1280 MP4.

## Run on GitHub
1. Open Actions in the repository.
2. Select the workflow named Blender 3D Preview.
3. Choose Run workflow.
4. When it completes, download the blender-3d-preview artifact.

## Important
This is a technical proof of concept, not yet the production Malayalam renderer. The current daily renderer remains unchanged. Malayalam subtitles and narration are not yet composited into this preview. Next, the Blender scene system can be generalized to build story-specific locations and character actions from output/story.json, then subtitles can be overlaid with the existing RAQM-enabled Pillow pipeline and narration muxed with FFmpeg.

It uses open-source Blender and FFmpeg and does not require a paid video-generation API.
