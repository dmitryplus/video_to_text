from __future__ import annotations

class GigaAMModelRunner:
    def __init__(self, model_name: str, revision: str):
        self.model_name = model_name
        self.revision = revision
        self.model = self._load_model()

    def _load_model(self):
        try:
            import torch
            from pyannote.audio.core.task import (
                Problem,
                Resolution,
                Scope,
                Specifications,
                Subset,
                Task,
            )
            from transformers import AutoModel
        except ImportError as exc:
            raise SystemExit(
                "Не удалось импортировать transformers. "
                "Установите зависимости: pip install -r requirements.txt"
            ) from exc

        # Доверенные checkpoint-файлы pyannote требуют этот класс, когда torch.load
        # по умолчанию использует weights_only=True в новых версиях PyTorch.
        torch.serialization.add_safe_globals(
            [
                torch.torch_version.TorchVersion,
                Specifications,
                Problem,
                Resolution,
                Scope,
                Subset,
                Task,
            ]
        )

        try:
            return AutoModel.from_pretrained(
                self.model_name,
                revision=self.revision,
                trust_remote_code=True,
            )
        except ImportError as exc:
            missing_name = getattr(exc, "name", None)
            if missing_name:
                raise SystemExit(
                    "Не хватает зависимости для загрузки модели: "
                    f"{missing_name}. Обновите окружение по README.md."
                ) from exc
            raise SystemExit(
                "Не удалось загрузить модель из-за отсутствующей Python-зависимости. "
                "Обновите окружение по README.md."
            ) from exc
