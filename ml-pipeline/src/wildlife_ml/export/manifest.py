from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wildlife_ml.export.onnx import OnnxExportConfig


@dataclass(frozen=True)
class ExportManifest:
    """Links an exported ONNX model to the class labels and kiosk-compatible metadata."""

    model_path: Path
    class_names: tuple[str, ...]
    image_size: tuple[int, int]
    opset: int

    def __post_init__(self) -> None:
        if not self.class_names:
            raise ValueError("class_names must not be empty")

    @classmethod
    def from_config(
        cls,
        model_path: Path,
        class_names: tuple[str, ...],
        config: OnnxExportConfig | None = None,
    ) -> ExportManifest:
        """Create a manifest from an *OnnxExportConfig*, filling in defaults when
        *config* is *None*."""
        resolved = config or OnnxExportConfig()
        return cls(
            model_path=model_path,
            class_names=class_names,
            image_size=resolved.image_size,
            opset=resolved.opset,
        )

    def to_summary(self) -> str:
        """Return a human-readable one-line summary suitable for logs."""
        h, w = self.image_size
        names = ", ".join(self.class_names)
        return (
            f"model={self.model_path} "
            f"classes=[{names}] "
            f"image_size={h}x{w} "
            f"opset={self.opset}"
        )
