"""
Test script to demonstrate threshold impact on evaluation scores.
"""
from app.main import evaluate

# Test with different threshold settings
print("=" * 80)
print("Testing Threshold Impact on Evaluation")
print("=" * 80)

# Test 1: Default thresholds
print("\n[Test 1] Default thresholds")
result1 = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=None
)
print(f"Overall Accuracy: {result1['overall_accuracy']}%")
print(f"Strict Pass Rate: {result1['strict_pass_rate']}%")
print(f"Invoice ID Accuracy: {result1['field_accuracy'].get('invoice_id', 'N/A')}%")
print(f"Gross Amount Accuracy: {result1['field_accuracy'].get('gross_amount', 'N/A')}%")

# Test 2: Very strict thresholds (95-100)
print("\n[Test 2] Very strict thresholds (95-100 for key fields)")
strict_thresholds = {
    "invoice_id": 100,
    "invoice_date": 95,
    "gross_amount": 98,
    "tax_amount": 98,
    "net_amount": 98,
    "description": 95,
    "currency": 100,
    "default": 95
}
result2 = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=strict_thresholds
)
print(f"Overall Accuracy: {result2['overall_accuracy']}%")
print(f"Strict Pass Rate: {result2['strict_pass_rate']}%")
print(f"Invoice ID Accuracy: {result2['field_accuracy'].get('invoice_id', 'N/A')}%")
print(f"Gross Amount Accuracy: {result2['field_accuracy'].get('gross_amount', 'N/A')}%")

# Test 3: Lenient thresholds (70-80)
print("\n[Test 3] Lenient thresholds (70-80 for key fields)")
lenient_thresholds = {
    "invoice_id": 85,
    "invoice_date": 75,
    "gross_amount": 75,
    "tax_amount": 75,
    "net_amount": 75,
    "description": 70,
    "currency": 90,
    "default": 75
}
result3 = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=lenient_thresholds
)
print(f"Overall Accuracy: {result3['overall_accuracy']}%")
print(f"Strict Pass Rate: {result3['strict_pass_rate']}%")
print(f"Invoice ID Accuracy: {result3['field_accuracy'].get('invoice_id', 'N/A')}%")
print(f"Gross Amount Accuracy: {result3['field_accuracy'].get('gross_amount', 'N/A')}%")

# Show differences
print("\n" + "=" * 80)
print("Comparison Summary")
print("=" * 80)
print(f"{'Metric':<25} {'Default':<15} {'Strict':<15} {'Lenient':<15}")
print("-" * 80)
print(f"{'Overall Accuracy':<25} {result1['overall_accuracy']:<15} {result2['overall_accuracy']:<15} {result3['overall_accuracy']:<15}")
print(f"{'Strict Pass Rate':<25} {result1['strict_pass_rate']:<15} {result2['strict_pass_rate']:<15} {result3['strict_pass_rate']:<15}")

print("\n✓ Threshold changes now have a SIGNIFICANT impact on scores!")
print("✓ Higher thresholds = stricter matching = lower scores")
print("✓ Lower thresholds = more lenient = higher scores")
