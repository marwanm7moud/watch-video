# watch-video

Let Claude (or any MCP client) **watch a video**. Give it a local file or a URL (YouTube and 1,500+
other sites via yt-dlp) and it gets a timestamped transcript plus a handful of scene-selected
keyframes, then drills into exact frames only when needed. No cloud transcription, no API keys.

It ships as two parts:

- **`video` MCP server** with six tools (below).
- **`watch-video` skill** that teaches Claude the cheap-first workflow: overview, then frames, then ranges.

## How it works

| Step | What happens |
|---|---|
| Transcript | Platform subtitles if the video has them (seconds), else **Parakeet TDT 0.6B v3** (int8, CPU, English), else **faster-whisper large-v3-turbo** (GPU or `language="auto"`). |
| Keyframes | Decodes *only* keyframes at thumbnail size, drops repeats and static slides, then fills the largest time gaps. The selection adapts to how much the video changes (screencast vs. action). |
| Contact sheets | Labelled frames tiled into grids: about 20 frames for the token cost of 1.5 full frames. Black bars are cropped automatically. |
| Drill-down | `get_frames` seeks to exact timestamps at 1280 px (readable code and charts). For URLs it seeks into the stream without downloading the whole video. |

Everything is cached under `~/.cache/video_mcp`, so repeat calls are instant.

Measured on a mid-range CPU (i5-11400, no GPU): 35.7-minute local video overview in about 2.6 minutes;
YouTube video with subtitles in about 7 seconds; a drill-down frame in about 0.5 seconds.

## Install

Requirements: Python 3.10+ and [ffmpeg](https://ffmpeg.org/download.html) (including `ffprobe`) on your PATH.

```bash
pip install git+https://github.com/marwanm7moud/watch-video
# optional: Whisper for non-English videos / GPU machines
pip install "watch-video[whisper] @ git+https://github.com/marwanm7moud/watch-video"
```

Install ffmpeg with `winget install Gyan.FFmpeg` (Windows), `brew install ffmpeg` (macOS) or
`sudo apt install ffmpeg` (Linux). The first transcription downloads the Parakeet model (about 650 MB).

### Register the MCP server

Claude Code:

```bash
claude mcp add video --scope user -- video-mcp
```

Claude Desktop (`claude_desktop_config.json`) or any other MCP client:

```json
{ "mcpServers": { "video": { "command": "video-mcp" } } }
```

If `video-mcp` is not on your PATH, use the full path to the executable or `python -m video_mcp.server`.

### Install the skill

Copy the skill folder so Claude knows when and how to use the tools:

```bash
# macOS / Linux
mkdir -p ~/.claude/skills && cp -r skills/watch-video ~/.claude/skills/
# Windows (PowerShell)
Copy-Item -Recurse skills\watch-video $HOME\.claude\skills\
```

Then ask Claude: *"Watch https://youtu.be/... and summarize it"*, or *"At what point do they explain the stop-loss, and what does the chart show then?"*

## Tools

| Tool | Use |
|---|---|
| `video_overview(source, max_frames=40)` | Start here: metadata, chapters, full transcript, contact sheets. |
| `get_frames(source, timestamps, hi_res=True)` | Exact frames (`"12:30"`, `"1:02:05"` or seconds), up to 20. |
| `scan_range(source, start, end, count=12)` | Evenly spaced frames in one sheet, to follow motion or a demo. |
| `get_transcript(source, start, end)` | Transcript slice. |
| `search_transcript(source, query)` | Timestamped hits for any of the words. |
| `check_hardware()` | Detected tools, GPU and the transcription profile in use. |

## Command line

The same operations work without MCP:

```bash
video-cli overview video.mp4 --max-frames 16
video-cli frames https://youtu.be/... 12:30 13:05
video-cli range video.mp4 10:00 10:30 --count 12
video-cli search video.mp4 "stop loss"
video-cli hw
```

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `VIDEO_MCP_CACHE` | `~/.cache/video_mcp` | Cache directory (delete it to reclaim space). |
| `VIDEO_MCP_LANG` | `en` | Default transcription language; `auto` detects it with Whisper. |
| `VIDEO_MCP_THREADS` | `4` (CPU) | Threads for CPU transcription. |
| `VIDEO_MCP_AVX512` | unset | Set to `1` to let Whisper use AVX-512 (faster, but a very heavy sustained load). |

On CPU the server runs below normal priority, one heavy job at a time, with Whisper held to AVX2, so a
long transcription does not freeze your desktop.

## Limitations

- Transcription is English-first. Other languages need Whisper (`language="auto"`), which is slow on CPU.
- Frames are sampled, not every frame is analysed; the transcript can mishear names and terms. The skill tells
  Claude to cite timestamps and confirm exact on-screen text with a hi-res frame.
- Use it only on videos you are allowed to access and process; respect each site's terms and copyright.

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

## License

MIT. See [LICENSE](LICENSE).
