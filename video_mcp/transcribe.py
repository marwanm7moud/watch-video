"""Transcription: platform subs > Parakeet (English, CPU) > faster-whisper large-v3-turbo."""
import json
import os
import time

from .hw import profile

_models = {}


def fmt_ts(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def _whisper():
    p = profile()
    if "whisper" not in _models:
        from faster_whisper import BatchedInferencePipeline, WhisperModel
        m = WhisperModel(p["whisper_model"], device=p["device"], compute_type=p["compute_type"],
                         cpu_threads=p["cpu_threads"])
        _models["whisper"] = (m, BatchedInferencePipeline(model=m))
    return _models["whisper"]


def _detect_language(wav):
    model, _ = _whisper()
    from faster_whisper.audio import decode_audio
    audio = decode_audio(wav, sampling_rate=16000)
    lang, prob, _ = model.detect_language(audio, vad_filter=True, language_detection_segments=4)
    return lang, prob


def _run_whisper(wav, language, prompt):
    p = profile()
    _, batched = _whisper()
    segs, info = batched.transcribe(
        wav, language=language, beam_size=p["beam_size"], batch_size=p["batch_size"],
        vad_filter=True, initial_prompt=prompt or None, condition_on_previous_text=False)
    out = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs
           if s.text.strip() and not _hallucination(s)]
    return out, info.language


# Whisper invents these on music/silence (classic English + Arabic subtitle-credit hallucinations).
_HALLUCINATIONS = {"thank you.", "thank you", "thanks for watching!", "thanks for watching.", "you",
                   "شكرا", "شكرا.", "شكرا لكم", "شكراً", "اشتركوا في القناة", "ترجمة نانسي قنقر",
                   "شكرا على المشاهدة", "موسيقى", "[موسيقى]", "[music]"}


def _hallucination(s):
    t = s.text.strip().lower()
    if s.no_speech_prob > 0.6 and s.avg_logprob < -0.8:
        return True
    return t in _HALLUCINATIONS and (s.no_speech_prob > 0.2 or s.avg_logprob < -0.5)


def _run_parakeet(wav):
    import onnx_asr
    if "parakeet" not in _models:
        vad = onnx_asr.load_vad("silero")
        # batch_size=1: batching pads segments to the longest one; on CPU that was 1.7x slower
        # (benchmark on an i5-11400, 300s clip: int8 bs1 13.0s, bs8 21.6s; fp32 bs1 18.4s)
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = profile()["cpu_threads"] or 4
        so.inter_op_num_threads = 1
        _models["parakeet"] = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", quantization="int8",
                                                  sess_options=so).with_vad(
            vad, batch_size=1, max_speech_duration_s=20)
    return [{"start": r.start, "end": r.end, "text": r.text.strip()}
            for r in _models["parakeet"].recognize(wav) if r.text.strip()]


def transcribe(video, engine="auto", language=None):
    """Returns {"segments":[...], "engine":..., "language":..., "seconds":...}. Cached per video+engine."""
    language = language or os.environ.get("VIDEO_MCP_LANG", "en")
    cache = os.path.join(video.dir, f"transcript_{engine}_{language}.json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    t0 = time.time()
    res = None
    if engine in ("auto", "subs"):
        res = video.platform_subs()
    if not res:
        meta = video.meta()
        if meta.get("has_audio") is False:
            res = {"segments": [], "engine": "none (no audio track)", "language": None}
        else:
            wav = video.audio_file()
            prompt = " ".join(filter(None, [meta.get("title"), (meta.get("description") or "")[:300]]))
            # English is assumed (no Whisper load just to detect); pass language="auto" to detect.
            lang, prob = _detect_language(wav) if language == "auto" else (language, 1.0)
            use_parakeet = engine == "parakeet" or (
                engine == "auto" and profile()["parakeet"] and lang == "en" and prob > 0.8)
            if use_parakeet:
                # No silent Whisper fallback on CPU: it is far heavier and can freeze a desktop.
                res = {"segments": _run_parakeet(wav), "engine": "parakeet-tdt-0.6b-v3", "language": lang}
            if not res:
                segs, lang = _run_whisper(wav, lang, prompt)
                p = profile()
                res = {"segments": segs, "engine": f"faster-whisper {p['whisper_model']} ({p['device']})",
                       "language": lang}
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return res


def as_text(segments, merge_gap=1.0, max_len=20.0):
    """Compact '[mm:ss] text' lines; merges tiny caption fragments to save tokens."""
    lines, cur = [], None
    for s in segments:
        if cur and s["start"] - cur["end"] <= merge_gap and s["end"] - cur["start"] <= max_len:
            cur["text"] += " " + s["text"]
            cur["end"] = s["end"]
        else:
            if cur:
                lines.append(cur)
            cur = dict(s)
    if cur:
        lines.append(cur)
    return "\n".join(f"[{fmt_ts(ln['start'])}] {ln['text']}" for ln in lines)
