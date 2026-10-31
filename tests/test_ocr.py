import pytest
from PIL import Image, ImageDraw

from video_mcp import ocr


def test_new_lines_drops_repeats_and_empty_frames():
    per = [(0, ["Title", "intro"]), (5, ["Title", "intro"]), (10, ["Title", "step 1"]), (15, [])]
    assert ocr.new_lines(per) == [(0, ["Title", "intro"]), (10, ["step 1"])]


def test_format_ocr_truncates():
    out = ocr.format_ocr([(0, ["x" * 50]), (60, ["y" * 50])], limit=60)
    assert out.startswith("[00:00] ")
    assert "truncated" in out


@pytest.mark.skipif(not ocr.available(), reason="rapidocr not installed")
def test_reads_text_from_image(tmp_path):
    p = tmp_path / "s.png"
    im = Image.new("RGB", (900, 200), "white")
    ImageDraw.Draw(im).text((20, 40), "def hello(name):", fill="black")
    im.save(p)
    assert any("hello" in ln.replace(" ", "") for ln in ocr._read(str(p)))
