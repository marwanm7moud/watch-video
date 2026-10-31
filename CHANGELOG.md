# Changelog

## 0.2.0

- Skill is now CLI-first and agent-agnostic (works with or without the MCP server), with a setup
  check, install steps, a "Network and data" section and troubleshooting.
- New task table and `references/recipes.md`: summary, notes, tutorial-to-steps, find a moment,
  claim check, long video, non-English, token budget.
- Screen recordings and other long-GOP videos: when a video has too few keyframes, the scan now
  adds timed samples so scene selection still covers the whole video.
- Optional OCR (`pip install watch-video[ocr]`, `video-cli overview --ocr`, `ocr=True`): on-screen
  text per keyframe as plain text, new lines only.
- Description rewritten with trigger phrases so agents activate the skill reliably.
- Packaged for PyPI: `pipx install watch-video` / `uvx --from watch-video video-cli`.
- Claude Code plugin and marketplace (`.claude-plugin/`): `/plugin install watch-video@watch-video`
  installs the MCP server and the skill in one step.
- Parakeet now handles all 25 European languages it supports (`--language de`, `fr`, `es`...) instead
  of English only; only other languages fall back to Whisper.
- `search` ranks results: exact phrase first, then by how many words match. It also lists matching
  on-screen text when an `--ocr` overview has run.

## 0.1.0

- Initial public release: `video_overview`, `get_frames`, `scan_range`, `get_transcript`,
  `search_transcript`, `check_hardware` MCP tools, a `video-cli` command and the `watch-video` skill.
