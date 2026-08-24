import math
from pathlib import Path

import numpy as np
import soundfile as sf


def calculate_frame_rms(
    samples: np.ndarray,
    frame_size: int = 2048,
) -> np.ndarray:
    """Calculate RMS loudness for short audio frames."""
    mono = samples.mean(axis=1)

    frame_values = []

    for start in range(0, len(mono), frame_size):
        frame = mono[start:start + frame_size]

        if len(frame) == 0:
            continue

        rms = float(
            np.sqrt(np.mean(np.square(frame)))
        )

        frame_values.append(rms)

    return np.asarray(frame_values)


def quality_from_snr(
    snr_db: float,
    clipping_ratio: float,
) -> str:
    """Create a rough, explainable quality estimate."""
    if clipping_ratio > 0.02:
        return "clipped"

    if snr_db >= 20:
        return "good"

    if snr_db >= 10:
        return "fair"

    return "noisy"


def analyze_audio(file_path: Path) -> dict:
    """
    Extract technical audio properties.

    Loudness is measured as approximate dBFS.
    Noise quality is estimated from frame-level RMS values.
    """
    audio_info = sf.info(str(file_path))

    samples, sample_rate = sf.read(
        str(file_path),
        dtype="float32",
        always_2d=True,
    )

    if len(samples) == 0 or sample_rate <= 0:
        raise ValueError("The audio file contains no samples")

    duration_seconds = len(samples) / sample_rate

    file_size_bytes = file_path.stat().st_size

    bitrate_kbps = (
        file_size_bytes
        * 8
        / duration_seconds
        / 1000
    )

    overall_rms = float(
        np.sqrt(np.mean(np.square(samples)))
    )

    if overall_rms > 0:
        loudness_dbfs = 20 * math.log10(overall_rms)
    else:
        loudness_dbfs = -120.0

    frame_rms = calculate_frame_rms(samples)

    positive_frames = frame_rms[frame_rms > 0]

    if len(positive_frames) > 0:
        noise_rms = float(
            np.percentile(positive_frames, 20)
        )

        estimated_snr_db = 20 * math.log10(
            max(overall_rms, 1e-12)
            / max(noise_rms, 1e-12)
        )
    else:
        estimated_snr_db = 0.0

    clipping_ratio = float(
        np.mean(np.abs(samples) >= 0.99)
    )

    return {
        "duration_seconds": round(
            duration_seconds,
            3,
        ),
        "sample_rate_hz": int(sample_rate),
        "sample_rate_khz": round(
            sample_rate / 1000,
            1,
        ),
        "bitrate_kbps": round(
            bitrate_kbps,
            2,
        ),
        "loudness_dbfs": round(
            loudness_dbfs,
            2,
        ),
        "estimated_snr_db": round(
            estimated_snr_db,
            2,
        ),
        "quality_label": quality_from_snr(
            estimated_snr_db,
            clipping_ratio,
        ),
        "channels": int(audio_info.channels),
        "format": audio_info.format,
        "subtype": audio_info.subtype,
    }