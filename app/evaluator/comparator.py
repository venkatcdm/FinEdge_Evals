import re

from rapidfuzz import fuzz

from app.utils.normalization import invoice_digits_core
from app.utils.normalization import normalize_currency_code
from app.utils.normalization import normalize_number
from app.utils.normalization import normalize_text
from app.utils.normalization import parse_calendar_date


def _resolve_threshold(field_name: str, thresholds: dict) -> int:
    if field_name in thresholds:
        return int(thresholds[field_name])
    short = field_name.split(".")[-1]
    if short in thresholds:
        return int(thresholds[short])
    return int(thresholds.get("default", 85))


def _use_token_blend(field_name: str) -> bool:
    n = field_name.lower()
    return any(
        k in n
        for k in (
            "description",
            "name",
            "address",
            "city",
            "email",
            "business_unit",
            "payment_terms",
            "invoice_category",
            "invoice_type",
            "invoice_language",
            "translated_text",
            "fiscal_regime",
            "multi_invoice",
        )
    )


def _is_currency_field(field_name: str) -> bool:
    return field_name.lower().split(".")[-1] == "currency"


def _is_calendar_date_field(field_name: str) -> bool:
    tail = field_name.lower().split(".")[-1]
    if "date" not in tail:
        return False
    if any(x in tail for x in ("update", "timestamp", "timezone", "time_zone")):
        return False
    return True


def _numeric_score_with_tolerance(ext_num: float, gt_num: float, threshold: int) -> float:
    """
    Numeric comparison where threshold controls tolerance band.
    Higher threshold = stricter matching required (tighter tolerance).
    Lower threshold = more tolerance allowed.
    
    This function now makes thresholds MUCH more impactful by:
    1. Mapping threshold directly to tolerance percentage
    2. Applying exponential decay beyond tolerance
    3. Even small differences get penalized with high thresholds
    """
    if ext_num == gt_num:
        return 100.0
    
    diff = abs(ext_num - gt_num)
    max_val = max(abs(ext_num), abs(gt_num), 1.0)
    rel_diff = diff / max_val  # Relative difference (e.g., 0.01 = 1%)
    
    # Map threshold to tolerance percentage (WIDER RANGE for more impact)
    # Lower thresholds = MUCH more tolerant (liberal matching)
    # Higher thresholds = very strict (conservative matching)
    # 
    # threshold 100 -> 0.1% tolerance (almost exact)
    # threshold 95 -> 0.5% tolerance
    # threshold 90 -> 1% tolerance
    # threshold 85 -> 2% tolerance
    # threshold 80 -> 5% tolerance
    # threshold 75 -> 10% tolerance
    # threshold 70 -> 20% tolerance (very liberal)
    # threshold 60 -> 30% tolerance (extremely liberal)
    if threshold >= 100:
        tolerance_pct = 0.001   # 0.1%
    elif threshold >= 98:
        tolerance_pct = 0.002   # 0.2%
    elif threshold >= 95:
        tolerance_pct = 0.005   # 0.5%
    elif threshold >= 90:
        tolerance_pct = 0.01    # 1%
    elif threshold >= 85:
        tolerance_pct = 0.02    # 2%
    elif threshold >= 80:
        tolerance_pct = 0.05    # 5%
    elif threshold >= 75:
        tolerance_pct = 0.10    # 10%
    elif threshold >= 70:
        tolerance_pct = 0.20    # 20%
    elif threshold >= 60:
        tolerance_pct = 0.30    # 30%
    else:
        tolerance_pct = 0.50    # 50% (extremely liberal)
    
    tolerance = max_val * tolerance_pct
    
    # Within tolerance: perfect score
    if diff <= tolerance:
        return 100.0
    
    # Beyond tolerance: score decreases based on distance
    # Make lenient thresholds MUCH more forgiving
    excess_ratio = (diff - tolerance) / max_val
    
    # Penalize based on how far beyond tolerance
    # The penalty scales with threshold strictness
    if threshold >= 95:
        # Very strict: harsh penalty for any deviation
        score = 100.0 * max(0.0, 1.0 - excess_ratio * 10)
    elif threshold >= 90:
        # Strict: moderate penalty
        score = 100.0 * max(0.0, 1.0 - excess_ratio * 6)
    elif threshold >= 80:
        # Medium: gentler penalty
        score = 100.0 * max(0.0, 1.0 - excess_ratio * 4)
    elif threshold >= 70:
        # Lenient: very forgiving
        score = 100.0 * max(0.0, 1.0 - excess_ratio * 2)
    else:
        # Extremely lenient: almost no penalty
        score = 100.0 * max(0.0, 1.0 - excess_ratio * 1)
    
    return max(0.0, min(100.0, score))


