# Recipes

Pick the recipe that matches the request. Every recipe starts with `video-cli overview`.
Cite `mm:ss` timestamps in every output.

## Summarize

1. Run `overview` (`--max-frames 16` if mostly talk).
2. If chapters exist, use them as the outline. If not, group the transcript into 4-8 topic blocks.
3. Output:
   - One-sentence verdict: what the video is and who it is for.
   - 5-8 bullets, each ending with a timestamp `(mm:ss)`.
   - Anything shown only on screen (numbers, code, slides) that the transcript missed, after checking with `frames`.
4. Do not fetch extra frames for a plain summary of a talking-head video.

## Notes or study guide

1. Run `overview`. Walk the transcript in order.
2. Output sections named after chapters or topic blocks. Each section: key points, definitions, any
   formula/code/number (verified with `frames` hi-res), and the start timestamp.
3. End with 3-5 review questions drawn from the content.

## Tutorial or coding video to steps

1. Run `overview --ocr` with the default 40 frames (or 80 for long tutorials). Screen recordings with
   few keyframes are topped up with timed samples automatically.
2. For each step the author performs, note the timestamp from the transcript.
3. Fetch hi-res frames at those timestamps in batches: `video-cli frames <src> t1 t2 t3 ...`.
4. Read code, commands and settings from the OCR text, then confirm them on the frames (OCR loses
   indentation). Do not guess code from the transcript.
5. Output numbered steps: what to do, exact command/code, timestamp. Mark anything you could not read
   as `[unreadable at mm:ss]`.
6. For an action that happens between two frames (a drag, a menu path), use `range` over that span.

## Find a moment

1. `video-cli search <src> "word1 word2"`. Any word matches.
2. No hits: try synonyms, then `transcript` over the likely chapter. Captions may mishear names.
3. If the moment is visual and not spoken (a chart appears, an error dialog), use `range` over each
   chapter with `--count 12`, then narrow down.
4. Report the best timestamp and 1-2 runner-up candidates.

## Check a claim

1. `search` for the claim terms, then `frames` at each hit.
2. Report: what was said (quote + timestamp), what was shown (frame at that time), and whether they agree.
3. If the transcript and the screen disagree, trust the screen and say so.

## Long video (over 1 hour)

1. Run `overview --max-frames 16`. The transcript may be cut at about 60,000 characters with a
   truncation note.
2. Work chapter by chapter: `video-cli transcript <src> <start> <end>` for each chapter.
3. Do not call `overview` again with a bigger frame count. Use `range` on the chapters that matter.
4. If there is no chapter list, split the duration into equal blocks and summarize each block.

## Non-English or no-speech video

- European language (fr, de, es, it, pt, nl, pl, ru, uk...): `--language <code>`, fast on CPU (Parakeet).
- Other languages: tell the user first, then `--language <code>` or `--language auto` (Whisper, slow on CPU).
- No speech: the overview says `(no speech)`. Work from frames only: `range` over the whole video.

## Token budget

- `overview` contact sheets: about 20 frames for the cost of 1.5 full frames. Cheapest visual pass.
- `frames` hi-res: about 1 full image per timestamp. Batch, and only for text that must be exact.
- `range --count 12`: one contact sheet. Use it before many single `frames` calls.
