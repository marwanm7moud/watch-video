"""video_mcp: let Claude "watch" videos via transcripts + smart keyframes."""
import os

__version__ = "0.1.0"

# HF's Xet transfer can stall model downloads on some networks; plain HTTPS is reliable.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

# AVX-512 int8 on all cores is the heaviest load a desktop CPU can run (big power/heat spikes,
# and it destabilised at least one machine), so CTranslate2 is held to AVX2 unless
# VIDEO_MCP_AVX512=1. Must be set before ctranslate2 is imported.
if os.environ.get("VIDEO_MCP_AVX512") != "1":
    os.environ.setdefault("CT2_FORCE_CPU_ISA", "AVX2")
