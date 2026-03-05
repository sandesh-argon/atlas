#!/usr/bin/env python3
"""
Verify all required dependencies are installed and importable.

Run this before deploying to AWS to catch missing packages early.

Usage:
    python utils/verify_dependencies.py
"""

import sys
from pathlib import Path

def check_dependency(package_name: str, import_name: str = None) -> bool:
    """
    Try to import a package and report success/failure.

    Args:
        package_name: Package name for display
        import_name: Actual import name (if different from package_name)

    Returns:
        True if import succeeded, False otherwise
    """
    if import_name is None:
        import_name = package_name

    try:
        __import__(import_name)
        version = None
        try:
            module = sys.modules[import_name]
            version = getattr(module, '__version__', None)
        except:
            pass

        if version:
            print(f"✅ {package_name:20s} version {version}")
        else:
            print(f"✅ {package_name:20s} (version unknown)")
        return True

    except ImportError as e:
        print(f"❌ {package_name:20s} MISSING - install with: pip install {package_name}")
        return False


def main():
    """Check all required dependencies."""
    print("=" * 80)
    print("DEPENDENCY VERIFICATION")
    print("=" * 80)
    print("")

    dependencies = [
        ('numpy', 'numpy'),
        ('pandas', 'pandas'),
        ('scipy', 'scipy'),
        ('scikit-learn', 'sklearn'),
        ('networkx', 'networkx'),
        ('statsmodels', 'statsmodels'),
        ('joblib', 'joblib'),
        ('tqdm', 'tqdm'),
        ('psutil', 'psutil'),
    ]

    results = []
    for package_name, import_name in dependencies:
        success = check_dependency(package_name, import_name)
        results.append(success)

    print("")
    print("=" * 80)

    if all(results):
        print("✅ ALL DEPENDENCIES VERIFIED")
        print("=" * 80)
        return 0
    else:
        failed_count = len([r for r in results if not r])
        print(f"❌ {failed_count} DEPENDENCIES MISSING")
        print("=" * 80)
        print("")
        print("Install missing packages with:")
        print("  pip install numpy pandas scipy scikit-learn networkx statsmodels joblib tqdm psutil")
        return 1


if __name__ == "__main__":
    sys.exit(main())
