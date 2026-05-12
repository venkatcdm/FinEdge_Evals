# Invoice Evaluation System - Improvements Summary

## Problems Identified

### 1. **Threshold Sliders Had Minimal Impact**
**Root Cause:** Thresholds were only applied AFTER computing raw similarity scores using a simple penalty curve (`_apply_threshold_curve`). The raw fuzzy/numeric scores were computed independently of thresholds, so adjusting sliders barely changed results.

**Example of Old Behavior:**
- Invoice ID with 95% similarity: Score = 95 regardless of threshold
- Only if score < threshold, it got halved (e.g., 90 → 45)
- Most fields had high similarity, so thresholds barely mattered

### 2. **Basic Evaluation Logic**
- No field importance weighting (all fields treated equally)
- Simple numeric comparison without business tolerance
- Rigid date comparison (fixed day windows)
- No context-aware text matching
- Item matching didn't leverage thresholds

---

## Improvements Made

### ✅ 1. Threshold-Aware Numeric Scoring
**File:** `app/evaluator/comparator.py` - `_numeric_score_with_tolerance()`

**Before:** Fixed tolerance bands (0.01, 0.1 absolute differences)
**After:** Threshold directly controls tolerance percentage:

| Threshold | Tolerance | Example: $10,000 invoice |
|-----------|-----------|--------------------------|
| 100       | 0.01%     | ±$1                      |
| 95        | 0.25%     | ±$25                     |
| 90        | 0.5%      | ±$50                     |
| 85        | 1%        | ±$100                    |
| 80        | 2%        | ±$200                    |
| 75        | 5%        | ±$500                    |
| 70        | 10%       | ±$1,000                  |

**Impact:** Now adjusting amount threshold from 95→85 allows 4x more tolerance!

### ✅ 2. Threshold-Aware Date Scoring
**File:** `app/evaluator/comparator.py` - `_calendar_date_score_with_threshold()`

**Before:** Fixed tolerance (1 day = 95%, 3 days = 88%)
**After:** Threshold controls day window:

| Threshold | Tolerance Window | Penalty Beyond |
|-----------|------------------|----------------|
| 100       | Same day only    | -10 pts/day    |
| 95        | ±1 day          | -10 pts/day    |
| 90        | ±2 days         | -5 pts/day     |
| 85        | ±3 days         | -5 pts/day     |
| 80        | ±5 days         | -3 pts/day     |
| 75        | ±7 days         | -3 pts/day     |
| 70        | ±14 days        | -3 pts/day     |

**Impact:** Date threshold 95→80 changes tolerance from ±1 to ±5 days!

### ✅ 3. Threshold-Aware Text Matching
**File:** `app/evaluator/comparator.py` - `_text_score_with_threshold()`

**Before:** Applied threshold curve after scoring
**After:** Threshold controls matching strategy:

| Threshold | Strategy | Acceptance Criteria |
|-----------|----------|---------------------|
| 100       | Exact only | 100% match required |
| 95-99     | Very strict | 95%+ raw similarity |
| 85-94     | Strict | 85%+ raw similarity |
| 75-84     | Moderate | 75%+ raw similarity |
| <75       | Lenient | Accepts lower scores |

**Impact:** High thresholds now reject near-matches that previously scored high!

### ✅ 4. Field Importance Weighting
**File:** `app/main.py` - `_get_field_weight()`

**New Feature:** Critical fields now contribute more to overall score:

| Field Type | Weight | Examples |
|------------|--------|----------|
| Critical   | 1.5x   | invoice_id, total_amount, gross_amount |
| Important  | 1.3x   | net_amount, tax_amount, currency |
| Medium     | 1.2x   | date fields, description |
| Default    | 1.0x   | All other fields |

**Impact:** Getting invoice_id wrong now hurts 50% more than getting email wrong!

### ✅ 5. Enhanced Item Matching
**File:** `app/evaluator/matcher.py` - `item_similarity()`, `match_items()`

**Improvements:**
- Threshold-aware scoring for description, amounts, quantity
- Priority-based matching (items with unique descriptions matched first)
- Better weighted composite scoring
- Tolerance bands controlled by thresholds

**Before:**
```python
score = desc_score * 0.4 + net_score * 0.25 + ...
```

**After:**
```python
# Each component uses threshold-controlled tolerance
desc_score = _apply_item_threshold(raw_score, desc_threshold)
net_score = _numeric_similarity_with_threshold(ext, gt, amount_threshold)
# Then weighted combination
```

