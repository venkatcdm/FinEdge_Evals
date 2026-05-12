"""
Debug: Check specific Merchant and Bill To field scores
"""
from app.main import evaluate

print("Checking Merchant and Bill To sections with different thresholds\n")
print("=" * 100)

# Very lenient
lenient = {
    "default": 50,
    "merchant.name": 50,
    "merchant.address_line_1": 50,
    "merchant.city": 50,
    "merchant.email": 50,
    "merchant.post_code": 50,
    "merchant.tax_reg_number": 50,
    "merchant.country": 50,
    "merchant.province_code": 50,
    "bill_to.name": 50,
    "bill_to.address_line_1": 50,
    "bill_to.city": 50,
    "bill_to.email": 50,
    "bill_to.post_code": 50,
    "bill_to.tax_reg_number": 50,
    "bill_to.requestor_first_name": 50,
    "bill_to.requestor_last_name": 50,
    "bill_to.country": 50,
    "bill_to.province_code": 50,
}

# Very strict
strict = {
    "default": 100,
    "merchant.name": 100,
    "merchant.address_line_1": 100,
    "merchant.city": 100,
    "merchant.email": 100,
    "merchant.post_code": 100,
    "merchant.tax_reg_number": 100,
    "merchant.country": 100,
    "merchant.province_code": 100,
    "bill_to.name": 100,
    "bill_to.address_line_1": 100,
    "bill_to.city": 100,
    "bill_to.email": 100,
    "bill_to.post_code": 100,
    "bill_to.tax_reg_number": 100,
    "bill_to.requestor_first_name": 100,
    "bill_to.requestor_last_name": 100,
    "bill_to.country": 100,
    "bill_to.province_code": 100,
}

print("Running with LENIENT thresholds (50)...")
result_lenient = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=lenient
)

print("\nRunning with STRICT thresholds (100)...")
result_strict = evaluate(
    "sample_data/extracted.json",
    "sample_data/groundtruth.json",
    "germany",
    thresholds=strict
)

print("\n" + "=" * 100)
print("MERCHANT SECTION - Field Level Comparison")
print("=" * 100)
print(f"{'Field':<40} {'Lenient (50)':<15} {'Strict (100)':<15} {'Difference':<15}")
print("-" * 100)

merchant_fields = {k: v for k, v in result_lenient.get('field_accuracy', {}).items() if k.startswith('merchant.')}
for field in sorted(merchant_fields.keys()):
    lenient_val = result_lenient.get('field_accuracy', {}).get(field, 0)
    strict_val = result_strict.get('field_accuracy', {}).get(field, 0)
    diff = lenient_val - strict_val
    print(f"{field:<40} {lenient_val:<15.2f} {strict_val:<15.2f} {diff:<+15.2f}")

print("\n" + "=" * 100)
print("BILL TO SECTION - Field Level Comparison")
print("=" * 100)
print(f"{'Field':<40} {'Lenient (50)':<15} {'Strict (100)':<15} {'Difference':<15}")
print("-" * 100)

bill_to_fields = {k: v for k, v in result_lenient.get('field_accuracy', {}).items() if k.startswith('bill_to.')}
for field in sorted(bill_to_fields.keys()):
    lenient_val = result_lenient.get('field_accuracy', {}).get(field, 0)
    strict_val = result_strict.get('field_accuracy', {}).get(field, 0)
    diff = lenient_val - strict_val
    print(f"{field:<40} {lenient_val:<15.2f} {strict_val:<15.2f} {diff:<+15.2f}")

print("\n" + "=" * 100)
print("SECTION ACCURACY COMPARISON")
print("=" * 100)
print(f"{'Section':<30} {'Lenient (50)':<15} {'Strict (100)':<15} {'Difference':<15}")
print("-" * 100)

for section in ['merchant', 'bill_to']:
    lenient_acc = result_lenient.get('section_accuracy', {}).get(section, 0)
    strict_acc = result_strict.get('section_accuracy', {}).get(section, 0)
    diff = lenient_acc - strict_acc
    print(f"{section:<30} {lenient_acc:<15.2f} {strict_acc:<15.2f} {diff:<+15.2f}")

print("\n" + "=" * 100)
print("DIAGNOSIS:")
print("=" * 100)

# Check how many fields are at extremes
merchant_extremes = sum(1 for v in merchant_fields.values() if v >= 99 or v <= 1)
bill_to_extremes = sum(1 for v in bill_to_fields.values() if v >= 99 or v <= 1)

print(f"\nMerchant Section:")
print(f"  Total fields: {len(merchant_fields)}")
print(f"  Fields at extremes (0% or 100%): {merchant_extremes}")
print(f"  Fields in middle range (1-99%): {len(merchant_fields) - merchant_extremes}")

print(f"\nBill To Section:")
print(f"  Total fields: {len(bill_to_fields)}")
print(f"  Fields at extremes (0% or 100%): {bill_to_extremes}")
print(f"  Fields in middle range (1-99%): {len(bill_to_fields) - bill_to_extremes}")

if merchant_extremes > len(merchant_fields) * 0.7:
    print("\n⚠️  Most Merchant fields are at 0% or 100% - thresholds won't help much")
    print("   Solution: Improve data extraction quality for fields showing 0%")

if bill_to_extremes > len(bill_to_fields) * 0.7:
    print("\n⚠️  Most Bill To fields are at 0% or 100% - thresholds won't help much")
    print("   Solution: Improve data extraction quality for fields showing 0%")

print("=" * 100)
