import json
from types import SimpleNamespace

import pytest

from video_mcp.core import _in_video, parse_ts, search_transcript
from video_mcp.source import is_url
from video_mcp.transcribe import as_text, fmt_ts


@pytest.mark.parametrize("raw,expected", [("90", 90), ("1:30", 90), ("1:02:05", 3725), (12.5, 12.5), (" 0:10 ", 10)])
def test_parse_ts(raw, expected):
    assert parse_ts(raw) == expected


@pytest.mark.parametrize("secs,expected", [(0, "00:00"), (65, "01:05"), (3725, "1:02:05")])
def test_fmt_ts(secs, expected):
    assert fmt_ts(secs) == expected


def test_is_url():
    assert is_url("https://youtu.be/abc")
    assert is_url("HTTP://example.com/v.mp4")
    assert not is_url(r"C:\videos\clip.mp4")


def test_as_text_merges_close_fragments_only():
    segs = [{"start": 0, "end": 1, "text": "hello"}, {"start": 1.2, "end": 2, "text": "world"},
            {"start": 10, "end": 11, "text": "later"}]
    assert as_text(segs) == "[00:00] hello world\n[00:10] later"


def test_in_video_keeps_seeks_inside_duration():
    v = SimpleNamespace(meta=lambda: {"duration": 22.0})
    assert _in_video(v, 22.0) == pytest.approx(21.9)
    assert _in_video(v, -3) == 0.0
    assert _in_video(v, 10) == 10
    assert _in_video(SimpleNamespace(meta=lambda: {}), 99) == 99


def _fake_video(monkeypatch, tmp_path, texts):
    segs = [{"start": i * 5, "end": i * 5 + 4, "text": t} for i, t in enumerate(texts)]
    monkeypatch.setattr("video_mcp.core.get_video", lambda src: SimpleNamespace(dir=str(tmp_path)))
    monkeypatch.setattr("video_mcp.core.transcribe", lambda v: {"segments": segs})


def test_search_transcript_matches_any_word(monkeypatch, tmp_path):
    _fake_video(monkeypatch, tmp_path, ["intro", "buy gold", "outro"])
    out = search_transcript("x", "GOLD silver")["text"]
    assert out.startswith("1 hits")
    assert "[00:05] buy gold" in out
    assert search_transcript("x", "nothing")["text"] == "no hits for 'nothing'"


def test_search_transcript_ranks_exact_phrase_first(monkeypatch, tmp_path):
    texts = ["stop here", "a", "b", "loss only", "c", "d", "set the stop loss now", "e", "f", "stop and loss"]
    _fake_video(monkeypatch, tmp_path, texts)
    out = search_transcript("x", "Stop  Loss", context=0)["text"]
    order = [out.index(t) for t in ["stop loss now", "stop and loss", "stop here", "loss only"]]
    assert order == sorted(order)


def test_search_transcript_includes_cached_ocr(monkeypatch, tmp_path):
    _fake_video(monkeypatch, tmp_path, ["intro"])
    (tmp_path / "ocr.json").write_text(json.dumps({"65.00": ["Error: disk full"], "3.00": ["Welcome"]}))
    out = search_transcript("x", "error")["text"]
    assert "no hits for 'error'" in out
    assert "## On screen (OCR keyframes)\n[01:05] Error: disk full" in out
