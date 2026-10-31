"""MCP server exposing video tools to Claude."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:  # mcp >= 2 renamed FastMCP -> MCPServer
    from mcp.server.mcpserver import Image
    from mcp.server.mcpserver import MCPServer as FastMCP  # noqa: E402
except ImportError:
    from mcp.server.fastmcp import FastMCP, Image  # noqa: E402

from video_mcp import core, hw  # noqa: E402

hw.be_nice()

mcp = FastMCP("video")


def _out(r):
    return [r["text"]] + [Image(path=p) for p in r["images"]]


@mcp.tool()
def video_overview(source: str, max_frames: int = 40, engine: str = "auto", language: str | None = None,
                   ocr: bool = False):
    """START HERE for any video. `source` = local file path or URL (YouTube + 1500 sites).
    Returns metadata, chapters, full timestamped transcript and contact sheets of scene-selected
    keyframes (timestamp in each cell). engine: auto|subs|parakeet|whisper. language: 'en' (default),
    another ISO code, or 'auto' to detect. Parakeet (fast on CPU) covers 25 European languages; others
    (Arabic, Chinese, Japanese, Hindi...) use Whisper, which is heavy on CPU.
    Cached: repeat calls are instant. First run on CPU without subtitles can take a few minutes
    for long videos. ocr=True also returns the text visible on screen (code, slides, UI) as text; needs
    the watch-video-mcp[ocr] extra."""
    return _out(core.overview(source, max_frames, engine, language, ocr))


@mcp.tool()
def get_frames(source: str, timestamps: list[str], hi_res: bool = True):
    """Exact frames at timestamps ('12:30', '1:02:05' or seconds), max 20. hi_res=True gives 1280px,
    enough to read code/slides. For URLs this seeks into the stream without downloading the video."""
    return _out(core.get_frames(source, timestamps, hi_res))


@mcp.tool()
def scan_range(source: str, start: str, end: str, count: int = 12):
    """Evenly spaced frames between start and end as one contact sheet. Use to follow motion or a
    demo step by step."""
    return _out(core.scan_range(source, start, end, count))


@mcp.tool()
def get_transcript(source: str, start: str = "0", end: str | None = None):
    """Transcript slice between start and end."""
    return core.get_transcript(source, start, end)["text"]


@mcp.tool()
def search_transcript(source: str, query: str):
    """Find where words are spoken, best matches (exact phrase) first. Returns timestamped hits with context.
    Also lists matching on-screen text if video_overview ran with ocr=True."""
    return core.search_transcript(source, query)["text"]


@mcp.tool()
def check_hardware():
    """Show detected tools, GPU and the transcription profile in use."""
    return hw.report()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
