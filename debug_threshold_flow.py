"""
Debug: Check if thresholds are actually being used in evaluation
"""
import json
from app.main import evaluate
from app.evaluator.comparator import compare_field

print("=" * 100)
print("DEBUG: Threshold Flow Test")
print("=" * 100)

# Test 1: Direct comparison - should show difference
print("\n1. Direct Field Comparison Test")
print("-" * 100)

test_val_ext = "9870.00"
test_val_gt = "9400.00"
field = "gross_amount"

print(f"Testing: {field}")
print(f"  Extracted: {test_val_ext}")
print(f"  Ground Truth: {test_val_gt}")

for thresh in [100, 90, 80, 70]:
    thresholds = {field: thresh}
    score = compare_field(test_val_ext, test_val_gt, field, thresholds)
    print(f"  Threshold {thresh}: Score = {score:.2f}")

# Test 2: Full evaluation with VERY different thresholds
print("\n\n2. Full Evaluation Test")
print("-" * 100)

# Extremely lenient - should give HIGH scores
lenient_thresholds = {
    "invoice_id": 60,
    "invoice_date": 60,
    "gross_amount": 60,
    "tax_amount": 60,
    "net_amount": 60,
    "total_amount": 60,
    "default": 60,
}

# Extremely strict - should give LOW scores  
strict_thresholds = {
    "invoice_id": 100,
    "invoice_date": 100,
    "gross_amount": 100,
    "tax_amount": 100,
    "net_amount": 100,
    "total_amount": 100,
    "default": 100,
}

print("\nRunning with LENIENT thresholds (60)...")
result_lenient = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=lenient_thresholds
)

print("\nRunning with STRICT thresholds (100)...")
result_strict = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=strict_thresholds
)

print("\n" + "=" * 100)
print("RESULTS COMPARISON")
print("=" * 100)
print(f"{'Metric':<30} {'Lenient (60)':<20} {'Strict (100)':<20} {'Difference':<20}")
print("-" * 100)
print(f"{'Overall Accuracy':<30} {result_lenient['overall_accuracy']:<20.2f} {result_strict['overall_accuracy']:<20.2f} {result_lenient['overall_accuracy'] - result_strict['overall_accuracy']:<+20.2f}")
print(f"{'Strict Pass Rate':<30} {result_lenient['strict_pass_rate']:<20.2f} {result_strict['strict_pass_rate']:<20.2f} {result_lenient['strict_pass_rate'] - result_strict['strict_pass_rate']:<+20.2f}")

print("\nSection Accuracy:")
print("-" * 100)
for section in sorted(set(list(result_lenient.get('section_accuracy', {}).keys()) + list(result_strict.get('section_accuracy', {}).keys()))):
    lenient_acc = result_lenient.get('section_accuracy', {}).get(section, 0)
    strict_acc = result_strict.get('section_accuracy', {}).get(section, 0)
    diff = lenient_acc - strict_acc
    print(f"{section:<30} {lenient_acc:<20.2f} {strict_acc:<20.2f} {diff:<+20.2f}")

print("\n" + "=" * 100)
if abs(result_lenient['overall_accuracy'] - result_strict['overall_accuracy']) > 2.0:
    print("✅ THRESHOLDS ARE WORKING - Significant difference!")
else:
    print("❌ PROBLEM: Thresholds have minimal impact!")
    print("\nPossible reasons:")
    print("  1. Most fields have exact matches (100% regardless)")
    print("  2. Threshold values not being passed correctly")
    print("  3. Need to check the evaluation flow")
print("=" * 100)
