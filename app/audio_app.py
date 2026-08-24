from pathlib import Path
from uuid import uuid4

import streamlit as st
from sqlalchemy import select

from src.audio.analyzer import analyze_audio
from src.database.connection import SessionLocal
from src.database.models import AudioSubmission
from src.ingestion.normalizers import (
    normalize_name,
    normalize_phone,
)
from src.matching.resolver import (
    create_person,
    find_person_by_phone,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIO_UPLOAD_DIR = PROJECT_ROOT / "uploads" / "audio"

AUDIO_UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


st.set_page_config(
    page_title="ConsultBae Audio Collection",
    page_icon="🎙️",
    layout="wide",
)


def save_audio_file(audio_file) -> tuple[Path, str]:
    """Save an uploaded or recorded audio file safely."""
    original_filename = getattr(
        audio_file,
        "name",
        "recording.wav",
    )

    suffix = Path(original_filename).suffix.lower()

    if not suffix:
        suffix = ".wav"

    stored_filename = f"{uuid4().hex}{suffix}"
    stored_path = AUDIO_UPLOAD_DIR / stored_filename

    stored_path.write_bytes(audio_file.getvalue())

    return stored_path, original_filename


def create_audio_submission(
    *,
    submitted_name: str,
    submitted_phone: str,
    audio_file,
) -> AudioSubmission:
    """Analyze audio and save its database record."""
    normalized_name = normalize_name(submitted_name)
    normalized_phone = normalize_phone(submitted_phone)

    if normalized_name is None:
        raise ValueError("Please enter a valid name")

    if normalized_phone is None:
        raise ValueError(
            "Please enter a valid 10-digit Indian phone number"
        )

    stored_path, original_filename = save_audio_file(
        audio_file
    )

    try:
        metadata = analyze_audio(stored_path)

        with SessionLocal() as session:
            person = find_person_by_phone(
                session,
                normalized_phone,
            )

            if person is None:
                person = create_person(
                    session,
                    full_name=normalized_name,
                    phone=normalized_phone,
                    source_name="audio_app",
                )

            relative_path = stored_path.relative_to(
                PROJECT_ROOT
            )

            submission = AudioSubmission(
                person_id=person.id,
                submitted_name=normalized_name,
                submitted_phone=normalized_phone,
                file_path=relative_path.as_posix(),
                original_filename=original_filename,
                duration_seconds=metadata[
                    "duration_seconds"
                ],
                sample_rate_hz=metadata[
                    "sample_rate_hz"
                ],
                bitrate_kbps=metadata[
                    "bitrate_kbps"
                ],
                loudness_dbfs=metadata[
                    "loudness_dbfs"
                ],
                estimated_snr_db=metadata[
                    "estimated_snr_db"
                ],
                quality_label=metadata[
                    "quality_label"
                ],
            )

            session.add(submission)
            session.commit()
            session.refresh(submission)

            return submission

    except Exception:
        stored_path.unlink(missing_ok=True)
        raise


def submission_page() -> None:
    st.title("🎙️ Audio Collection")
    st.write(
        "Enter your details, record or upload an audio "
        "sample, and submit it for analysis."
    )

    submitted_name = st.text_input(
        "Full name",
        placeholder="Enter your name",
    )

    submitted_phone = st.text_input(
        "Phone number",
        placeholder="10-digit Indian phone number",
    )

    st.subheader("Record audio")

    recorded_audio = st.audio_input(
        "Record a voice sample"
    )

    st.caption("Alternatively, upload an existing WAV file.")

    uploaded_audio = st.file_uploader(
        "Upload audio",
        type=["wav"],
    )

    selected_audio = recorded_audio or uploaded_audio

    if selected_audio is not None:
        st.audio(selected_audio)

    if st.button(
        "Submit audio",
        type="primary",
        use_container_width=True,
    ):
        if selected_audio is None:
            st.error(
                "Record or upload an audio file before submitting."
            )
            return

        try:
            with st.spinner(
                "Saving and analyzing your audio..."
            ):
                submission = create_audio_submission(
                    submitted_name=submitted_name,
                    submitted_phone=submitted_phone,
                    audio_file=selected_audio,
                )

            st.success(
                f"Submission #{submission.id} saved successfully."
            )

            column1, column2, column3, column4 = st.columns(4)

            column1.metric(
                "Duration",
                f"{submission.duration_seconds:.2f} sec",
            )

            column2.metric(
                "Sample rate",
                f"{submission.sample_rate_hz / 1000:.1f} kHz",
            )

            column3.metric(
                "Bitrate",
                f"{submission.bitrate_kbps:.1f} kbps",
            )

            column4.metric(
                "Loudness",
                f"{submission.loudness_dbfs:.1f} dBFS",
            )

            st.info(
                f"Estimated quality: "
                f"{submission.quality_label.title()}"
            )

        except ValueError as error:
            st.error(str(error))

        except Exception as error:
            st.error(
                f"Audio submission failed: {error}"
            )


def submissions_page() -> None:
    st.title("📋 Audio Submissions")

    with SessionLocal() as session:
        statement = (
            select(AudioSubmission)
            .order_by(AudioSubmission.created_at.desc())
        )

        submissions = list(
            session.scalars(statement).all()
        )

    if not submissions:
        st.info("No audio submissions have been received yet.")
        return

    st.write(f"Total submissions: {len(submissions)}")

    for submission in submissions:
        with st.container(border=True):
            heading, quality = st.columns([4, 1])

            heading.subheader(
                f"#{submission.id} — "
                f"{submission.submitted_name}"
            )

            quality.metric(
                "Quality",
                submission.quality_label.title(),
            )

            st.caption(
                f"Phone: {submission.submitted_phone} · "
                f"Submitted: {submission.created_at}"
            )

            absolute_path = (
                PROJECT_ROOT / submission.file_path
            )

            if absolute_path.exists():
                st.audio(str(absolute_path))
            else:
                st.warning("Stored audio file is missing.")

            column1, column2, column3, column4, column5 = (
                st.columns(5)
            )

            column1.metric(
                "Duration",
                f"{submission.duration_seconds:.2f}s",
            )

            column2.metric(
                "Sample rate",
                f"{submission.sample_rate_hz / 1000:.1f} kHz",
            )

            column3.metric(
                "Bitrate",
                f"{submission.bitrate_kbps:.1f} kbps",
            )

            column4.metric(
                "Loudness",
                f"{submission.loudness_dbfs:.1f} dBFS",
            )

            column5.metric(
                "Estimated SNR",
                (
                    f"{submission.estimated_snr_db:.1f} dB"
                    if submission.estimated_snr_db is not None
                    else "N/A"
                ),
            )


page = st.sidebar.radio(
    "Navigation",
    [
        "Submit Audio",
        "View Submissions",
    ],
)

if page == "Submit Audio":
    submission_page()
else:
    submissions_page()