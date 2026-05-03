from __future__ import annotations

import numpy as np
from wildlife_ml.eval.metrics import intersection_over_union, precision_recall


def _box(x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    return np.asarray([x1, y1, x2, y2], dtype=np.int64)


def test_iou_identical_boxes_is_one() -> None:
    box = _box(0, 0, 10, 10)
    assert intersection_over_union(box, box) == 1.0


def test_iou_disjoint_boxes_is_zero() -> None:
    a = _box(0, 0, 10, 10)
    b = _box(20, 20, 30, 30)
    assert intersection_over_union(a, b) == 0.0


def test_iou_partial_overlap() -> None:
    a = _box(0, 0, 10, 10)         # area 100
    b = _box(5, 5, 15, 15)         # area 100, overlap 5x5 = 25
    iou = intersection_over_union(a, b)
    assert iou == 25 / (100 + 100 - 25)


def test_iou_zero_area_boxes_returns_zero() -> None:
    a = _box(5, 5, 5, 5)
    b = _box(5, 5, 5, 5)
    assert intersection_over_union(a, b) == 0.0


def test_iou_one_zero_area_box_returns_zero() -> None:
    a = _box(0, 0, 0, 0)
    b = _box(0, 0, 10, 10)
    assert intersection_over_union(a, b) == 0.0


def test_precision_recall_basic() -> None:
    p, r = precision_recall(true_positive=8, false_positive=2, false_negative=2)
    assert p == 0.8
    assert r == 0.8


def test_precision_recall_zero_denominators() -> None:
    p, r = precision_recall(true_positive=0, false_positive=0, false_negative=0)
    assert p == 0.0
    assert r == 0.0


def test_precision_recall_all_false_positives() -> None:
    p, r = precision_recall(true_positive=0, false_positive=5, false_negative=0)
    assert p == 0.0
    assert r == 0.0
