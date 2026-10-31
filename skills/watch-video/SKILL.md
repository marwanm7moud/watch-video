---
name: watch-video
description: Watch and understand a video from a local file or URL (YouTube and 1500+ sites) by reading its timestamped transcript and keyframes. Use when the user shares a video link or path, or asks to summarize a video, transcribe it, find the moment where something is said, or read code, slides, charts or UI shown on screen at a given time.
---

# Watch a video

Runs fully local: no API keys, no cloud transcription. Transcript from platform subtitles, else
Parakeet (25 European languages, CPU), else Whisper (other languages or GPU).

## 0. Setup check (once per session)

Run `video-cli --version`.

- Works: continue.
- `command not found`: install with `pipx install watch-video-mcp` (or `uv tool install watch-video-mcp`,
  or `pip install watch-video-mcp`). Then run `video-cli --version` again.
- Run `video-cli hw`. If `ffmpeg` or `ffprobe` is missing, tell the user to install it
  (`winget install Gyan.FFmpeg`, `brew install ffmpeg`, `sudo apt install ffmpeg`). Do not continue without it.
- First transcription without subtitles downloads a ~650 MB model. Tell the user before starting.

If the `video` MCP server is connected (tools named `video_overview`, `get_frames`, `scan_range`,
`get_transcript`, `search_transcript`, with an `mcp__video__` or `mcp__plugin_watch-video_video__` prefix),
call those tools instead of the CLI. The arguments are identical.

## Workflow (cheap first, detail on demand)

CLI output ends with `IMAGE: <path>` lines. Read each image path to see the frames.

1. `video-cli overview <src> [--max-frames N]` - always first. Gives metadata, chapters, full
   timestamped transcript and contact sheets (small labelled frames, black bars auto-cropped).
   Answer from this if you can.
   - Mostly-talk video (podcast, lecture): `--max-frames 16`.
   - Visual-heavy (tutorial, demo, chart walkthrough): keep the default 40, or use 80.
   - Slides, code or UI on screen: add `--ocr`. It lists the on-screen text per keyframe as plain text
     (new lines only), cheaper and more exact than reading images. Needs `pipx install "watch-video-mcp[ocr]"`;
     `video-cli hw` shows whether OCR is installed. OCR drops leading spaces and may split words, so
     confirm indentation or exact code with a hi-res `frames` call.
2. Need to read text, code, UI or chart values at a moment: `video-cli frames <src> 12:30 13:05`.
   Pick timestamps from the transcript or the contact-sheet labels. Batch several in one call.
3. Need to follow motion or a step-by-step action: `video-cli range <src> 10:00 10:30 --count 12`.
4. "Where do they talk about X?": `video-cli search <src> "x"` (any word matches, exact phrase ranked
   first), then `frames` at the hits. After an `--ocr` overview it also lists matching on-screen text.
   `video-cli transcript <src> 10:00 12:00` returns a slice.

## Pick the task

| User wants | Do |
|---|---|
| Summary or "what is this about" | `overview`, answer from transcript and chapters |
| Notes, study guide | `overview`, then sections per chapter |
| Steps or code from a tutorial | `overview`, then hi-res `frames` at each step |
| Where something is said or shown | `search`, then `frames` or `range` |
| Is a claim true | `search`, then `frames`, compare |
| Video over 1 hour | `overview --max-frames 16`, then `transcript` per chapter |

Read `references/recipes.md` for the output format of each task before you write the answer.

## Rules

- Cite timestamps (mm:ss) for every claim about the video.
- Contact-sheet cells are small: never claim exact on-screen text from them. Fetch hi-res frames first.
- Transcripts can mishear names and terms. When it matters, cross-check with on-screen frames.
- Do not re-run `overview` for the same video. It is cached, but the images cost tokens again.
- Transcription assumes English. Parakeet also handles 24 other European languages (French, German,
  Spanish, Russian, Ukrainian...): pass `--language <code>`, e.g. `--language de`. For other languages
  (Arabic, Chinese, Japanese, Hindi...) tell the user, then use `--language <code>` or `--language auto`
  (Whisper, needs `watch-video-mcp[whisper]`, heavy on CPU; prefer a GPU machine).
- Only process videos the user is allowed to access.

## Network and data

- URLs: `yt-dlp` fetches metadata, captions and a low-res copy (or audio) into the local cache.
  `frames` on a URL seeks into the stream and does not download the whole video.
- First run without subtitles downloads the Parakeet model from Hugging Face. Whisper models
  download only when Whisper is used.
- Cache lives in `~/.cache/video_mcp` (override with `VIDEO_MCP_CACHE`). Delete it to reclaim space.
- Nothing is uploaded anywhere. No telemetry. No credentials are read or stored.

## Troubleshooting

- `video-cli hw` shows detected tools and the transcription profile in use.
- Very long video on CPU is slow: use `--engine subs` when captions exist, or work on a time range.
- Private or age-gated URL fails in `yt-dlp`: ask the user for a local file.
