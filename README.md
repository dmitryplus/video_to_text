# Скрипт создания конспекта видео встречи

Видео скачивается с Яндекс.Диска, YouTube или VK Video, вырезается аудио дорожка и прогоняется через модель для распознавания речи `ai-sage/GigaAM-v3`.


## Запуск из консоли
```bash
./.venv/bin/python main.py "https://disk.360.yandex.ru/i/*************"
```

## Требования

- Python 3.12 или совместимая версия Python 3.
- Установленные `ffmpeg` и `ffprobe`, доступные из консоли.
- Доступ в интернет для скачивания видеофайла с Яндекс.Диска, YouTube или VK Video и первой загрузки моделей.
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

С URL на видео с Яндекс.Диска:

```bash
HF_TOKEN=hf_... ./.venv/bin/python main.py "https://disk.360.yandex.ru/i/*************"
```

С YouTube-ссылкой:

```bash
HF_TOKEN=hf_... ./.venv/bin/python main.py "https://www.youtube.com/watch?v=neHSPe-P408"
```

С VK Video-ссылкой:

```bash
HF_TOKEN=hf_... ./.venv/bin/python main.py "https://vkvideo.ru/video-3156562_456249044"
```

С локальным аудиофайлом:

```bash
HF_TOKEN=hf_... ./.venv/bin/python main.py path/to/audio.mp3
```

Скрипт принимает только один аргумент: URL видео или путь к локальному аудиофайлу.
Если на вход подан URL с видео, скрипт скачивает исходный видеофайл, извлекает аудиодорожку и уже её использует как основную запись для распознавания.

Автоматически имя выходного файла строится как `<имя_источника>_transcript.txt`.

## Краткое описание работы скрипта

- При первом запуске модель будет скачана из Hugging Face.
- Для инференса в этом проекте используются `torch==2.8.0` и `torchaudio==2.8.0`.
- Любой входной файл проходит через единый silence-aware pipeline.
- URL на видео поддерживаются через `file_processing.py`: Яндекс.Диск скачивается через прямую ссылку, YouTube и VK Video скачиваются через `yt-dlp` как видеофайлы до 480p, дальше из них извлекается и обрабатывается аудиодорожка.
- Скачанное видео и извлечённый WAV сохраняются в `.cache/recordings`.
- Аудио режется по тишине, с ограничением минимальной и максимальной длины сегмента.
- Если подходящей тишины рядом нет, сегмент режется по безопасной длине.
- Результат всегда сохраняется автоматически в `<имя_источника>_transcript.txt`.
