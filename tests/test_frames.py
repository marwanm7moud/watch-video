import subprocess

import numpy as np
import pytest
from PIL import Image

from video_mcp import frames as fr
from video_mcp.hw import find_bin


def test_label_adds_strip_without_covering_frame():
    img = Image.new("RGB", (640, 360), (255, 0, 0))
    out = fr._label(img, 65)
    assert out.width == 640 and out.height > 360
    assert out.getpixel((2, out.height - 360)) == (255, 0, 0)  # frame's top-left pixel untouched


def test_select_picks_changes_and_respects_budget():
    # 30 keyframes: three visually distinct "slides", each repeated 10 times
    thumbs = [np.full((fr.THUMB, fr.THUMB), v, np.int16) for v in (0, 120, 240) for _ in range(10)]
    frames = [(float(i * 10), t) for i, t in enumerate(thumbs)]
    picked = fr.select(frames, 300, max_frames=6)
    assert picked[0] == 0
    assert {0.0, 100.0, 200.0} <= set(picked)
    assert len(picked) <= 6


def test_select_empty():
    assert fr.select([], 10) == []


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    try:
        ffmpeg = find_bin("ffmpeg")
    except FileNotFoundError:
        pytest.skip("ffmpeg not installed")
    path = tmp_path_factory.mktemp("clip") / "clip.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=6",
                    "-g", "10", "-pix_fmt", "yuv420p", str(path)], check=True)
    return str(path)


def test_scan_extract_and_contact_sheet(clip, tmp_path):
    kf = fr.scan_keyframes(clip)
    assert len(kf) >= 5
    out = fr.extract(clip, [0, 2.5, 5], str(tmp_path / "f"), long_side=256)
    assert len(out) == 3
    assert max(Image.open(out[0][1]).size) == 256
    sheets = fr.contact_sheets(out, str(tmp_path / "s"))
    assert len(sheets) == 1


def test_scene_cuts_finds_hard_cuts(tmp_path):
    try:
        ffmpeg = find_bin("ffmpeg")
    except FileNotFoundError:
        pytest.skip("ffmpeg not installed")
    path = str(tmp_path / "cuts.mp4")
    # three 2 s solid-colour shots: hard cuts at 2 s and 4 s
    subprocess.run([ffmpeg, "-v", "error", "-y", *[a for c in ("red", "blue", "green") for a in
                    ("-f", "lavfi", "-i", f"color=c={c}:s=160x120:r=10:d=2")],
                    "-filter_complex", "concat=n=3:v=1:a=0", "-pix_fmt", "yuv420p", path], check=True)
    assert [round(t) for t in fr.scene_cuts(path)] == [2, 4]
    assert [round(t) for t in fr.scene_cuts(path, 3, 6)] == [4]


def test_is_sparse():
    assert fr.is_sparse(2, 600, 40)  # 10-min screencast with 2 keyframes
    assert not fr.is_sparse(3, 19, 8)  # short clip: few keyframes are fine
    assert not fr.is_sparse(60, 600, 40)


def test_sparse_keyframes_fall_back_to_timed_samples(tmp_path):
    try:
        ffmpeg = find_bin("ffmpeg")
    except FileNotFoundError:
        pytest.skip("ffmpeg not installed")
    path = str(tmp_path / "long_gop.mp4")
    # one keyframe for the whole 60 s clip, like a screen recording
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=5:duration=60",
                    "-g", "9999", "-keyint_min", "9999", "-sc_threshold", "0", "-pix_fmt", "yuv420p", path],
                   check=True)
    assert len(fr.scan_keyframes(path)) <= 2
    frames = fr.scan(path, 60, 40)
    assert len(frames) >= 20
    assert len(fr.select(frames, 60, max_frames=10)) >= 5
