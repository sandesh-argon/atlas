#!/usr/bin/env python3
"""
Fix sign consistency bug in A4 validation logic.

Bug: Validation allowed edges where beta and CI have opposite signs.
Fix: Add explicit sign consistency check.

Runtime: ~30 seconds
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime

print("="*60)
print("FIXING A4 SIGN CONSISTENCY BUG")
print("="*60)

# Load original results
print("\n1. Loading original results...")
with open('outputs/lasso_effect_estimates.pkl', 'rb') as f:
    data = pickle.load(f)

df = pd.DataFrame(data['all_results'])
print(f"   Loaded {len(df):,} edges")

# Check original validated count
original_validated = df[
    (df['status'] == 'success') &
    (df['ci_lower'] * df['ci_upper'] > 0) &
    (df['beta'].abs() > 0.12)
]
print(f"   Original 'validated': {len(original_validated):,}")

# Identify sign-inconsistent edges
print("\n2. Identifying sign-inconsistent edges...")
sign_errors = original_validated[
    ((original_validated['beta'] > 0) & (original_validated['ci_upper'] < 0)) |
    ((original_validated['beta'] < 0) & (original_validated['ci_lower'] > 0))
]
print(f"   Sign-inconsistent edges: {len(sign_errors):,} ({len(sign_errors)/len(original_validated)*100:.1f}%)")

# Save audit of removed edges
print("\n3. Saving audit of removed edges...")
sign_errors[['source', 'target', 'beta', 'ci_lower', 'ci_upper']].to_csv(
    'diagnostics/removed_sign_inconsistent_edges.csv',
    index=False
)
print(f"   Saved to: diagnostics/removed_sign_inconsistent_edges.csv")

# Apply CORRECT validation logic
print("\n4. Applying correct validation logic...")
correct_validated = df[
    (df['status'] == 'success') &
    (df['beta'].abs() > 0.12) &
    (df['ci_lower'] * df['ci_upper'] > 0) &  # Same sign
    (np.sign(df['beta']) == np.sign(df['ci_lower'])) &  # Beta agrees with CI
    (np.sign(df['beta']) == np.sign(df['ci_upper']))
].copy()

print(f"   Correctly validated: {len(correct_validated):,}")
print(f"   Removed: {len(original_validated) - len(correct_validated):,}")

# Verify zero sign errors
verify_errors = correct_validated[
    ((correct_validated['beta'] > 0) & (correct_validated['ci_upper'] < 0)) |
    ((correct_validated['beta'] < 0) & (correct_validated['ci_lower'] > 0))
]
print(f"\n5. Verification: Sign errors in corrected set: {len(verify_errors)}")
if len(verify_errors) == 0:
    print("   ✅ SUCCESS: Zero sign inconsistencies")
else:
    print("   ❌ ERROR: Sign errors still present!")
    raise ValueError("Sign consistency fix failed")

# Update data structure
print("\n6. Creating fixed dataset...")
data_fixed = {
    'all_results': df.to_dict('records'),
    'validated_edges': correct_validated.to_dict('records'),
    'metadata': {
        **data['metadata'],
        'n_validated': len(correct_validated),
        'n_validated_original': len(original_validated),
        'n_removed_sign_errors': len(sign_errors),
        'timestamp_fixed': datetime.now().isoformat(),
        'fix_applied': 'sign_consistency_check'
    }
}

# Save fixed dataset
with open('outputs/lasso_effect_estimates_FIXED.pkl', 'wb') as f:
    pickle.dump(data_fixed, f)
print(f"   Saved to: outputs/lasso_effect_estimates_FIXED.pkl")

# Create summary
print("\n" + "="*60)
print("FIX SUMMARY")
print("="*60)
print(f"Original validated:    {len(original_validated):,}")
print(f"Sign-inconsistent:     {len(sign_errors):,} ({len(sign_errors)/len(original_validated)*100:.1f}%)")
print(f"Correctly validated:   {len(correct_validated):,}")
print(f"Reduction:             {len(original_validated) - len(correct_validated):,}")
print()
print(f"✅ Sign bug FIXED")
print(f"✅ {len(correct_validated):,} validated edges ready for A5")
print("="*60)

# Save summary
with open('outputs/sign_bug_fix_summary.txt', 'w') as f:
    f.write("A4 Sign Consistency Bug Fix\n")
    f.write("="*60 + "\n\n")
    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"Original validated edges:    {len(original_validated):,}\n")
    f.write(f"Sign-inconsistent removed:   {len(sign_errors):,}\n")
    f.write(f"Correctly validated:         {len(correct_validated):,}\n")
    f.write(f"Reduction:                   {len(original_validated) - len(correct_validated):,} ({(len(original_validated) - len(correct_validated))/len(original_validated)*100:.1f}%)\n\n")
    f.write("Verification: 0 sign errors in corrected dataset\n")
    f.write("Status: READY FOR A5\n")

print("\nSummary saved to: outputs/sign_bug_fix_summary.txt")
