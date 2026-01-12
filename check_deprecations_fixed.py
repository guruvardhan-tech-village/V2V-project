#!/usr/bin/env python3
"""
GitHub Actions Deprecation Warning Checker

This script checks for deprecated GitHub Actions and configurations
that might cause warnings in the workflow execution.

Requirements validated:
- 1.4: No deprecation warnings appear
"""

import yaml
import re
import sys
from pathlib import Path
from typing import Dict, List

def check_workflow_deprecations(workflow_path: str) -> bool:
    """Check workflow for deprecation issues."""
    print("GitHub Actions Deprecation Check")
    print("=" * 50)
    print(f"Checking: {workflow_path}")
    print()
    
    # Load workflow
    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow_data = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading workflow: {e}")
        return False
    
    issues = []
    
    # Define current recommended versions
    recommended_versions = {
        'actions/checkout': 'v4',
        'github/codeql-action/init': 'v3',
        'github/codeql-action/analyze': 'v3'
    }
    
    print("=== Checking Action Versions ===")
    
    # Check all steps in all jobs
    if 'jobs' in workflow_data:
        for job_name, job_data in workflow_data['jobs'].items():
            if 'steps' in job_data:
                for i, step in enumerate(job_data['steps']):
                    if 'uses' in step:
                        action = step['uses']
                        step_name = step.get('name', f'Step {i+1}')
                        
                        # Parse action name and version
                        if '@' in action:
                            action_name, version = action.rsplit('@', 1)
                        else:
                            action_name = action
                            version = 'latest'
                        
                        # Check against recommended versions
                        if action_name in recommended_versions:
                            recommended = recommended_versions[action_name]
                            
                            if version != recommended and version != 'latest':
                                if version in ['v1', 'v2'] and action_name.startswith('github/codeql-action'):
                                    issues.append(f"❌ {job_name}/{step_name}: {action_name}@{version} is deprecated (use @{recommended})")
                                elif version in ['v1', 'v2', 'v3'] and action_name == 'actions/checkout':
                                    issues.append(f"⚠️  {job_name}/{step_name}: {action_name}@{version} is outdated (use @{recommended})")
                                else:
                                    print(f"✅ {job_name}/{step_name}: {action_name}@{version}")
                            else:
                                print(f"✅ {job_name}/{step_name}: {action_name}@{version}")
    
    print("\n=== Checking for Deprecated Features ===")
    
    # Read raw content to check for deprecated patterns
    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading workflow content: {e}")
        return False
    
    deprecated_patterns = [
        (r'echo\s*::\s*set-output', 'set-output command (use GITHUB_OUTPUT)'),
        (r'echo\s*::\s*save-state', 'save-state command (use GITHUB_STATE)'),
        (r'echo\s*::\s*add-path', 'add-path command (use GITHUB_PATH)')
    ]
    
    for pattern, description in deprecated_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append(f"❌ Deprecated feature found: {description}")
        else:
            print(f"✅ No deprecated {description.split('(')[0].strip()} usage")
    
    print("\n=== Checking Runner Versions ===")
    
    deprecated_runners = ['ubuntu-18.04', 'macos-10.15', 'windows-2016']
    
    if 'jobs' in workflow_data:
        for job_name, job_data in workflow_data['jobs'].items():
            if 'runs-on' in job_data:
                runner = job_data['runs-on']
                if runner in deprecated_runners:
                    issues.append(f"❌ {job_name}: Deprecated runner '{runner}'")
                else:
                    print(f"✅ {job_name}: Runner '{runner}' is current")
    
    # Print summary
    print("\n" + "=" * 50)
    print("DEPRECATION CHECK SUMMARY")
    print("=" * 50)
    
    if not issues:
        print("✅ No deprecation warnings found!")
        print("All actions, features, and runners are current")
        return True
    else:
        print(f"❌ {len(issues)} deprecation issues found:")
        for issue in issues:
            print(f"   {issue}")
        print("\nThese issues may cause deprecation warnings during workflow execution")
        return False

def main():
    """Main function."""
    workflow_path = ".github/workflows/codeql-analysis.yml"
    
    if not Path(workflow_path).exists():
        print(f"❌ Workflow file not found: {workflow_path}")
        return False
    
    return check_workflow_deprecations(workflow_path)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)