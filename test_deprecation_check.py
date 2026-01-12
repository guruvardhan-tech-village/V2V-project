#!/usr/bin/env python3
"""
Simple test script to verify deprecation checking functionality.
"""

import sys
from pathlib import Path

def test_deprecation_check():
    """Test the deprecation checking functionality."""
    print("Testing Deprecation Check Functionality")
    print("=" * 50)
    
    workflow_path = ".github/workflows/codeql-analysis.yml"
    
    if not Path(workflow_path).exists():
        print(f"❌ Workflow file not found: {workflow_path}")
        return False
    
    try:
        from check_deprecations import DeprecationChecker
        
        checker = DeprecationChecker(workflow_path)
        success = checker.run_full_check()
        
        return success
        
    except Exception as e:
        print(f"❌ Error running deprecation check: {e}")
        return False

if __name__ == "__main__":
    success = test_deprecation_check()
    print(f"\nTest result: {'✅ PASS' if success else '❌ FAIL'}")
    sys.exit(0 if success else 1)