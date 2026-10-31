"""Keyframe-only scene scan, dedup, frame extraction and contact sheets."""
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .hw import find_bin
from .transcribe import fmt_ts

THUMB = 48  # px, grayscale thumbnail used only for change detection


def _font(size):
    for f in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _decode_thumbs(path, pre_input, vf_head):
    cmd = [find_bin("ffmpeg"), "-hide_banner", "-threads", "4", *pre_input, "-i", path, "-an", "-sn",
           "-vf", f"{vf_head}scale={THUMB}:{THUMB},format=gray,showinfo", "-fps_mode", "passthrough",
           "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=1800)
    times = [float(m) for m in re.findall(rb"pts_time:\s*([\d.]+)", r.stderr)]
    n = len(r.stdout) // (THUMB * THUMB)
    buf = np.frombuffer(r.stdout[: n * THUMB * THUMB], np.uint8).reshape(n, THUMB, THUMB).astype(np.int16)
    return list(zip(times[:n], buf))


def scan_keyframes(path):
    """Decode ONLY keyframes (-skip_frame nokey) at tiny size. Returns [(t, thumb)]. ~10-30x faster
    than decoding every frame."""
    return _decode_thumbs(path, ["-skip_frame", "nokey"], "")


def sample_frames(path, interval):
    """Decode one tiny frame every `interval` seconds. Slower than scan_keyframes (decodes everything)."""
    return _decode_thumbs(path, [], f"fps=1/{interval:.3f},")


def scene_cuts(path, start=0.0, end=None, threshold=0.2):
    """Hard cuts in [start, end] from ffmpeg's scene-change score, decoded at 160 px. Returns [t]."""
    span = ["-t", f"{end - start:.3f}"] if end else []
    cmd = [find_bin("ffmpeg"), "-hide_banner", "-ss", f"{start:.3f}", *span, "-i", path, "-an", "-sn",
           "-vf", f"scale=160:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=1800)
    cuts = []
    for m in re.findall(rb"pts_time:\s*([\d.]+)", r.stderr):
        t = round(start + float(m), 2)
        if not cuts or t - cuts[-1] >= 0.5:  # one cut can score high on two consecutive frames
            cuts.append(t)
    return cuts


def is_sparse(n_keyframes, duration, max_frames):
    """True when keyframes are too few to cover the video (long-GOP screen recordings: one keyframe
    every 10-30 s), so scene selection would miss content."""
    return n_keyframes < min(max_frames, (duration or 0) / 10)


def scan(path, duration, max_frames):
    """Keyframes, topped up with timed samples when the video has too few of them."""
    kf = scan_keyframes(path)
    if not is_sparse(len(kf), duration, max_frames):
        return kf
    interval = max(2.0, duration / 200)
    merged = {round(t, 2): f for t, f in sample_frames(path, interval)}
    merged.update({round(t, 2): f for t, f in kf})
    return sorted(merged.items())


def select(frames, duration, max_frames=40, noise=0.004, window=6, change_share=0.7):
    """Adaptive selection, relative to THIS video's amount of change (screencasts change ~0.3% per
    keyframe, action videos ~10%+):
      1. change frames: keep a keyframe if it differs from ALL of the last `window` kept ones
         (kills A-B-A repeats and static slides); the threshold is binary-searched so these use
         ~`change_share` of the budget.
      2. coverage frames: fill the largest time gaps with the keyframe nearest each gap's middle."""
    if not frames:
        return []
    duration = duration or frames[-1][0]

    def run(thr):
        kept = [0]
        for i in range(1, len(frames)):
            if min(np.abs(frames[i][1] - frames[k][1]).mean() / 255 for k in kept[-window:]) > thr:
                kept.append(i)
        return kept

    budget = max(1, int(max_frames * change_share))
    kept = run(noise)
    if len(kept) > budget:
        lo, hi = noise, 0.6
        for _ in range(14):
            mid = (lo + hi) / 2
            if len(run(mid)) > budget:
                lo = mid
            else:
                hi = mid
        kept = run(hi)
    kept = set(kept)
    times = [f[0] for f in frames]
    min_gap, blocked = duration / max_frames, set()
    while len(kept) < min(max_frames, len(frames)):
        ks = sorted(kept)
        edges = [times[k] for k in ks] + [duration]
        open_gaps = [j for j in range(len(ks)) if edges[j] not in blocked]
        if not open_gaps:
            break
        g = max(open_gaps, key=lambda j: edges[j + 1] - edges[j])
        if edges[g + 1] - edges[g] < 1.5 * min_gap:
            break
        mid = (edges[g] + edges[g + 1]) / 2
        cand = min((i for i in range(len(frames)) if i not in kept), key=lambda i: abs(times[i] - mid))
        if edges[g] < times[cand] < edges[g + 1]:
            kept.add(cand)
        else:
            blocked.add(edges[g])  # no keyframe inside this gap
    return [round(times[k], 2) for k in sorted(kept)]


def _label(img, t):
    """Timestamp in a black strip above the frame, so it never hides on-screen text."""
    f = _font(max(14, img.height // 22))
    txt = fmt_ts(t)
    _, _, _, y1 = ImageDraw.Draw(img).textbbox((0, 0), txt, font=f)
    out = Image.new("RGB", (img.width, img.height + y1 + 8), (0, 0, 0))
    out.paste(img, (0, y1 + 8))
    ImageDraw.Draw(out).text((5, 3), txt, fill=(255, 255, 0), font=f)
    return out


def detect_crop(path, duration):
    """Find black bars (e.g. landscape video re-uploaded as portrait) from 3 sample points.
    Returns an ffmpeg 'crop=w:h:x:y' or '' if bars are negligible."""
    boxes = []
    for frac in (0.2, 0.5, 0.8):
        r = subprocess.run([find_bin("ffmpeg"), "-hide_banner", "-ss", f"{duration * frac:.1f}", "-i", path,
                            "-vf", "cropdetect=limit=24:round=2:reset=0", "-frames:v", "15", "-an", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=120)
        m = re.findall(r"x1:(\d+) x2:(\d+) y1:(\d+) y2:(\d+)", r.stderr)
        w = re.findall(r"crop=(\d+):(\d+)", r.stderr)
        if m and w:
            boxes.append([int(v) for v in m[-1]])
    if not boxes:
        return ""
    x1, y1 = min(b[0] for b in boxes), min(b[2] for b in boxes)
    x2, y2 = max(b[1] for b in boxes), max(b[3] for b in boxes)
    pr = subprocess.run([find_bin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                         "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    W, H = (int(v) for v in pr.strip().split(",")[:2])
    w, h = (x2 - x1 + 1) // 2 * 2, (y2 - y1 + 1) // 2 * 2
    if w <= 0 or h <= 0 or w * h > 0.85 * W * H:  # <15% bars: not worth cropping
        return ""
    # relative, so it also applies to the hi-res stream of the same video
    return (f"crop='trunc(iw*{w / W:.4f}/2)*2':'trunc(ih*{h / H:.4f}/2)*2'"
            f":'iw*{x1 / W:.4f}':'ih*{y1 / H:.4f}'")


def extract(inp, times, out_dir, long_side=768, label=True, workers=3, crop=""):
    """Grab one frame per timestamp (parallel ffmpeg seeks). Returns [(t, path)]."""
    os.makedirs(out_dir, exist_ok=True)
    scale = f"scale='if(gt(iw,ih),{long_side},-2)':'if(gt(iw,ih),-2,{long_side})'"
    if crop:
        scale = f"{crop},{scale}"

    def one(t):
        p = os.path.join(out_dir, f"f_{t:09.2f}_{long_side}{'c' if crop else ''}{'s' if label else 'n'}.jpg")
        if not os.path.exists(p):
            subprocess.run([find_bin("ffmpeg"), "-v", "error", "-y", "-threads", "1", "-ss", f"{t:.3f}", "-i", inp,
                            "-frames:v", "1", "-vf", scale, "-q:v", "3", "-threads", "1", p], timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if label and os.path.exists(p):
                _label(Image.open(p).convert("RGB"), t).save(p, quality=88)
        return (t, p) if os.path.exists(p) else None
    with ThreadPoolExecutor(workers) as ex:
        return [r for r in ex.map(one, times) if r]


def contact_sheets(frames, out_dir, cell_long=384, sheet_w=1536, sheet_h=1152):
    """Tile labelled frames into grids: ~20 frames for the token cost of ~1.5 full frames."""
    if not frames:
        return []
    os.makedirs(out_dir, exist_ok=True)
    ims = []
    for t, p in frames:
        im = Image.open(p).convert("RGB")
        im.thumbnail((cell_long, cell_long))
        ims.append(im)
    cw, ch = max(i.width for i in ims), max(i.height for i in ims)
    cols, rows = max(1, sheet_w // cw), max(1, sheet_h // ch)
    per = cols * rows
    paths = []
    for s in range(0, len(ims), per):
        chunk = ims[s:s + per]
        r = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cw, r * ch), (24, 24, 24))
        for i, im in enumerate(chunk):
            sheet.paste(im, ((i % cols) * cw, (i // cols) * ch))
        p = os.path.join(out_dir, f"sheet_{s // per + 1:02d}.jpg")
        sheet.save(p, quality=85)
        paths.append(p)
    return paths


def keyframes(video, max_frames=40):
    """Cached scene-aware frame selection for a video. Returns [(t, path)] at 768px."""
    cache = os.path.join(video.dir, f"keyframes_{max_frames}.json")
    if os.path.exists(cache):
        return [tuple(x) for x in json.load(open(cache))]
    scan_path = video.scan_file()
    dur = video.meta().get("duration") or 0
    times = select(scan(scan_path, dur, max_frames), dur, max_frames=max_frames)
    out = extract(scan_path, times, os.path.join(video.dir, "frames"), crop=crop_for(video))
    json.dump(out, open(cache, "w"))
    return out


def crop_for(video):
    """Cached black-bar crop filter for a video ('' = none)."""
    p = os.path.join(video.dir, "crop.json")
    if not os.path.exists(p):
        json.dump({"crop": detect_crop(video.scan_file(), video.meta().get("duration") or 0)}, open(p, "w"))
    return json.load(open(p))["crop"]
