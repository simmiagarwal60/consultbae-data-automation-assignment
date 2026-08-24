import numpy as np
import soundfile as sf

from src.audio.analyzer import analyze_audio


def test_analyze_wav_audio(tmp_path):
    sample_rate = 16_000
    duration = 1.0

    time_values = np.linspace(
        0,
        duration,
        int(sample_rate * duration),
        endpoint=False,
    )

    tone = 0.5 * np.sin(
        2 * np.pi * 440 * time_values
    )

    audio_path = tmp_path / "test_tone.wav"

    sf.write(
        audio_path,
        tone,
        sample_rate,
        subtype="PCM_16",
    )

    result = analyze_audio(audio_path)

    assert 0.99 <= result["duration_seconds"] <= 1.01
    assert result["sample_rate_hz"] == 16_000
    assert result["sample_rate_khz"] == 16.0
    assert result["bitrate_kbps"] > 0
    assert result["loudness_dbfs"] < 0
    assert result["quality_label"] in {
        "good",
        "fair",
        "noisy",
        "clipped",
    }