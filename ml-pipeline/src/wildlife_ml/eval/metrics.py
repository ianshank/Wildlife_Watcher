from __future__ import annotations

from wildlife_ml.types import Float32Tensor, Int64Tensor


def intersection_over_union(box_a: Int64Tensor, box_b: Int64Tensor) -> float:
    ax1, ay1, ax2, ay2 = [int(value) for value in box_a.tolist()]
    bx1, by1, bx2, by2 = [int(value) for value in box_b.tolist()]

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union_area = area_a + area_b - inter_area
    if union_area == 0:
        return 0.0
    return inter_area / union_area


def precision_recall(
    true_positive: int,
    false_positive: int,
    false_negative: int,
) -> tuple[float, float]:
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = 0.0 if precision_denominator == 0 else true_positive / precision_denominator
    recall = 0.0 if recall_denominator == 0 else true_positive / recall_denominator
    return precision, recall


__all__ = ["Float32Tensor", "intersection_over_union", "precision_recall"]