def _calendar_date_score_with_threshold(ext_str: str, gt_str: str, threshold: int):
    """
    Date comparison where threshold controls day tolerance window.
    Higher threshold = fewer days tolerance (stricter).
    Lower threshold = more days tolerance (lenient).
    """
    d0 = parse_calendar_date(ext_str)
    d1 = parse_calendar_date(gt_str)
    
    if d0 is None and d1 is None:
        return None
    if d0 is None or d1 is None:
        return 0.0
    if d0 == d1:
        return 100.0
    
    days = abs((d0 - d1).days)
    
    # Map threshold to day tolerance (WIDER RANGE for more impact)
    if threshold >= 100:
        max_tolerance_days = 0  # Exact match only
    elif threshold >= 95:
        max_tolerance_days = 1  # ±1 day
    elif threshold >= 90:
        max_tolerance_days = 3  # ±3 days
    elif threshold >= 85:
        max_tolerance_days = 5  # ±5 days
    elif threshold >= 80:
        max_tolerance_days = 7  # ±1 week
    elif threshold >= 75:
        max_tolerance_days = 14  # ±2 weeks
    elif threshold >= 70:
        max_tolerance_days = 30  # ±1 month
    else:
        max_tolerance_days = 60  # ±2 months (very liberal)
    
    if days <= max_tolerance_days:
        return 100.0
    
    # Beyond tolerance: linear decay with more forgiving penalties for low thresholds
    excess_days = days - max_tolerance_days
    
    if threshold >= 95:
        # Strict: -10 points per day beyond tolerance
        score = 100.0 - min(excess_days * 10.0, 100.0)
    elif threshold >= 85:
        # Medium: -5 points per day
        score = 100.0 - min(excess_days * 5.0, 100.0)
    elif threshold >= 75:
        # Lenient: -2 points per day
        score = 100.0 - min(excess_days * 2.0, 100.0)
    else:
        # Very lenient: -1 point per day (almost no penalty)
        score = 100.0 - min(excess_days * 1.0, 100.0)
    
    return max(0.0, score)


def _text_score_with_threshold(ext_str: str, gt_str: str, field_name: str, threshold: int) -> float:
    """
    Text comparison where threshold controls matching strategy.
    Higher threshold = requires exact/near-exact match.
    Lower threshold = allows fuzzy/partial matches.
    """
    ext_norm = normalize_text(ext_str)
    gt_norm = normalize_text(gt_str)
    
    if ext_norm == gt_norm:
        return 100.0
    
    # Threshold 100: exact match only
    if threshold >= 100:
        return 0.0
    
    # Calculate multiple similarity scores
    if _use_token_blend(field_name):
        token_score = float(fuzz.token_sort_ratio(ext_norm, gt_norm))
        partial_score = float(fuzz.partial_ratio(ext_norm, gt_norm))
        ratio_score = float(fuzz.ratio(ext_norm, gt_norm))
        
        # Short strings: use best of token/partial
        if len(ext_norm) < 20 or len(gt_norm) < 20:
            raw_score = max(token_score, partial_score)
        else:
            # Longer strings: weighted blend
            raw_score = token_score * 0.7 + partial_score * 0.3
    else:
        ratio_score = float(fuzz.ratio(ext_norm, gt_norm))
        token_score = float(fuzz.token_sort_ratio(ext_norm, gt_norm))
        
        # For non-text fields, use conservative scoring
        raw_score = min(ratio_score, token_score)
    
    # Apply threshold-based scaling (MORE LIBERAL for low thresholds)
    # High threshold (90-100): only accept high raw scores
    # Medium threshold (75-90): moderate acceptance
    # Low threshold (60-75): very lenient, accepts lower scores
    if threshold >= 95:
        # Very strict: require 95%+ raw similarity
        if raw_score >= 95:
            return raw_score
        elif raw_score >= 85:
            return raw_score * 0.8
        else:
            return raw_score * 0.5
    elif threshold >= 85:
        # Strict: require 85%+ raw similarity
        if raw_score >= 90:
            return raw_score
        elif raw_score >= 80:
            return raw_score * 0.9
        else:
            return raw_score * 0.65
    elif threshold >= 75:
        # Moderate: accept 70%+ raw similarity
        if raw_score >= 80:
            return raw_score
        elif raw_score >= 65:
            return raw_score * 0.95
        else:
            return raw_score * 0.75
    elif threshold >= 65:
        # Lenient: accept 60%+ raw similarity
        if raw_score >= 75:
            return raw_score
        else:
            return raw_score * 0.85
    else:
        # Very lenient: almost no penalty
        return raw_score * 0.95


