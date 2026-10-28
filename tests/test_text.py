import pytest

from video_mcp.core import parse_ts, search_transcript
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


def test_search_transcript_matches_any_word(monkeypatch):
    segs = [{"start": i * 5, "end": i * 5 + 4, "text": t} for i, t in enumerate(["intro", "buy gold", "outro"])]
    monkeypatch.setattr("video_mcp.core.get_video", lambda src: None)
    monkeypatch.setattr("video_mcp.core.transcribe", lambda v: {"segments": segs})
    out = search_transcript("x", "GOLD silver")["text"]
    assert out.startswith("1 hits")
    assert "[00:05] buy gold" in out
    assert search_transcript("x", "nothing")["text"] == "no hits for 'nothing'"
