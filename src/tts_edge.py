from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

VOICE_CANDIDATES = ("ml-IN-MidhunNeural", "ml-IN-SobhanaNeural")


async def _synthesize(text: str, destination: Path, voice: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+0%", volume="+0%", pitch="+0Hz")
    await communicate.save(str(destination))


def create_voice(text: str, destination: Path) -> None:
    """Create Malayalam narration with free Edge TTS voices; no paid API key is used."""
    if not text.strip():
        raise RuntimeError("Narration text is empty.")
    if len(text) > 5000:
        raise RuntimeError("Narration is too long for one Edge TTS request.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to convert narration to WAV.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    mp3_path = destination.with_suffix(".edge.mp3")
    errors: list[str] = []
    for voice in VOICE_CANDIDATES:
        try:
            asyncio.run(_synthesize(text, mp3_path, voice))
            if not mp3_path.is_file() or mp3_path.stat().st_size < 1024:
                raise RuntimeError("TTS returned an empty audio file.")
            subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp3_path),
                 "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(destination)],
                check=True, timeout=180,
            )
            data = destination.read_bytes()
            if len(data) < 1024 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
                raise RuntimeError("TTS conversion did not produce a valid WAV file.")
            print(f"Malayalam narration ready. Provider=Edge TTS; voice={voice}; bytes={len(data)}")
            return
        except Exception as error:
            errors.append(f"{voice}: {type(error).__name__}")
        finally:
            mp3_path.unlink(missing_ok=True)

    raise RuntimeError("All free Malayalam Edge TTS voices failed: " + "; ".join(errors))
