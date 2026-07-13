from __future__ import annotations

import argparse
from pathlib import Path
import sys

from audio_processing import AudioProcessingConfig, AudioProcessor
from file_processing import DEFAULT_CACHE_DIR, FileProcessor
from model_runner import GigaAMModelRunner


DEFAULT_MODEL = "ai-sage/GigaAM-v3"
DEFAULT_REVISION = "e2e_rnnt"
DEFAULT_OUTPUT_SUFFIX = "_transcript.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Распознать видео по URL или локальный аудиофайл через GigaAM v3."
    )
    parser.add_argument(
        "input_ref",
        help="URL видео или путь к локальному аудиофайлу.",
    )
    return parser.parse_args()


def build_output_path(input_ref: str, recording_source_path: Path | None) -> Path:
    if recording_source_path is not None:
        return Path.cwd() / f"{recording_source_path.stem}{DEFAULT_OUTPUT_SUFFIX}"

    input_path = Path(input_ref).expanduser()
    return Path.cwd() / f"{input_path.stem}{DEFAULT_OUTPUT_SUFFIX}"


def main() -> None:
    args = parse_args()
    audio_processor = AudioProcessor(AudioProcessingConfig())
    runner = GigaAMModelRunner(DEFAULT_MODEL, DEFAULT_REVISION)
    file_processor = FileProcessor(
        cache_dir=DEFAULT_CACHE_DIR,
        keep_source_media=True,
        keep_extracted_audio=True,
    )

    with file_processor.prepare(args.input_ref) as recording:
        transcription = audio_processor.transcribe_long_audio(
            runner.model,
            recording.audio_path,
        )
        output_path = build_output_path(args.input_ref, recording.source_path)

    output_path.write_text(transcription + "\n", encoding="utf-8")
    print(f"Результат сохранен в: {output_path}", file=sys.stderr)
    print(transcription)


if __name__ == "__main__":
    main()
