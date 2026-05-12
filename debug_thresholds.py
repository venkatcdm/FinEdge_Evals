"""
Debug script to verify thresholds are actually being applied
"""
from app.main import evaluate
from app.evaluator.comparator import compare_field

print("=" * 100)
print("THRESHOLD VERIFICATION TEST")
print("=" * 100)

# Test 1: Direct field comparison with different thresholds
print("\n1. Testing Individual Field Scoring")
print("-" * 100)

test_cases = [
    ("9400.00", "9450.00", "gross_amount", "Amount with 0.53% difference"),
    ("2024-04-29", "2024-05-02", "invoice_date", "Date 3 days apart"),
    ("Manpower Staffing", "Manpower Staffing Ltda", "merchant.name", "Partial text match"),
]

for ext, gt, field, description in test_cases:
    print(f"\n{description}")
    print(f"  Field: {field}")
    print(f"  Extracted: {ext}")
    print(f"  Ground Truth: {gt}")
    
    for thresh in [70, 80, 90, 95, 100]:
        thresholds = {field: thresh}
        score = compare_field(ext, gt, field, thresholds)
        print(f"  Threshold {thresh}: Score = {score:.2f}")

# Test 2: Full evaluation with very different thresholds
print("\n\n2. Testing Full Evaluation with Different Thresholds")
print("-" * 100)

# Very lenient
lenient = {
    "invoice_id": 70,
    "invoice_date": 70,
    "gross_amount": 70,
    "tax_amount": 70,
    "net_amount": 70,
    "description": 70,
    "currency": 80,
    "default": 70,
    # Add all merchant fields
    "merchant.name": 70,
    "merchant.address_line_1": 70,
    "merchant.city": 70,
    "merchant.email": 70,
    "merchant.post_code": 70,
    "merchant.tax_reg_number": 70,
    "merchant.bank_account_number": 70,
    "merchant.country": 70,
    "merchant.province_code": 70,
    # Add all bill_to fields
    "bill_to.name": 70,
    "bill_to.address_line_1": 70,
    "bill_to.city": 70,
    "bill_to.email": 70,
    "bill_to.post_code": 70,
    "bill_to.tax_reg_number": 70,
    "bill_to.requestor_first_name": 70,
    "bill_to.requestor_last_name": 70,
    # Add items fields
    "items.description": 70,
    "items.net_amount": 70,
    "items.gross_amount": 70,
    "items.quantity": 70,
    "items.unit_price": 70,
}

# Very strict
strict = {k: 100 for k in lenient.keys()}
strict["default"] = 100

print("\nRunning evaluation with LENIENT thresholds (70)...")
result_lenient = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=lenient
)

print("\nRunning evaluation with STRICT thresholds (100)...")
result_strict = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=strict
)

print("\n" + "=" * 100)
print("COMPARISON RESULTS")
print("=" * 100)
print(f"{'Metric':<30} {'Lenient (70)':<20} {'Strict (100)':<20} {'Difference':<20}")
print("-" * 100)
print(f"{'Overall Accuracy':<30} {result_lenient['overall_accuracy']:<20} {result_strict['overall_accuracy']:<20} {result_strict['overall_accuracy'] - result_lenient['overall_accuracy']:<+20.2f}")
print(f"{'Strict Pass Rate':<30} {result_lenient['strict_pass_rate']:<20} {result_strict['strict_pass_rate']:<20} {result_strict['strict_pass_rate'] - result_lenient['strict_pass_rate']:<+20.2f}")

# Show section accuracy comparison
print(f"\n{'Section Accuracy':<30}")
print("-" * 100)
all_sections = set(list(result_lenient.get('section_accuracy', {}).keys()) + list(result_strict.get('section_accuracy', {}).keys()))
for section in sorted(all_sections):
    lenient_acc = result_lenient.get('section_accuracy', {}).get(section, 0)
    strict_acc = result_strict.get('section_accuracy', {}).get(section, 0)
    diff = strict_acc - lenient_acc
    print(f"{section:<30} {lenient_acc:<20} {strict_acc:<20} {diff:<+20.2f}")

# Show some field accuracy comparisons
print(f"\n{'Field Accuracy (sample)':<30}")
print("-" * 100)
sample_fields = ['invoice_id', 'invoice_date', 'gross_amount', 'tax_amount', 'merchant.name', 'merchant.email', 'items.description', 'items.gross_amount']
for field in sample_fields:
    lenient_acc = result_lenient.get('field_accuracy', {}).get(field, 0)
    strict_acc = result_strict.get('field_accuracy', {}).get(field, 0)
    diff = strict_acc - lenient_acc
    print(f"{field:<30} {lenient_acc:<20} {strict_acc:<20} {diff:<+20.2f}")

print("\n" + "=" * 100)
if abs(result_strict['overall_accuracy'] - result_lenient['overall_accuracy']) > 1.0:
    print("✅ THRESHOLDS ARE WORKING - Significant difference detected!")
else:
    print("⚠️  WARNING: Thresholds have minimal impact. This could mean:")
    print("   1. Most fields have exact matches (score 100 regardless of threshold)")
    print("   2. Data quality is very high or very low")
    print("   3. Threshold mapping needs adjustment")
print("=" * 100)
