---
status: resolved
trigger: "pipx install . fails with 'Directory '/home/buckleyrobinson/projects/cesar/cesar' is not installable'"
created: 2026-02-01T00:00:00Z
updated: 2026-02-01T00:00:00Z
---

## Current Focus

hypothesis: User is running pipx install from wrong directory (inside cesar/ subdirectory)
test: running pipx install from cesar/ subdirectory vs project root
expecting: error from subdirectory, success from root
next_action: verify this is the root cause

## Symptoms

expected: Running `pipx install .` from /home/buckleyrobinson/projects/cesar should install the cesar package
actual: Error message says it's looking in /home/buckleyrobinson/projects/cesar/cesar (doubled path) for pyproject.toml
errors: |
  pipx install .
  ERROR: Directory '/home/buckleyrobinson/projects/cesar/cesar' is not installable. Neither 'setup.py' nor 'pyproject.toml' found.
  Cannot determine package name from spec '/home/buckleyrobinson/projects/cesar/cesar'. Check package spec for errors.
reproduction: Run `pipx install .` from project root
started: User is trying to test after v2.1 milestone completion

## Eliminated

- hypothesis: pyproject.toml has incorrect package path configuration
  evidence: Configuration is correct with [tool.setuptools.packages.find] where=["."] and include=["cesar*"]
  timestamp: 2026-02-01T00:00:00Z

- hypothesis: Missing __init__.py in cesar package
  evidence: cesar/__init__.py exists with proper content including __version__
  timestamp: 2026-02-01T00:00:00Z

- hypothesis: pyproject.toml missing or misconfigured in project root
  evidence: pyproject.toml exists in project root with correct [project] and [project.scripts] configuration
  timestamp: 2026-02-01T00:00:00Z

## Evidence

- timestamp: 2026-02-01T00:00:00Z
  checked: Project structure
  found: |
    - /home/buckleyrobinson/projects/cesar/ (project root) contains pyproject.toml
    - /home/buckleyrobinson/projects/cesar/cesar/ (package directory) contains __init__.py, cli.py, etc.
  implication: Standard Python package structure is correct

- timestamp: 2026-02-01T00:00:00Z
  checked: Running pipx install from project root
  found: Installation succeeds without error
  implication: Configuration is correct when run from proper location

- timestamp: 2026-02-01T00:00:00Z
  checked: Running pipx install from cesar/ subdirectory
  found: Exact error reproduced - "Directory '/home/buckleyrobinson/projects/cesar/cesar' is not installable"
  implication: User ran command from wrong directory

## Resolution

root_cause: User ran `pipx install .` from inside the cesar/ package subdirectory instead of the project root. When running from /home/buckleyrobinson/projects/cesar/cesar/, pipx looks for pyproject.toml in that location, but it only exists in the project root.

fix: No code changes needed. This is a user error - the command must be run from /home/buckleyrobinson/projects/cesar/ (project root), not from /home/buckleyrobinson/projects/cesar/cesar/ (package subdirectory).

verification: |
  - Confirmed error reproduces when run from cesar/ subdirectory
  - Confirmed installation succeeds when run from project root
  - Checked existing pipx installation shows package installed correctly

files_changed: []
