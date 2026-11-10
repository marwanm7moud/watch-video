import wave

import numpy as np
import pytest

from video_mcp.transcribe import _load_wav


def _write_wav(path, pcm, rate=16000, channels=1):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.asarray(pcm, np.int16).tobytes())


def test_load_wav_scales_pcm_like_faster_whisper(tmp_path):
    p = tmp_path / "a.wav"
    _write_wav(p, [0, 16384, -32768, 32767])
    audio = _load_wav(str(p))
    assert audio.dtype == np.float32
    assert audio.tolist() == [0.0, 0.5, -1.0, 32767 / 32768]


@pytest.mark.parametrize("rate,channels", [(44100, 1), (16000, 2)])
def test_load_wav_rejects_other_formats(tmp_path, rate, channels):
    p = tmp_path / "b.wav"
    _write_wav(p, [0, 0, 0, 0], rate=rate, channels=channels)
    with pytest.raises(ValueError):
        _load_wav(str(p))
