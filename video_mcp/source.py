"""Resolve a video input (local file or URL) into a cache entry with metadata."""
import hashlib
import json
import os
import re
import subprocess
import time

from .hw import find_bin

CACHE_ROOT = os.environ.get("VIDEO_MCP_CACHE", os.path.join(os.path.expanduser("~"), ".cache", "video_mcp"))


def is_url(s):
    return bool(re.match(r"^https?://", s.strip(), re.I))


def ffprobe(path):
    out = subprocess.run(
        [find_bin("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True).stdout
    return json.loads(out)


class Video:
    """One cached video. Everything derived from it lives under self.dir."""

    def __init__(self, src):
        src = src.strip().strip('"')
        self.src = src
        self.url = src if is_url(src) else None
        if self.url:
            self.info = self._yt_info()
            self.key = re.sub(r"[^\w-]", "_", f"{self.info.get('extractor_key', 'web')}_{self.info['id']}")
        else:
            path = os.path.abspath(src)
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            st = os.stat(path)
            self.key = hashlib.sha1(f"{path}|{st.st_size}|{st.st_mtime}".encode()).hexdigest()[:12]
            self.local_path = path
            self.info = None
        self.dir = os.path.join(CACHE_ROOT, self.key)
        os.makedirs(self.dir, exist_ok=True)

    # ---------- metadata ----------
    def _yt_info(self):
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as y:
            return y.sanitize_info(y.extract_info(self.url, download=False))

    def meta(self):
        p = os.path.join(self.dir, "meta.json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
        if self.url:
            i = self.info
            m = {"source": self.url, "title": i.get("title"), "channel": i.get("uploader"),
                 "duration": i.get("duration"), "upload_date": i.get("upload_date"),
                 "description": (i.get("description") or "")[:3000],
                 "chapters": [{"start": c["start_time"], "title": c["title"]} for c in (i.get("chapters") or [])],
                 "language": i.get("language")}
        else:
            pr = ffprobe(self.local_path)
            v = next((s for s in pr["streams"] if s["codec_type"] == "video"), {})
            m = {"source": self.local_path, "title": os.path.basename(self.local_path),
                 "duration": float(pr["format"].get("duration", 0)),
                 "width": v.get("width"), "height": v.get("height"),
                 "has_audio": any(s["codec_type"] == "audio" for s in pr["streams"]),
                 "chapters": [{"start": float(c["start_time"]), "title": c.get("tags", {}).get("title", "")}
                              for c in pr.get("chapters", [])]}
        json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return m

    # ---------- media access ----------
    def _ydl(self, fmt, outtmpl, extra=None):
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "format": fmt, "outtmpl": outtmpl,
                "concurrent_fragment_downloads": 8, "noprogress": True}
        opts.update(extra or {})
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(self.url, download=True)
            return y.prepare_filename(info)

    def scan_file(self):
        """Low-res video used for keyframe scanning (local file = itself)."""
        if not self.url:
            return self.local_path
        for f in os.listdir(self.dir):
            if f.startswith("scan."):
                return os.path.join(self.dir, f)
        return self._ydl("bv*[height<=480][ext=mp4]/bv*[height<=480]/b[height<=480]/wv*/w",
                         os.path.join(self.dir, "scan.%(ext)s"))

    def audio_file(self):
        """16 kHz mono wav for ASR."""
        wav = os.path.join(self.dir, "audio.wav")
        if os.path.exists(wav):
            return wav
        if self.url:
            src = None
            for f in os.listdir(self.dir):
                if f.startswith("audio_src."):
                    src = os.path.join(self.dir, f)
            src = src or self._ydl("ba/b", os.path.join(self.dir, "audio_src.%(ext)s"))
        else:
            src = self.local_path
        subprocess.run([find_bin("ffmpeg"), "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                        "-c:a", "pcm_s16le", wav], check=True, timeout=1800,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return wav

    def hires_input(self):
        """Input for full-quality single frames. For URLs: a direct stream URL ffmpeg can seek into,
        so we never download the whole high-res video."""
        if not self.url:
            return self.local_path
        p = os.path.join(self.dir, "stream.json")
        if os.path.exists(p):
            d = json.load(open(p))
            if time.time() - d["t"] < 3 * 3600:
                return d["url"]
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                               "format": "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b"}) as y:
            i = y.extract_info(self.url, download=False)
        u = i.get("url") or i["requested_formats"][0]["url"]
        json.dump({"t": time.time(), "url": u}, open(p, "w"))
        return u

    # ---------- platform subtitles ----------
    def platform_subs(self, langs=("en", "en-US", "en-GB")):
        """Return [{start,end,text}] from uploaded/auto captions, or None. Prefers human subs."""
        if not self.url:
            return None
        i = self.info
        orig = (i.get("language") or "").split("-")[0]
        manual, auto = i.get("subtitles") or {}, i.get("automatic_captions") or {}
        pick = None
        for pool, keys in ((manual, [*langs, orig]), (auto, ["en-orig", *langs, f"{orig}-orig", orig])):
            for k in keys:
                if k and k in pool:
                    pick = (pool[k], k)
                    break
            if pick:
                break
        if not pick:
            return None
        fmts, lang = pick
        j3 = next((f for f in fmts if f.get("ext") == "json3"), None)
        if not j3:
            return None
        import urllib.request
        data = json.loads(urllib.request.urlopen(j3["url"], timeout=30).read().decode("utf-8"))
        segs = []
        for ev in data.get("events", []):
            txt = "".join(s.get("utf8", "") for s in ev.get("segs") or []).replace("\n", " ").strip()
            if txt:
                st = ev["tStartMs"] / 1000
                segs.append({"start": st, "end": st + ev.get("dDurationMs", 0) / 1000, "text": txt})
        return {"segments": segs, "engine": f"platform-subs:{lang}", "language": lang.split("-")[0]} if segs else None
