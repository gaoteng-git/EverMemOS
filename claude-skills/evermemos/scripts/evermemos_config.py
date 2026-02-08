#!/usr/bin/env python3
"""
EverMemOS Configuration Manager

This module handles configuration loading and project exclusion logic,
similar to claude-mem's SettingsDefaultsManager and isProjectExcluded.
"""

import os
import json
import sys
from pathlib import Path


def get_excluded_projects():
    """
    Get list of projects that should be excluded from tracking

    Follows claude-mem's approach:
    1. Check environment variable first
    2. Fall back to config file
    3. Default to empty list

    Returns:
        list: List of project paths to exclude
    """
    # Method 1: From environment variable (comma-separated)
    env_excluded = os.environ.get('EVERMEMOS_EXCLUDED_PROJECTS', '')
    if env_excluded:
        excluded_list = [path.strip() for path in env_excluded.split(',') if path.strip()]
        if excluded_list:
            return excluded_list

    # Method 2: From config file
    config_path = Path.home() / '.evermemos' / 'config.json'
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                excluded = config.get('excluded_projects', [])
                if excluded:
                    return excluded
        except Exception as e:
            print(f"[WARNING] Failed to load config from {config_path}: {e}", file=sys.stderr)

    # Default: no exclusions
    return []


def is_project_excluded(cwd):
    """
    Check if a project should be excluded from tracking

    This replicates claude-mem's isProjectExcluded logic:
    - Check if cwd matches any excluded project path
    - Support both exact matches and parent directory checks

    Args:
        cwd: Current working directory

    Returns:
        bool: True if project should be excluded
    """
    if not cwd:
        return False

    excluded_projects = get_excluded_projects()
    if not excluded_projects:
        return False

    # Normalize cwd path
    try:
        cwd_path = Path(cwd).resolve()
    except Exception as e:
        print(f"[WARNING] Failed to resolve cwd path: {cwd}: {e}", file=sys.stderr)
        return False

    # Check if cwd matches any excluded project
    for excluded in excluded_projects:
        try:
            excluded_path = Path(excluded).resolve()

            # Check if cwd is the excluded path or a subdirectory
            if cwd_path == excluded_path or excluded_path in cwd_path.parents:
                return True
        except Exception as e:
            # Invalid path in config, skip it
            print(f"[WARNING] Invalid excluded project path: {excluded}: {e}", file=sys.stderr)
            continue

    return False


# Export symbols
__all__ = ['get_excluded_projects', 'is_project_excluded']
