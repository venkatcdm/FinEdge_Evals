"""
Debug script to understand field-level scoring
"""
from app.evaluator.comparator import compare_field

# Test different scenarios
test_cases = [
    # (extracted, ground_truth, field_name)
    ("12345", "12345", "invoice_id"),  # Exact match
    ("12345", "12346", "invoice_id"),  # Off by 1
    ("2024-04-29", "2024-04-29", "invoice_date"),  # Exact date
    ("2024-04-29", "2024-04-30", "invoice_date"),  # 1 day off
    ("9400.00", "9400.00", "gross_amount"),  # Exact amount
    ("9400.00", "9405.00", "gross_amount"),  # 5 off
    ("9400.00", "9450.00", "gross_amount"),  # 50 off
    ("Manpower Staffing", "Manpower Staffing Ltda", "merchant.name"),  # Partial
    ("roberio.alencar@manpowergroup.com.br", "different@email.com", "merchant.email"),  # Different
]

print("Testing scoring with different thresholds\n")
print("=" * 100)

for ext, gt, field in test_cases:
    print(f"\nField: {field}")
    print(f"  Extracted: {ext}")
    print(f"  Ground Truth: {gt}")
    
    # Test with different thresholds
    for threshold_val in [70, 80, 90, 95, 100]:
        thresholds = {field: threshold_val}
        score = compare_field(ext, gt, field, thresholds)
        print(f"  Threshold {threshold_val:>3}: Score = {score:.2f}")
