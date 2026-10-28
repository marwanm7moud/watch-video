import subprocess

import numpy as np
import pytest
from PIL import Image

from video_mcp import frames as fr
from video_mcp.hw import find_bin


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