### ✅ 6. Improved Threshold Penalty Curve
**File:** `app/evaluator/comparator.py` - `_apply_threshold_curve()`

**Before:** Simple 50% penalty for scores below threshold
**After:** Progressive penalty based on distance from threshold:

| Distance from Threshold | Penalty |
|-------------------------|---------|
| At or above threshold   | Boost toward 100 |
| Within 5 points below   | 15% penalty (×0.85) |
| 5-15 points below       | 35% penalty (×0.65) |
| 15-30 points below      | 60% penalty (×0.40) |
| 30+ points below        | 80% penalty (×0.20) |

### ✅ 7. Interactive Threshold Impact Analysis
**File:** `frontend/streamlit_app.py`

**New UI Features:**
1. **Help Section:** Explains how thresholds affect each field type
2. **Sensitivity Analysis:** Shows comparison of:
   - Current settings
   - Stricter (+10 threshold)
   - More lenient (-10 threshold)
3. **Visual Deltas:** Green/red indicators show score changes

---

## How Thresholds Now Work

### Example 1: Numeric Field (gross_amount)

**Scenario:** Extracted = $9,400, Ground Truth = $9,450 (0.53% difference)

| Threshold | Tolerance | Score | Reason |
|-----------|-----------|-------|--------|
| 100       | 0.01% (±$0.94) | 89.6 | Way beyond tolerance, steep penalty |
| 95        | 0.25% (±$23.5) | 94.4 | Beyond tolerance, moderate penalty |
| 90        | 0.5% (±$47)    | 99.6 | Just beyond tolerance, slight penalty |
| 85        | 1% (±$94)      | 100.0 | Within tolerance, perfect score |
| 80        | 2% (±$188)     | 100.0 | Within tolerance, perfect score |

**Result:** Changing threshold from 85→95 drops score from 100→94.4!

### Example 2: Date Field (invoice_date)

**Scenario:** Extracted = 2024-04-29, Ground Truth = 2024-05-02 (3 days apart)

| Threshold | Window | Score | Reason |
|-----------|--------|-------|--------|
| 100       | 0 days | 70.0 | 3 days beyond, -10 pts/day |
| 95        | ±1 day | 80.0 | 2 days beyond, -10 pts/day |
| 90        | ±2 days| 90.0 | 1 day beyond, -5 pts/day |
| 85        | ±3 days| 100.0 | Within tolerance |
| 80        | ±5 days| 100.0 | Within tolerance |

**Result:** Threshold choice dramatically affects score!

### Example 3: Text Field (merchant.name)

**Scenario:** Extracted = "Manpower Staffing", Ground Truth = "Manpower Staffing Ltda"

| Threshold | Strategy | Raw Score | Final Score |
|-----------|----------|-----------|-------------|
| 100       | Exact only | 85% | 0.0 (not exact) |
| 95        | Very strict | 85% | 34.0 (penalized) |
| 90        | Strict | 85% | 72.25 (penalized) |
| 80        | Moderate | 85% | 80.75 (accepted) |
| 70        | Lenient | 85% | 80.75 (accepted) |

---

## Testing the Improvements

### Run Field-Level Tests
```bash
python test_field_scoring.py
```
Shows how individual fields score with different thresholds.

### Run Impact Analysis
```bash
python test_threshold_impact.py
```
Compares default, strict, and lenient threshold configurations.

### Test in UI
```bash
streamlit run frontend/streamlit_app.py
```
Upload your JSON files and see the "Threshold Impact Analysis" section.

---

## Key Benefits

1. **Meaningful Threshold Control:** Sliders now have significant, predictable impact
2. **Business-Logic Alignment:** Tolerance bands match real-world invoice validation needs
3. **Fair Weighting:** Critical fields matter more in overall scoring
4. **Transparent Scoring:** Users can see exactly how thresholds affect results
5. **Granular Control:** Each threshold value maps to specific tolerance levels

---

## Files Modified

1. `app/evaluator/comparator.py` - Core scoring logic (204 lines added/modified)
2. `app/evaluator/matcher.py` - Item matching with thresholds (123 lines added/modified)
3. `app/main.py` - Field weighting system (49 lines added)
4. `frontend/streamlit_app.py` - UI improvements & sensitivity analysis (99 lines added)

---

## Backward Compatibility

All changes are backward compatible:
- Existing eval configs work without modification
- Default thresholds unchanged
- Can optionally add `field_weights` to eval configs for custom weighting
- Threshold sliders work with any schema (global, germany, uk)
