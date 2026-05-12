from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

from app.utils.normalization import normalize_number
from app.utils.normalization import normalize_text


def _parse_tax_rate(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def numeric_similarity(a, b):

    a = normalize_number(a)
    b = normalize_number(b)

    if a is None and b is None:
        return 100.0

    if a is None or b is None:
        return 0.0

    if abs(a - b) <= 0.01:
        return 100.0

    if abs(a - b) <= 0.1:
        return 95.0

    diff = abs(a - b)
    max_val = max(abs(a), abs(b))

    return max(0.0, (1 - min(diff / max_val, 1)) * 100)


def quantity_similarity(a, b):
    a = normalize_number(a)
    b = normalize_number(b)

    if a is None and b is None:
        return 100.0

    if a is None or b is None:
        return 0.0

    if abs(a - b) <= 0.01:
        return 100.0

    if abs(a - b) <= 0.5:
        return 80.0

    return max(0.0, 100.0 - min(abs(a - b) * 20.0, 100.0))


def item_similarity(ext_item, gt_item, weights, thresholds=None):
    """
    Enhanced item similarity with threshold-aware scoring.
    Uses weighted composite of description, amounts, and quantity.
    Thresholds control tolerance for each field type.
    """
    from app.evaluator.comparator import compare_field
    
    if thresholds is None:
        thresholds = {}
    
    # Extract thresholds for item fields
    desc_threshold = thresholds.get("description", 75)
    amount_threshold = thresholds.get("amount", 90)
    qty_threshold = thresholds.get("quantity", 85)
    
    # Description score (text-based)
    desc_score = float(
        fuzz.token_sort_ratio(
            normalize_text(ext_item.get("description", "")),
            normalize_text(gt_item.get("description", "")),
        )
    )
    # Apply threshold curve
    desc_score = _apply_item_threshold(desc_score, desc_threshold)

    # Amount scores (numeric-based)
    net_score = _numeric_similarity_with_threshold(
        ext_item.get("net_amount"),
        gt_item.get("net_amount"),
        amount_threshold,
    )

    gross_score = _numeric_similarity_with_threshold(
        ext_item.get("gross_amount"),
        gt_item.get("gross_amount"),
        amount_threshold,
    )

    # Quantity score
    qty_score = _numeric_similarity_with_threshold(
        ext_item.get("quantity"),
        gt_item.get("quantity"),
        qty_threshold,
    )

    # Weighted combination
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0
    
    return (
        desc_score * weights.get("description", 0.4)
        + net_score * weights.get("net_amount", 0.25)
        + gross_score * weights.get("gross_amount", 0.25)
        + qty_score * weights.get("quantity", 0.1)
    ) / total_weight


def _apply_item_threshold(score: float, threshold: int) -> float:
    """Apply threshold-based scaling for item field matching."""
    if score >= threshold:
        return min(100.0, score)
    
    gap = threshold - score
    if gap <= 5:
        return score * 0.9
    elif gap <= 15:
        return score * 0.7
    else:
        return score * 0.4


def _numeric_similarity_with_threshold(a, b, threshold: int) -> float:
    """Numeric similarity with threshold-controlled tolerance."""
    a = normalize_number(a)
    b = normalize_number(b)

    if a is None and b is None:
        return 100.0

    if a is None or b is None:
        return 0.0
    
    if a == b:
        return 100.0

    diff = abs(a - b)
    max_val = max(abs(a), abs(b), 1.0)
    rel_diff = diff / max_val
    
    # Map threshold to tolerance
    if threshold >= 99:
        tolerance = 0.001
    elif threshold >= 95:
        tolerance = 0.005
    elif threshold >= 90:
        tolerance = 0.01
    elif threshold >= 85:
        tolerance = 0.02
    elif threshold >= 80:
        tolerance = 0.05
    else:
        tolerance = 0.10
    
    if rel_diff <= tolerance:
        return 100.0
    
    # Beyond tolerance: exponential decay
    excess = (rel_diff - tolerance) / max(tolerance, 0.01)
    return max(0.0, 100.0 * (1.0 - min(excess * 0.5, 1.0)))


def match_items(ext_items, gt_items, weights, thresholds=None, min_score: float = 50.0):
    """
    Enhanced item matching with threshold-aware similarity.
    Uses greedy bipartite matching with better score calculation.
    """
    matches: List[Dict[str, Any]] = []
    used = set()

    # Sort GT items by specificity (items with more unique descriptions first)
    gt_priorities = []
    for idx, item in enumerate(gt_items):
        desc = str(item.get("description", "")).strip()
        # Prioritize items with longer descriptions (more specific)
        priority = len(desc)
        gt_priorities.append((priority, idx))
    
    # Sort by priority (descending)
    gt_priorities.sort(reverse=True)

    for _, gt_index in gt_priorities:
        gt_item = gt_items[gt_index]

        best_score = 0.0
        best_match = None

        for ext_index, ext_item in enumerate(ext_items):

            if ext_index in used:
                continue

            score = item_similarity(
                ext_item,
                gt_item,
                weights,
                thresholds,
            )

            if score > best_score:
                best_score = score
                best_match = ext_index

        if best_match is not None and best_score >= min_score:
            used.add(best_match)
        else:
            best_match = None

        matches.append(
            {
                "gt_index": gt_index,
                "ext_index": best_match,
                "score": best_score,
            }
        )

    # Re-sort matches by original GT index for consistent output
    matches.sort(key=lambda m: m["gt_index"])
    return matches


def _rate_match_score(gt_rate: Optional[float], ext_rate: Optional[float]) -> float:
    if gt_rate is not None and ext_rate is not None:
        if abs(gt_rate - ext_rate) <= 0.01:
            return 100.0
        if abs(gt_rate - ext_rate) <= 0.5:
            return 80.0
        diff = abs(gt_rate - ext_rate)
        max_val = max(abs(gt_rate), abs(ext_rate))
        if max_val > 0:
            return max(0.0, (1 - min(diff / max_val, 1)) * 100)
        return 0.0
    return 0.0


def match_tax_rows(ext_items, gt_items, rate_field: str, min_score: float = 50.0):

    matches: List[Dict[str, Any]] = []
    used = set()

    for gt_index, gt_item in enumerate(gt_items):
        gt_rate = _parse_tax_rate(gt_item.get(rate_field))

        best_score = 0.0
        best_match = None

        for ext_index, ext_item in enumerate(ext_items):
            if ext_index in used:
                continue

            ext_rate = _parse_tax_rate(ext_item.get(rate_field))
            score = _rate_match_score(gt_rate, ext_rate)

            if score > best_score:
                best_score = score
                best_match = ext_index

        if best_match is not None and best_score >= min_score:
            used.add(best_match)
        else:
            best_match = None

        matches.append(
            {
                "gt_index": gt_index,
                "ext_index": best_match,
                "score": best_score,
            }
        )

    return matches
