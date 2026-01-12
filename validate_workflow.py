#!/usr/bin/env python3
"""
GitHub Workflow Validation Script

This script validates the GitHub workflow YAML syntax, checks for deprecated actions,
verifies language configuration, and tests different project configurations.

Requirements validated:
- 1.4: No deprecation warnings appear
- 2.1: Languages are correctly identified
- 2.3: Multi-language projects are handled appropriately
"""

import yaml
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class WorkflowValidator:
    """Validates GitHub workflow configuration and setup."""
    
    def __init__(self, workflow_path: str):
        self.workflow_path = Path(workflow_path)
        self.workflow_data = None
        self.validation_results = []
        self.errors = []
        self.warnings = []
        
    def load_workflow(self) -> bool:
        """Load and parse the workflow YAML file."""
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Handle the 'on:' key which can be problematic in YAML
                self.workflow_data = yaml.safe_load(content)
            return True
        except yaml.YAMLError as e:
            self.errors.append(f"YAML syntax error: {e}")
            return False
        except FileNotFoundError:
            self.errors.append(f"Workflow file not found: {self.workflow_path}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading workflow: {e}")
            return False
    
    def validate_yaml_syntax(self) -> bool:
        """Validate YAML syntax and structure."""
        print("=== YAML Syntax Validation ===")
        
        if not self.load_workflow():
            print("❌ YAML syntax validation failed")
            return False
            
        # Check required top-level keys
        required_keys = ['name', 'jobs']
        # Note: 'on' key might be parsed as boolean True in some YAML parsers
        if True not in self.workflow_data and 'on' not in self.workflow_data:
            self.errors.append("Missing required top-level key: on")
        
        for key in required_keys:
            if key not in self.workflow_data:
                self.errors.append(f"Missing required top-level key: {key}")
        
        # Validate job structure
        if 'jobs' in self.workflow_data:
            for job_name, job_data in self.workflow_data['jobs'].items():
                if not isinstance(job_data, dict):
                    self.errors.append(f"Job '{job_name}' must be a dictionary")
                    continue
                    
                # Check required job keys
                job_required_keys = ['runs-on', 'steps']
                for key in job_required_keys:
                    if key not in job_data:
                        self.errors.append(f"Job '{job_name}' missing required key: {key}")
        
        if self.errors:
            print("❌ YAML structure validation failed")
            for error in self.errors:
                print(f"   Error: {error}")
            return False
        else:
            print("✅ YAML syntax and structure valid")
            return True
    
    def check_action_versions(self) -> bool:
        """Check for outdated GitHub Actions versions."""
        print("\n=== Action Version Validation ===")
        
        # Define current recommended versions
        recommended_versions = {
            'actions/checkout': 'v4',
            'github/codeql-action/init': 'v3',
            'github/codeql-action/analyze': 'v3'
        }
        
        deprecated_patterns = [
            r'actions/checkout@v[123]',
            r'github/codeql-action/init@v[12]',
            r'github/codeql-action/analyze@v[12]'
        ]
        
        version_issues = []
        
        # Check all steps in all jobs
        if 'jobs' in self.workflow_data:
            for job_name, job_data in self.workflow_data['jobs'].items():
                if 'steps' in job_data:
                    for i, step in enumerate(job_data['steps']):
                        if 'uses' in step:
                            action = step['uses']
                            
                            # Check for deprecated versions
                            for pattern in deprecated_patterns:
                                if re.match(pattern, action):
                                    version_issues.append(f"Job '{job_name}', step {i+1}: Deprecated action '{action}'")
                            
                            # Check for recommended versions
                            for action_name, recommended_version in recommended_versions.items():
                                if action.startswith(action_name):
                                    if not action.endswith(f'@{recommended_version}'):
                                        current_version = action.split('@')[-1] if '@' in action else 'latest'
                                        version_issues.append(f"Job '{job_name}', step {i+1}: Action '{action_name}' should use {recommended_version}, currently using {current_version}")
        
        if version_issues:
            print("⚠️  Action version issues found:")
            for issue in version_issues:
                print(f"   Warning: {issue}")
            self.warnings.extend(version_issues)
            return False
        else:
            print("✅ All actions use current recommended versions")
            return True
    
    def validate_language_configuration(self) -> bool:
        """Validate CodeQL language configuration."""
        print("\n=== Language Configuration Validation ===")
        
        expected_languages = ['python', 'java', 'cpp']
        language_issues = []
        
        # Find CodeQL initialization step
        codeql_init_found = False
        if 'jobs' in self.workflow_data:
            for job_name, job_data in self.workflow_data['jobs'].items():
                if 'steps' in job_data:
                    for step in job_data['steps']:
                        if 'uses' in step and 'codeql-action/init' in step['uses']:
                            codeql_init_found = True
                            
                            # Check language configuration
                            if 'with' in step and 'languages' in step['with']:
                                languages_str = step['with']['languages']
                                if isinstance(languages_str, str):
                                    configured_languages = [lang.strip() for lang in languages_str.split(',')]
                                elif isinstance(languages_str, list):
                                    configured_languages = languages_str
                                else:
                                    language_issues.append("Languages must be specified as string or list")
                                    break
                                
                                # Check if all expected languages are present
                                for expected_lang in expected_languages:
                                    if expected_lang not in configured_languages:
                                        language_issues.append(f"Missing expected language: {expected_lang}")
                                
                                # Check for unexpected languages
                                valid_languages = ['python', 'java', 'cpp', 'csharp', 'go', 'javascript', 'ruby']
                                for lang in configured_languages:
                                    if lang not in valid_languages:
                                        language_issues.append(f"Invalid language specified: {lang}")
                            else:
                                language_issues.append("CodeQL init step missing language configuration")
                            break
        
        if not codeql_init_found:
            language_issues.append("CodeQL initialization step not found")
        
        if language_issues:
            print("❌ Language configuration issues found:")
            for issue in language_issues:
                print(f"   Error: {issue}")
            self.errors.extend(language_issues)
            return False
        else:
            print("✅ Language configuration is valid")
            return True
    
    def check_project_structure_compatibility(self) -> bool:
        """Check if workflow is compatible with current project structure."""
        print("\n=== Project Structure Compatibility ===")
        
        project_root = self.workflow_path.parent.parent.parent
        compatibility_issues = []
        
        # Check for expected directories and files
        expected_structures = {
            'Python files': list(project_root.rglob('*.py')),
            'Java files': list(project_root.rglob('*.java')),
            'Kotlin files': list(project_root.rglob('*.kt')),
            'Arduino files': list(project_root.rglob('*.ino')),
            'C++ files': list(project_root.rglob('*.cpp')),
            'C files': list(project_root.rglob('*.c')),
            'Header files': list(project_root.rglob('*.h')) + list(project_root.rglob('*.hpp'))
        }
        
        print("Project structure analysis:")
        total_files = 0
        for file_type, files in expected_structures.items():
            count = len(files)
            total_files += count
            status = "✅" if count > 0 else "⚪"
            print(f"   {status} {file_type}: {count} files")
        
        if total_files == 0:
            compatibility_issues.append("No source files found for any supported language")
        
        # Check for build system files
        build_files = {
            'Gradle': list(project_root.rglob('build.gradle*')) + list(project_root.rglob('settings.gradle*')),
            'Requirements': list(project_root.rglob('requirements*.txt'))
        }
        
        print("\nBuild system analysis:")
        for build_type, files in build_files.items():
            count = len(files)
            status = "✅" if count > 0 else "⚪"
            print(f"   {status} {build_type} files: {count} files")
        
        # Check for specific project directories
        important_dirs = ['Android_app', 'yolo', 'hardware']
        print("\nImportant directories:")
        for dir_name in important_dirs:
            dir_path = project_root / dir_name
            status = "✅" if dir_path.exists() and dir_path.is_dir() else "❌"
            print(f"   {status} {dir_name}/: {'Present' if dir_path.exists() else 'Missing'}")
        
        if compatibility_issues:
            print("\n❌ Project structure compatibility issues:")
            for issue in compatibility_issues:
                print(f"   Error: {issue}")
            self.errors.extend(compatibility_issues)
            return False
        else:
            print("\n✅ Project structure is compatible with workflow")
            return True
    
    def validate_workflow_triggers(self) -> bool:
        """Validate workflow trigger configuration."""
        print("\n=== Workflow Trigger Validation ===")
        
        trigger_issues = []
        
        # Handle the case where 'on' is parsed as boolean True
        triggers = None
        if 'on' in self.workflow_data:
            triggers = self.workflow_data['on']
        elif True in self.workflow_data:
            triggers = self.workflow_data[True]
        else:
            trigger_issues.append("No workflow triggers defined")
            return False
        expected_triggers = ['push', 'pull_request', 'schedule']
        
        print("Configured triggers:")
        for trigger_type in expected_triggers:
            if trigger_type in triggers:
                print(f"   ✅ {trigger_type}: Configured")
                
                # Validate specific trigger configurations
                if trigger_type in ['push', 'pull_request']:
                    if 'branches' in triggers[trigger_type]:
                        branches = triggers[trigger_type]['branches']
                        if 'main' not in branches:
                            self.warnings.append(f"{trigger_type} trigger should include 'main' branch")
                
                elif trigger_type == 'schedule':
                    if isinstance(triggers[trigger_type], list):
                        for schedule in triggers[trigger_type]:
                            if 'cron' not in schedule:
                                trigger_issues.append("Schedule trigger missing cron expression")
                    else:
                        trigger_issues.append("Schedule trigger must be a list")
            else:
                print(f"   ⚪ {trigger_type}: Not configured")
        
        if trigger_issues:
            print("\n❌ Workflow trigger issues:")
            for issue in trigger_issues:
                print(f"   Error: {issue}")
            self.errors.extend(trigger_issues)
            return False
        else:
            print("\n✅ Workflow triggers are properly configured")
            return True
    
    def run_full_validation(self) -> bool:
        """Run all validation checks."""
        print("GitHub Workflow Validation")
        print("=" * 50)
        print(f"Validating: {self.workflow_path}")
        print()
        
        validation_steps = [
            ("YAML Syntax", self.validate_yaml_syntax),
            ("Action Versions", self.check_action_versions),
            ("Language Configuration", self.validate_language_configuration),
            ("Project Compatibility", self.check_project_structure_compatibility),
            ("Workflow Triggers", self.validate_workflow_triggers)
        ]
        
        all_passed = True
        results = {}
        
        for step_name, validation_func in validation_steps:
            try:
                result = validation_func()
                results[step_name] = result
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ {step_name} validation failed with exception: {e}")
                results[step_name] = False
                all_passed = False
        
        # Print summary
        print("\n" + "=" * 50)
        print("VALIDATION SUMMARY")
        print("=" * 50)
        
        for step_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {step_name}")
        
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warnings found:")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        if self.errors:
            print(f"\n❌ {len(self.errors)} errors found:")
            for error in self.errors:
                print(f"   - {error}")
        
        print(f"\nOverall Result: {'✅ PASS' if all_passed else '❌ FAIL'}")
        print(f"Errors: {len(self.errors)}, Warnings: {len(self.warnings)}")
        
        return all_passed

def main():
    """Main validation function."""
    workflow_path = ".github/workflows/codeql-analysis.yml"
    
    if not os.path.exists(workflow_path):
        print(f"❌ Workflow file not found: {workflow_path}")
        return False
    
    validator = WorkflowValidator(workflow_path)
    success = validator.run_full_validation()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)