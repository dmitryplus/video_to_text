# Скрипт создания конспекта видео встречи

Видео скачивается с Яндекс.Диска, вырезается аудио дорожка и прогоняется через модель для распознавания речи `ai-sage/GigaAM-v3`.


## Запуск из консоли
```bash
./.venv/bin/python main.py "https://disk.360.yandex.ru/i/*************"
```

## Требования

- Python 3.12 или совместимая версия Python 3.
- Установленные `ffmpeg` и `ffprobe`, доступные из консоли.
- Доступ в интернет для скачивания видеофайла и первой загрузки моделей.
- `HF_TOKEN` с доступом к Hugging Face и принятой лицензией для `pyannote/segmentation-3.0`.
- Python-зависимости из `requirements.txt`.
- `torch==2.8.0` и `torchaudio==2.8.0`; для CPU-запуска они ставятся отдельно из официального индекса PyTorch.

## Подготовка окружения

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install 'torch==2.8.0' 'torchaudio==2.8.0' --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Для CPU-запуска используется официальный индекс PyTorch без CUDA-зависимостей.
Эта конфигурация выровнена под рекомендации model card `ai-sage/GigaAM-v3` и проверена в этом проекте.

## Запуск

Для запуска нужен `HF_TOKEN` с доступом к Hugging Face и принятой лицензией для:

- `pyannote/segmentation-3.0`

Пример запуска через переменную окружения:

```bash
HF_TOKEN=hf_... python main.py
```

Локальный запуск напрямую из созданного virtualenv, без `source .venv/bin/activate`:

```bash
HF_TOKEN=hf_... ./.venv/bin/python main.py record.mp3 --output record_transcript.txt
```

По умолчанию будет использован `record.mp3`, результат сохранится в `record_transcript.txt`,
а исходный медиафайл и извлечённый WAV будут кэшироваться в `.cache/recordings`.

Базовый запуск:

```bash
python main.py
```

С указанием собственного файла:

```bash
python main.py path/to/audio.mp3
```

С URL на видеозапись встречи:

```bash
./.venv/bin/python main.py "https://disk.360.yandex.ru/i/*************"
```

```bash
HF_TOKEN=hf_... ./.venv/bin/python main.py "https://disk.360.yandex.ru/i/*************"
```

Если на вход подан URL с видео, скрипт скачивает исходный файл, извлекает аудиодорожку и уже её использует как основную запись для распознавания.

С явным именем выходного файла:

```bash
python main.py record.mp3 --output record_transcript.txt
```

Автоматически имя выходного файла строится как `<имя_источника>_transcript.txt`.

Без сохранения скачанного видео и извлечённого аудио в кэш:

```bash
python main.py "https://disk.360.yandex.ru/i/************" \
  --no-keep-source-media \
  --no-keep-extracted-audio
```

С выбором ревизии модели:

```bash
python main.py record.mp3 --revision e2e_rnnt
```

С настройкой параметров обработки:

```bash
python main.py record.mp3 --chunk-seconds 20 --chunk-overlap-seconds 2
```

С настройкой нарезки по тишине:

```bash
python main.py record.mp3 \
  --chunk-seconds 20 \
  --min-chunk-seconds 10 \
  --max-chunk-seconds 24 \
  --chunk-overlap-seconds 2 \
  --silence-duration-seconds 0.35 \
  --silence-noise-level -35dB
```

Поддерживаемые ревизии GigaAM v3:

- `ssl`
- `ctc`
- `rnnt`
- `e2e_ctc`
- `e2e_rnnt`

## Краткое описание работы скрипта

- При первом запуске модель будет скачана из Hugging Face.
- Для инференса в этом проекте используются `torch==2.8.0` и `torchaudio==2.8.0`.
- Любой входной файл проходит через единый silence-aware pipeline.
- URL на видео поддерживаются через `file_processing.py`: файл скачивается, из него извлекается аудио, и дальше уже обрабатывается именно аудиодорожка.
- По умолчанию скачанное видео и извлечённый WAV сохраняются в `.cache/recordings`.
- При необходимости это можно отключить через `--no-keep-source-media` и `--no-keep-extracted-audio`.
- Аудио режется по тишине, с ограничением минимальной и максимальной длины сегмента.
- Если подходящей тишины рядом нет, сегмент режется по безопасной длине.
- Скрипт добавляет overlap между соседними сегментами и потом пытается убрать повторы на уровне слов и простых предложений.
- Если `--output` не указан, результат все равно сохраняется автоматически в `<имя_источника>_transcript.txt`.
