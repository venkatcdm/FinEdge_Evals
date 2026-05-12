"""
Quick test to show threshold impact with realistic differences
"""
from app.evaluator.comparator import compare_field

print("THRESHOLD IMPACT DEMONSTRATION")
print("=" * 80)

# Test scenarios with realistic differences
tests = [
    ("9400.00", "9450.00", "gross_amount", "Amount: 0.53% diff ($50 on $9,400)"),
    ("9400.00", "9500.00", "gross_amount", "Amount: 1.06% diff ($100 on $9,400)"),
    ("9400.00", "9870.00", "gross_amount", "Amount: 5% diff ($470 on $9,400)"),
    ("2024-04-29", "2024-05-02", "invoice_date", "Date: 3 days apart"),
    ("2024-04-29", "2024-05-15", "invoice_date", "Date: 16 days apart"),
    ("Manpower Staffing", "Manpower Staffing Ltda", "merchant.name", "Text: ~85% similar"),
]

print("\nField comparisons with different thresholds:\n")

for ext, gt, field, description in tests:
    print(f"\n{description}")
    print(f"  Ext: {ext} | GT: {gt}")
    
    scores = {}
    for thresh in [100, 95, 90, 85, 80, 75, 70]:
        thresholds = {field: thresh, "default": 85}
        score = compare_field(ext, gt, field, thresholds)
        scores[thresh] = score
    
    # Show the range
    print(f"  Threshold 100: {scores[100]:6.2f}%  |  90: {scores[90]:6.2f}%  |  80: {scores[80]:6.2f}%  |  70: {scores[70]:6.2f}%")
    
    # Calculate improvement from strict to lenient
    improvement = scores[70] - scores[100]
    if improvement > 5:
        print(f"  ✅ Lowering threshold from 100→70 IMPROVES score by +{improvement:.2f} points!")
    else:
        print(f"  → Small change ({improvement:+.2f} points) - field is either exact match or completely wrong")

print("\n" + "=" * 80)
print("KEY INSIGHT:")
print("Lowering thresholds makes matching MORE LIBERAL by:")
print("  • Increasing tolerance bands (5% → 20% → 50%)")
print("  • Widening date windows (±1 day → ±1 month → ±2 months)")
print("  • Accepting lower text similarity (95% → 75% → 60%)")
print("=" * 80)
