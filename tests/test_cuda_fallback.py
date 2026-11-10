import pytest

from video_mcp import hw
from video_mcp import transcribe as tr

CUBLAS = "Library cublas64_12.dll is not found or cannot be loaded"


class FakeVideo:
    def __init__(self, d):
        self.dir = str(d)

    def platform_subs(self):
        return None

    def meta(self):
        return {"title": "clip"}

    def audio_file(self):
        return "audio.wav"


@pytest.fixture
def gpu_machine(monkeypatch):
    """ctranslate2 reports a GPU; whether its CUDA libraries load is up to each test."""
    monkeypatch.setattr(hw, "cuda_devices", lambda: 1)
    monkeypatch.setattr(hw, "parakeet_available", lambda: True)
    monkeypatch.setattr(hw, "_cuda_error", None)
    monkeypatch.setattr(tr, "_models", {})
    hw.profile.cache_clear()
    yield
    hw.profile.cache_clear()


def test_missing_cublas_moves_auto_english_to_parakeet(gpu_machine, monkeypatch, tmp_path):
    def whisper(wav, language, prompt):
        assert hw.profile()["device"] == "cuda"
        raise RuntimeError(CUBLAS)
    monkeypatch.setattr(tr, "_run_whisper", whisper)
    monkeypatch.setattr(tr, "_run_parakeet", lambda wav: [{"start": 0, "end": 1, "text": "hi"}])
    res = tr.transcribe(FakeVideo(tmp_path), "auto", "en")
    assert res["engine"] == "parakeet-tdt-0.6b-v3"
    assert hw.profile()["device"] == "cpu"
    assert hw._cuda_error == CUBLAS


def test_missing_cublas_retries_whisper_on_cpu(gpu_machine, monkeypatch, tmp_path):
    devices = []

    def whisper(wav, language, prompt):
        devices.append(hw.profile()["device"])
        if devices[-1] == "cuda":
            raise RuntimeError(CUBLAS)
        return [{"start": 0, "end": 1, "text": "merhaba"}], language
    monkeypatch.setattr(tr, "_run_whisper", whisper)
    res = tr.transcribe(FakeVideo(tmp_path), "whisper", "tr")
    assert devices == ["cuda", "cpu"]
    assert res["engine"].endswith("(cpu)")
    assert res["segments"][0]["text"] == "merhaba"


def test_other_runtime_errors_are_raised(gpu_machine, monkeypatch, tmp_path):
    def whisper(wav, language, prompt):
        raise RuntimeError("CUDA failed with error out of memory")
    monkeypatch.setattr(tr, "_run_whisper", whisper)
    with pytest.raises(RuntimeError, match="out of memory"):
        tr.transcribe(FakeVideo(tmp_path), "whisper", "en")
    assert hw.profile()["device"] == "cuda"
