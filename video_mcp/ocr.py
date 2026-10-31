"""Optional on-screen text extraction (RapidOCR, ONNX, CPU). Install with `pip install watch-video-mcp[ocr]`."""
import json
import os

from . import frames as fr
from .transcribe import fmt_ts

MAX_OCR_CHARS = 20000
MIN_CONF = 0.6

_engine = []


def available():
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def _read(path):
    if not _engine:
        from rapidocr_onnxruntime import RapidOCR
        _engine.append(RapidOCR())
    res, _ = _engine[0](path)
    # top-to-bottom, left-to-right reading order
    items = sorted(res or [], key=lambda r: (round(r[0][0][1] / 12), r[0][0][0]))
    return [r[1].strip() for r in items if r[2] >= MIN_CONF and r[1].strip()]


def new_lines(per_frame):
    """[(t, [lines])] -> [(t, [lines not already on the previous frame])]; drops empty frames."""
    out, prev = [], set()
    for t, lines in per_frame:
        fresh = [ln for ln in lines if ln not in prev]
        prev = set(lines)
        if fresh:
            out.append((t, fresh))
    return out


def format_ocr(per_frame, limit=MAX_OCR_CHARS):
    text = "\n".join(f"[{fmt_ts(t)}] " + " | ".join(lines) for t, lines in new_lines(per_frame))
    if len(text) > limit:
        text = text[:limit] + "\n... [truncated: use get_frames on the timestamps you need]"
    return text


def cached(video):
    """[(t, [lines])] already OCRed for this video, in time order; empty if OCR never ran."""
    cache = os.path.join(video.dir, "ocr.json")
    if not os.path.exists(cache):
        return []
    done = json.load(open(cache, encoding="utf-8"))
    return sorted((float(t), lines) for t, lines in done.items())


def screen_text(video, times, long_side=1280):
    """OCR the given timestamps (cached). Frames are grabbed unlabelled at hi-res so text is readable."""
    if not available():
        raise RuntimeError('OCR is not installed. Run: pip install "watch-video-mcp[ocr]"')
    cache = os.path.join(video.dir, "ocr.json")
    done = json.load(open(cache, encoding="utf-8")) if os.path.exists(cache) else {}
    todo = [t for t in times if f"{t:.2f}" not in done]
    if todo:
        got = fr.extract(video.hires_input(), todo, os.path.join(video.dir, "frames"), long_side=long_side,
                         label=False, crop=fr.crop_for(video))
        for t, p in got:
            done[f"{t:.2f}"] = _read(p)
        json.dump(done, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return [(t, done.get(f"{t:.2f}", [])) for t in times]