def _currency_field_score(ext_str: str, gt_str: str):
    c0 = normalize_currency_code(ext_str)
    c1 = normalize_currency_code(gt_str)
    if not c0 and not c1:
        return None
    if not c0 or not c1:
        return 0.0
    if c0 == c1:
        return 100.0
    return float(fuzz.ratio(c0, c1))


def _invoice_id_field_score(ext_str: str, gt_str: str) -> float:
    d_e = invoice_digits_core(ext_str)
    d_g = invoice_digits_core(gt_str)

    if len(d_e) >= 8 and len(d_g) >= 8:
        if d_e == d_g:
            return 100.0
        if d_e in d_g or d_g in d_e:
            shorter = min(len(d_e), len(d_g))
            longer = max(len(d_e), len(d_g))
            if longer > 0 and shorter / longer >= 0.92:
                return 96.0

    folded_e = re.sub(r"[^a-z0-9]+", "", ext_str.casefold())
    folded_g = re.sub(r"[^a-z0-9]+", "", gt_str.casefold())
    if folded_e and folded_g and folded_e == folded_g:
        return 100.0

    if not folded_e or not folded_g:
        return 0.0

    token = float(fuzz.token_sort_ratio(folded_e, folded_g))
    partial = float(fuzz.partial_ratio(folded_e, folded_g))
    ratio = float(fuzz.ratio(folded_e, folded_g))
    return max(token * 0.88, partial * 0.9, ratio * 0.82)


def _apply_threshold_curve(score: float, threshold: int) -> float:
    """
    Apply threshold as a dynamic scaling curve.
    - Scores >= threshold: scale up toward 100
    - Scores near threshold (±5): linear interpolation
    - Scores < threshold: progressive penalty based on distance
    """
    if score >= threshold:
        # Boost scores that meet threshold toward 100
        overshoot = score - threshold
        max_overshoot = 100.0 - threshold
        if max_overshoot > 0:
            boost_factor = 0.3 * (overshoot / max_overshoot)
            return min(100.0, score + (100.0 - score) * boost_factor)
        return score
    
    # Scores below threshold get penalized proportionally
    gap = threshold - score
    if gap <= 5:
        # Within 5 points: gentle penalty
        return score * 0.85
    elif gap <= 15:
        # 5-15 points below: moderate penalty
        return score * 0.65
    elif gap <= 30:
        # 15-30 points below: strong penalty
        return score * 0.40
    else:
        # More than 30 points below: severe penalty
        return score * 0.20


def compare_field(ext, gt, field_name, thresholds):
    """
    Compare extracted vs ground truth values with advanced logic.
    
    Thresholds now actively control:
    1. Tolerance bands for numeric fields
    2. Strictness of text matching
    3. Date comparison windows
    4. Penalty curves for mismatches
    """

    if ext is None and gt is None:
        return 100.0

    ext_str = "" if ext is None else str(ext).strip()
    gt_str = "" if gt is None else str(gt).strip()

    if not ext_str and not gt_str:
        return 100.0

    if not ext_str or not gt_str:
        return 0.0

    # Get threshold for this field (controls tolerance & strictness)
    threshold = _resolve_threshold(field_name, thresholds)
    
    # Numeric fields: threshold controls tolerance band
    ext_num = normalize_number(ext_str)
    gt_num = normalize_number(gt_str)

    if ext_num is not None and gt_num is not None:
        return _numeric_score_with_tolerance(ext_num, gt_num, threshold)

    fn = field_name.lower()

    # Calendar date fields: threshold controls day tolerance window
    if _is_calendar_date_field(field_name):
        ds = _calendar_date_score_with_threshold(ext_str, gt_str, threshold)
        if ds is not None:
            return ds

    # Currency fields: strict matching with threshold control
    if _is_currency_field(field_name):
        cs = _currency_field_score(ext_str, gt_str)
        if cs is not None:
            return _apply_threshold_curve(cs, threshold)

    # Invoice ID: special handling with digit extraction
    if "invoice_id" in fn and "electronic_uid" not in fn:
        score = _invoice_id_field_score(ext_str, gt_str)
        return _apply_threshold_curve(score, threshold)

    # Text fields: threshold controls matching strictness
    return _text_score_with_threshold(ext_str, gt_str, field_name, threshold)
