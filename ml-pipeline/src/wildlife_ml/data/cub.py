from __future__ import annotations

import csv
from collections.abc import Collection
from pathlib import Path
from typing import TypedDict


class Sample(TypedDict):
    image_path: Path
    label: int
    bbox: tuple[int, int, int, int]


def load_samples(
    metadata_csv: Path,
    allowed_species: Collection[str] | None = None,
) -> list[Sample]:
    rows: list[Sample] = []
    allowed = set(allowed_species) if allowed_species is not None else None
    with metadata_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            species = raw["species"]
            if allowed is not None and species not in allowed:
                continue
            rows.append(
                {
                    "image_path": Path(raw["image_path"]),
                    "label": int(raw["label"]),
                    "bbox": (
                        int(raw["bbox_x"]),
                        int(raw["bbox_y"]),
                        int(raw["bbox_w"]),
                        int(raw["bbox_h"]),
                    ),
                }
            )
    return rows
