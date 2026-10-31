# watch-video

<!-- mcp-name: io.github.marwanm7moud/watch-video -->

Let Claude (or any MCP client) **watch a video**. Give it a local file or a URL (YouTube and 1,500+
other sites via yt-dlp) and it gets a timestamped transcript plus a handful of scene-selected
keyframes, then drills into exact frames only when needed. No cloud transcription, no API keys.

```text
> Watch https://www.youtube.com/watch?v=jNQXAC9IVRw and tell me what he says about the elephants.

$ video-cli overview https://www.youtube.com/watch?v=jNQXAC9IVRw --max-frames 8
# Me at the zoo
duration: 00:19
transcript: platform-subs:en, language=en, 6 segments, took 0.4s
keyframes: 3 scene-selected at 00:00, 00:05, 00:11
total time: 6.7s

## Transcript
[00:01] All right, so here we are, in front of the elephants
[00:05] the cool thing about these guys is that they have really... really really long trunks and that's cool
[00:16] and that's pretty much all there is to say
IMAGE: ~/.cache/video_mcp/Youtube_jNQXAC9IVRw/sheets_8/sheet_01.jpg

Claude: He stands in front of the elephants (00:01) and says the cool thing about them is
their really long trunks (00:05). That is the whole video (00:16).
```

## Why this one

| | watch-video | Cloud video APIs (e.g. Gemini) | Transcript-only tools |
|---|---|---|---|
| Sees the screen (code, slides, charts, UI) | Yes: keyframes, hi-res frames, OCR | Yes | No |
| Runs locally, nothing uploaded | Yes | No: the video goes to the provider | Varies |
| API key or account | None | Required, billed per use | Varies |
| Videos without captions | Local Parakeet / Whisper | Yes | Often fails |
| Token cost of the visual pass | ~20 frames per contact sheet (cost of ~1.5 images) | Billed by video length | None (no visuals) |
| Private recordings (meetings, bug repros) | Safe: never leave the machine | Uploaded | Varies |

It ships as two parts:

- **`video` MCP server** with six tools (below).
- **`watch-video` skill** that teaches Claude the cheap-first workflow: overview, then frames, then ranges.

## How it works

| Step | What happens |
|---|---|
| Transcript | Platform subtitles if the video has them (seconds), else **Parakeet TDT 0.6B v3** (int8, CPU, 25 European languages), else **faster-whisper large-v3-turbo** (other languages, GPU or `language="auto"`). |
| Keyframes | Decodes *only* keyframes at thumbnail size, drops repeats and static slides, then fills the largest time gaps. The selection adapts to how much the video changes (screencast vs. action). |
| Contact sheets | Labelled frames tiled into grids: about 20 frames for the token cost of 1.5 full frames. Black bars are cropped automatically. |
| Drill-down | `get_frames` seeks to exact timestamps at 1280 px (readable code and charts). For URLs it seeks into the stream without downloading the whole video. |

Everything is cached under `~/.cache/video_mcp`, so repeat calls are instant.

Measured on a mid-range CPU (i5-11400, no GPU): 35.7-minute local video overview in about 2.6 minutes;
YouTube video with subtitles in about 7 seconds; a drill-down frame in about 0.5 seconds.

## Install

Requirements: Python 3.10+ and [ffmpeg](https://ffmpeg.org/download.html) (including `ffprobe`) on your PATH.

### Claude Code: one command (plugin)

Installs the MCP server and the skill together. Needs [uv](https://docs.astral.sh/uv/) for `uvx`.

```text
/plugin marketplace add marwanm7moud/watch-video
/plugin install watch-video@watch-video
```

### Any agent: package, server, skill

```bash
pipx install watch-video          # or: uv tool install watch-video / pip install watch-video
# optional extras: Whisper (non-European languages / GPU) and OCR (on-screen text as text)
pipx install "watch-video[whisper,ocr]"
# latest from GitHub instead of PyPI:
pip install git+https://github.com/marwanm7moud/watch-video
```

No install needed to try the CLI: `uvx --from watch-video video-cli hw`.

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

The skill works with or without the MCP server: it falls back to `video-cli` and installs it on first use.
Copy the skill folder so your agent knows when and how to use the tools:

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
| `video_overview(source, max_frames=40, ocr=False)` | Start here: metadata, chapters, full transcript, contact sheets. `ocr=True` adds on-screen text. |
| `get_frames(source, timestamps, hi_res=True)` | Exact frames (`"12:30"`, `"1:02:05"` or seconds), up to 20. |
| `scan_range(source, start, end, count=12)` | Evenly spaced frames in one sheet, to follow motion or a demo. |
| `get_transcript(source, start, end)` | Transcript slice. |
| `search_transcript(source, query)` | Timestamped hits for any of the words, exact phrase first; plus on-screen text after an `ocr=True` overview. |
| `check_hardware()` | Detected tools, GPU and the transcription profile in use. |

## Command line

The same operations work without MCP:

```bash
video-cli overview video.mp4 --max-frames 16
video-cli overview demo.mp4 --ocr          # also read code/slides on screen
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

- English is assumed unless you pass `language`. Parakeet covers 25 European languages on CPU (`language="de"`,
  `"fr"`, `"es"`, ...). Other languages (Arabic, Chinese, Japanese, Hindi, ...) need Whisper, which is slow on CPU.
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
