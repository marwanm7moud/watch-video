"""CLI for testing and for use without MCP:
  video-cli overview <src> [--max-frames N] [--engine E] [--language L]
  video-cli frames <src> 12:30 13:05 [--low]
  video-cli range <src> 10:00 10:30 [--count 12]
  video-cli transcript <src> [start] [end]
  video-cli search <src> <query>
  video-cli hw
(also runnable as `python -m video_mcp.cli ...`)
"""
import argparse
import sys

from . import __version__, core, hw


def build_parser():
    ap = argparse.ArgumentParser(prog="video-cli", description="Let an AI watch a video from the shell.")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("overview", help="metadata, transcript and contact sheets")
    o.add_argument("src")
    o.add_argument("--max-frames", type=int, default=40)
    o.add_argument("--engine", default="auto", help="auto|subs|parakeet|whisper")
    o.add_argument("--language")

    f = sub.add_parser("frames", help="exact frames at timestamps")
    f.add_argument("src")
    f.add_argument("ts", nargs="+")
    f.add_argument("--low", action="store_true", help="768px instead of 1280px")

    r = sub.add_parser("range", help="evenly spaced frames between two timestamps")
    r.add_argument("src")
    r.add_argument("start")
    r.add_argument("end")
    r.add_argument("--count", type=int, default=12)

    t = sub.add_parser("transcript", help="transcript slice")
    t.add_argument("src")
    t.add_argument("start", nargs="?", default="0")
    t.add_argument("end", nargs="?")

    s = sub.add_parser("search", help="find where words are spoken")
    s.add_argument("src")
    s.add_argument("query")

    sub.add_parser("hw", help="show detected tools, GPU and transcription profile")
    return ap


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    hw.be_nice()
    a = build_parser().parse_args(argv)
    if a.cmd == "hw":
        print(hw.report())
        return
    res = {"overview": lambda: core.overview(a.src, a.max_frames, a.engine, a.language),
           "frames": lambda: core.get_frames(a.src, a.ts, not a.low),
           "range": lambda: core.scan_range(a.src, a.start, a.end, a.count),
           "transcript": lambda: core.get_transcript(a.src, a.start, a.end),
           "search": lambda: core.search_transcript(a.src, a.query)}[a.cmd]()
    print(res["text"])
    for p in res["images"]:
        print("IMAGE:", p)


if __name__ == "__main__":
    main()
