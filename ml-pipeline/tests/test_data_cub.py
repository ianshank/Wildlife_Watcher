from __future__ import annotations

from pathlib import Path

import pytest
from wildlife_ml.data.cub import load_samples


@pytest.fixture
def metadata_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "meta.csv"
    csv_path.write_text(
        "image_path,label,bbox_x,bbox_y,bbox_w,bbox_h,species\n"
        "img/1.jpg,0,10,20,30,40,bird-a\n"
        "img/2.jpg,1,1,2,3,4,bird-b\n"
        "img/3.jpg,2,5,6,7,8,bird-c\n",
        encoding="utf-8",
    )
    return csv_path


def test_load_samples_returns_all_rows(metadata_csv: Path) -> None:
    rows = load_samples(metadata_csv)
    assert len(rows) == 3
    first = rows[0]
    assert first["image_path"] == Path("img/1.jpg")
    assert first["label"] == 0
    assert first["bbox"] == (10, 20, 30, 40)


def test_load_samples_filters_by_species(metadata_csv: Path) -> None:
    rows = load_samples(metadata_csv, allowed_species=["bird-a", "bird-c"])
    assert [row["label"] for row in rows] == [0, 2]


def test_load_samples_empty_allowed_set(metadata_csv: Path) -> None:
    rows = load_samples(metadata_csv, allowed_species=[])
    assert rows == []


def test_load_samples_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_samples(tmp_path / "missing.csv")
