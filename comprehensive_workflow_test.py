#!/usr/bin/env python3
"""
Comprehensive GitHub Workflow Test Suite

This script runs all validation tests for the GitHub workflow to ensure
it meets all requirements for task 5.

Requirements validated:
- 1.4: No deprecation warnings appear
- 2.1: Languages are correctly identified
- 2.3: Multi-language projects are handled appropriately
"""

import sys
import subprocess
from pathlib import Path

def run_test(test_name: str, test_command: list) -> bool:
    """Run a test and return success status."""
    print(f"\n{'='*60}")
    print(f"RUNNING: {test_name}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            test_command,
            capture_output=False,
            text=True,
            cwd=Path.cwd()
        )
        
        success = result.returncode == 0
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n{status}: {test_name}")
        
        return success
        
    except Exception as e:
        print(f"❌ ERROR running {test_name}: {e}")
        return False

def main():
    """Run comprehensive workflow validation tests."""
    print("Comprehensive GitHub Workflow Test Suite")
    print("=" * 60)
    print("Validating GitHub workflow against all requirements")
    print()
    
    # Define all tests to run
    tests = [
        ("YAML Syntax & Structure Validation", ["python", "validate_workflow.py"]),
        ("Workflow Configuration Testing", ["python", "test_workflow_configurations.py"]),
        ("Deprecation Warning Check", ["python", "check_deprecations_fixed.py"])
    ]
    
    results = []
    
    # Run all tests
    for test_name, test_command in tests:
        success = run_test(test_name, test_command)
        results.append((test_name, success))
    
    # Print final summary
    print(f"\n{'='*60}")
    print("COMPREHENSIVE TEST SUMMARY")
    print(f"{'='*60}")
    
    passed_tests = 0
    total_tests = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed_tests += 1
    
    print(f"\nResults: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
        print("The GitHub workflow is fully validated and ready for use.")
        print("\nValidated requirements:")
        print("  ✅ 1.4: No deprecation warnings appear")
        print("  ✅ 2.1: Languages are correctly identified")
        print("  ✅ 2.3: Multi-language projects are handled appropriately")
        return True
    else:
        print(f"\n❌ {total_tests - passed_tests} tests failed")
        print("Please review the failed tests and fix any issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)