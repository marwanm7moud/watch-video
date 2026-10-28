"""High-level operations shared by the MCP server and the CLI."""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from . import frames as fr
from . import hw
from .source import Video
from .transcribe import as_text, fmt_ts, transcribe

_videos = {}
MAX_TRANSCRIPT_CHARS = 60000


def get_video(src):
    if src not in _videos:
        _videos[src] = Video(src)
    return _videos[src]


def overview(src, max_frames=40, engine="auto", language=None):
    """Metadata + full transcript + contact sheets. Transcription and frame scan run in parallel."""
    t0 = time.time()
    v = get_video(src)
    meta = v.meta()
    if hw.profile()["device"] == "cuda":  # GPU does ASR, so CPU is free for ffmpeg in parallel
        with ThreadPoolExecutor(2) as ex:
            ft = ex.submit(transcribe, v, engine, language)
            fk = ex.submit(fr.keyframes, v, max_frames)
            tr, kf = ft.result(), fk.result()
    else:  # CPU only: one heavy job at a time (frames take seconds, ASR minutes)
        kf = fr.keyframes(v, max_frames)
        tr = transcribe(v, engine, language)
    sheets = fr.contact_sheets(kf, os.path.join(v.dir, f"sheets_{max_frames}"))
    text = as_text(tr["segments"])
    truncated = len(text) > MAX_TRANSCRIPT_CHARS
    if truncated:
        text = text[:MAX_TRANSCRIPT_CHARS] + "\n... [truncated: use get_transcript(start, end) for the rest]"
    head = [f"# {meta.get('title')}", f"source: {meta.get('source')}",
            f"duration: {fmt_ts(meta.get('duration') or 0)}"]
    if meta.get("channel"):
        head.append(f"channel: {meta['channel']}")
    if meta.get("chapters"):
        head.append("chapters:\n" + "\n".join(f"  [{fmt_ts(c['start'])}] {c['title']}" for c in meta["chapters"]))
    if meta.get("description"):
        head.append("description: " + meta["description"][:800])
    head.append(f"transcript: {tr['engine']}, language={tr.get('language')}, {len(tr['segments'])} segments, "
                f"took {tr.get('seconds')}s")
    head.append(f"keyframes: {len(kf)} scene-selected at " + ", ".join(fmt_ts(t) for t, _ in kf))
    head.append(f"contact sheets: {len(sheets)} (timestamp in each cell's top-left)")
    head.append(f"total time: {time.time() - t0:.1f}s")
    return {"text": "\n".join(head) + "\n\n## Transcript\n" + (text or "(no speech)"), "images": sheets,
            "timings": {"transcribe_s": tr.get("seconds"), "total_s": round(time.time() - t0, 1)}}


def parse_ts(x):
    if isinstance(x, (int, float)):
        return float(x)
    parts = [float(p) for p in str(x).strip().split(":")]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def get_frames(src, timestamps, hi_res=True):
    """Exact frames at given timestamps. hi_res=1280px (read code/text), else 768px."""
    v = get_video(src)
    times = [parse_ts(t) for t in timestamps][:20]
    inp = v.hires_input() if hi_res else (v.scan_file() if v.url else v.local_path)
    out = fr.extract(inp, times, os.path.join(v.dir, "frames"), long_side=1280 if hi_res else 768,
                     crop=fr.crop_for(v))
    return {"text": "frames: " + ", ".join(fmt_ts(t) for t, _ in out), "images": [p for _, p in out]}


def scan_range(src, start, end, count=12):
    """Evenly sampled frames over [start, end] tiled into one contact sheet — for action/motion."""
    v = get_video(src)
    a, b = parse_ts(start), parse_ts(end)
    count = max(2, min(int(count), 40))
    times = [round(a + (b - a) * i / (count - 1), 2) for i in range(count)]
    inp = v.scan_file() if v.url else v.local_path
    out = fr.extract(inp, times, os.path.join(v.dir, "frames"), long_side=768, crop=fr.crop_for(v))
    d = os.path.join(v.dir, f"range_{int(a)}_{int(b)}_{count}")
    sheets = fr.contact_sheets(out, d)
    return {"text": f"{len(out)} frames {fmt_ts(a)}-{fmt_ts(b)} every {(b - a) / (count - 1):.1f}s",
            "images": sheets}


def get_transcript(src, start=0, end=None, engine="auto", language=None):
    v = get_video(src)
    a, b = parse_ts(start), parse_ts(end) if end is not None else 1e12
    tr = transcribe(v, engine, language)
    segs = [s for s in tr["segments"] if s["end"] >= a and s["start"] <= b]
    return {"text": as_text(segs) or "(no speech in range)", "images": []}


def search_transcript(src, query, context=1):
    """Case-insensitive search (any of the space-separated words). Returns hits with neighbours."""
    v = get_video(src)
    segs = transcribe(v)["segments"]
    words = [w for w in re.split(r"\s+", query.lower()) if w]
    hits = [i for i, s in enumerate(segs) if any(w in s["text"].lower() for w in words)]
    blocks, seen = [], set()
    for i in hits[:30]:
        rng = [j for j in range(i - context, i + context + 1) if 0 <= j < len(segs) and j not in seen]
        seen.update(rng)
        blocks.append("\n".join(f"[{fmt_ts(segs[j]['start'])}] {segs[j]['text']}" for j in rng))
    return {"text": f"{len(hits)} hits for '{query}'\n\n" + "\n---\n".join(blocks) if hits
            else f"no hits for '{query}'", "images": []}
