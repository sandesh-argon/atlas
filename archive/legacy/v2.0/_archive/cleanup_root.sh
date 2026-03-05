#!/bin/bash
# Cleanup v2.0 root directory - keep only subdirectories and essential files

cd <repo-root>/v2.0

# Create archive directory
mkdir -p _archive

# Move temporary/completed status files
mv A6_PREPARATION_COMPLETE.md _archive/ 2>/dev/null || true
mv PRE_A0_COMPLETE.md _archive/ 2>/dev/null || true
mv V1_INTEGRATION_COMPLETE.md _archive/ 2>/dev/null || true
mv create_phaseA_export.sh _archive/ 2>/dev/null || true
mv PROJECT_STATUS.json _archive/ 2>/dev/null || true
mv EXECUTION_FRAMEWORK.md _archive/ 2>/dev/null || true

echo "✅ Cleanup complete!"
echo ""
echo "Remaining files in v2.0 root:"
ls -lh | grep "^-" | awk '{print "  " $9 " (" $5 ")"}'
echo ""
echo "Directories:"
ls -lh | grep "^d" | awk '{print "  " $9 "/"}'
