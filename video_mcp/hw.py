"""Hardware + tool checker. Picks the fastest transcription setup for this machine."""
import functools
import glob
import os
import shutil
import subprocess


@functools.lru_cache(None)
def find_bin(name):
    """Locate ffmpeg/ffprobe/yt-dlp even when PATH wasn't refreshed after install."""
    p = shutil.which(name)
    if p:
        return p
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [os.path.join(local, "Microsoft", "WinGet", "Links", name + ".exe")]
    candidates += glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "*", "*", "bin", name + ".exe"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    if name == "yt-dlp":
        return None  # fall back to the python module
    raise FileNotFoundError(f"{name} not found. Install it (winget install Gyan.FFmpeg).")


@functools.lru_cache(None)
def cuda_devices():
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count()
    except Exception:
        return 0


@functools.lru_cache(None)
def ocr_available():
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


@functools.lru_cache(None)
def parakeet_available():
    try:
        import onnx_asr  # noqa: F401
        return True
    except Exception:
        return False


def free_ram_gb():
    if os.name == "nt":
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        m = MS()
        m.len = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.avail / 2**30
    try:
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30
    except (ValueError, OSError, AttributeError):
        return 8.0


def be_nice():
    """Run this process (and the ffmpeg children it spawns, which inherit it) below normal priority,
    so a long transcription never freezes the desktop."""
    try:
        if os.name == "nt":
            import ctypes
            BELOW_NORMAL = 0x4000
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW_NORMAL)
        else:
            os.nice(10)
    except Exception:
        pass


@functools.lru_cache(None)
def profile():
    """Return the transcription profile for this machine."""
    gpu = cuda_devices() > 0
    cpus = os.cpu_count() or 4
    if gpu:
        return {
            "device": "cuda", "compute_type": "float16", "cpu_threads": 0,
            "whisper_model": "large-v3-turbo", "beam_size": 5, "batch_size": 16,
            "parakeet": False,  # turbo on GPU is already fast and handles many languages
        }
    ram = free_ram_gb()
    return {
        # 4 threads by default: 6 vs 10 threads measured the same speed, and lower sustained load
        # keeps the machine responsive. Override with VIDEO_MCP_THREADS.
        "device": "cpu", "compute_type": "int8",
        "cpu_threads": int(os.environ.get("VIDEO_MCP_THREADS", max(1, min(4, cpus // 2)))),
        "whisper_model": "large-v3-turbo" if ram >= 4 else "small", "beam_size": 1,
        "batch_size": 4 if ram >= 8 else 1,
        "parakeet": parakeet_available(),  # ~23x realtime for English on a mid-range desktop CPU
    }


def report():
    def ver(b):
        try:
            path = find_bin(b)
            if not path:
                return "python module"
            out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10).stdout
            return out.splitlines()[0][:60] if out else path
        except Exception as e:
            return f"MISSING ({e})"
    p = profile()
    lines = [
        f"CPU threads: {os.cpu_count()}",
        f"CUDA GPUs: {cuda_devices()}",
        f"Free RAM: {free_ram_gb():.1f} GB",
        f"CPU ISA for Whisper: {os.environ.get('CT2_FORCE_CPU_ISA', 'auto (AVX-512 if available)')}",
        f"ffmpeg: {ver('ffmpeg')}",
        f"ffprobe: {ver('ffprobe')}",
        f"Parakeet (onnx-asr): {'yes' if parakeet_available() else 'no'}",
        f"OCR (rapidocr): {'yes' if ocr_available() else 'no (pip install watch-video[ocr])'}",
        f"Profile: {p}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
