---
name: watch-video
description: Watch and understand an English video (local file or URL - YouTube and 1500+ sites). Use when the user shares a video path/link or asks what happens in a video, to summarize it, find a moment, or read code/slides/charts shown in it.
---

# Watch a video

Tools come from the `video` MCP server (`mcp__video__*`). If it is not connected, run the same
steps through the CLI (installed with the package, or `python -m video_mcp.cli` from a clone of the
repo): `video-cli overview|frames|range|transcript|search <src> ...`, then Read the
printed `IMAGE:` paths.

## Workflow (cheap first, detail on demand)

1. `video_overview(source)` - always first. Gives metadata, chapters, full timestamped transcript
   and contact sheets (small labelled frames, black bars auto-cropped). Answer from this if you can.
   - Mostly-talk video (podcast, lecture): `max_frames=16`.
   - Visual-heavy (tutorial, demo, chart walkthrough): keep 40 or raise to 80.
2. Need to read text/code/UI/chart values at a moment -> `get_frames(source, ["12:30"], hi_res=True)`.
   Pick timestamps from the transcript or the contact-sheet labels. Batch several in one call.
3. Need to follow motion or a step-by-step action -> `scan_range(source, "10:00", "10:30", count=12)`.
4. "Where do they talk about X?" -> `search_transcript` (any of the words matches),
   then `get_frames` at the hits.

## Rules
- Cite timestamps (mm:ss) for every claim about the video.
- Contact-sheet cells are small: never claim exact on-screen text from them - fetch hi-res first.
- Transcripts can mishear names/terms; when it matters, cross-check with on-screen frames.
- Don't re-call `video_overview` for the same video - it's cached, but the images cost tokens again.
- Transcription is English by default (platform subtitles, else Parakeet on CPU). For a non-English
  video, say so; `language="auto"` enables Whisper, which is heavy on CPU - prefer a GPU machine.
