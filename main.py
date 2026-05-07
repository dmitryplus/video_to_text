from __future__ import annotations

import argparse
from pathlib import Path
import sys

from audio_processing import (
    AudioProcessingConfig,
    AudioProcessor,
    DEFAULT_CHUNK_OVERLAP_SECONDS,
    DEFAULT_CHUNK_SECONDS,
    DEFAULT_MAX_CHUNK_SECONDS,
    DEFAULT_MIN_CHUNK_SECONDS,
    DEFAULT_SILENCE_DURATION_SECONDS,
    DEFAULT_SILENCE_NOISE_LEVEL,
)
from file_processing import DEFAULT_CACHE_DIR, FileProcessor
from model_runner import GigaAMModelRunner


DEFAULT_MODEL = "ai-sage/GigaAM-v3"
DEFAULT_REVISION = "e2e_rnnt"
DEFAULT_OUTPUT_SUFFIX = "_transcript.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Распознать аудиофайл через GigaAM v3 и Hugging Face Transformers."
    )
    parser.add_argument(
        "audio_path",
        nargs="?",
        default="record.mp3",
        help="Путь или URL исходной записи. По умолчанию: record.mp3.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Идентификатор модели Hugging Face. По умолчанию: {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--revision",
        default=DEFAULT_REVISION,
        help=(
            "Ревизия модели. Для GigaAM-v3: ssl, ctc, rnnt, "
            "e2e_ctc, e2e_rnnt."
        ),
    )
    parser.add_argument(
        "--output",
        help=(
            "Необязательный путь для сохранения расшифровки в текстовый файл. "
            "Если не указан, имя файла будет создано автоматически."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help="Каталог для кэша скачанных медиафайлов и извлеченного аудио.",
    )
    parser.add_argument(
        "--keep-source-media",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Сохранять скачанный или исходный медиафайл в каталоге кэша. Включено по умолчанию.",
    )
    parser.add_argument(
        "--keep-extracted-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Сохранять извлеченный WAV-файл в каталоге кэша. Включено по умолчанию.",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=DEFAULT_CHUNK_SECONDS,
        help="Целевая длина аудио-чанка. По умолчанию: 20 секунд.",
    )
    parser.add_argument(
        "--chunk-overlap-seconds",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP_SECONDS,
        help="Перекрытие между чанками. По умолчанию: 2 секунды.",
    )
    parser.add_argument(
        "--min-chunk-seconds",
        type=int,
        default=DEFAULT_MIN_CHUNK_SECONDS,
        help="Минимальная длина сегмента при разбиении по тишине. По умолчанию: 10 секунд.",
    )
    parser.add_argument(
        "--max-chunk-seconds",
        type=int,
        default=DEFAULT_MAX_CHUNK_SECONDS,
        help="Максимальная длина сегмента при разбиении по тишине. По умолчанию: 30 секунд.",
    )
    parser.add_argument(
        "--silence-duration-seconds",
        type=float,
        default=DEFAULT_SILENCE_DURATION_SECONDS,
        help="Минимальная длительность тишины для ffmpeg silencedetect. По умолчанию: 0.35.",
    )
    parser.add_argument(
        "--silence-noise-level",
        default=DEFAULT_SILENCE_NOISE_LEVEL,
        help="Порог шума для ffmpeg silencedetect. По умолчанию: -35dB.",
    )
    return parser.parse_args()


def build_output_path(
    requested_output: str | None,
    input_ref: str,
    recording_source_path: Path | None,
) -> Path:
    if requested_output:
        return Path(requested_output).expanduser()

    if recording_source_path is not None:
        return Path.cwd() / f"{recording_source_path.stem}{DEFAULT_OUTPUT_SUFFIX}"

    input_path = Path(input_ref).expanduser()
    return Path.cwd() / f"{input_path.stem}{DEFAULT_OUTPUT_SUFFIX}"


def main() -> None:
    args = parse_args()
    audio_processor = AudioProcessor(
        AudioProcessingConfig(
            chunk_seconds=args.chunk_seconds,
            overlap_seconds=args.chunk_overlap_seconds,
            min_chunk_seconds=args.min_chunk_seconds,
            max_chunk_seconds=args.max_chunk_seconds,
            silence_duration_seconds=args.silence_duration_seconds,
            silence_noise_level=args.silence_noise_level,
        )
    )
    runner = GigaAMModelRunner(args.model, args.revision)
    file_processor = FileProcessor(
        cache_dir=args.cache_dir,
        keep_source_media=args.keep_source_media,
        keep_extracted_audio=args.keep_extracted_audio,
    )

    with file_processor.prepare(args.audio_path) as recording:
        transcription = audio_processor.transcribe_long_audio(
            runner.model,
            recording.audio_path,
        )
        output_path = build_output_path(
            args.output,
            args.audio_path,
            recording.source_path,
        )

    output_path.write_text(transcription + "\n", encoding="utf-8")
    print(f"Результат сохранен в: {output_path}", file=sys.stderr)
    print(transcription)


if __name__ == "__main__":
    main()
