# Release Agent

Performs release tasks for OpenLens: version bump, build executables, tag, and publish.

## When to Use

Use this agent when:
- Preparing a new release (e.g., `v0.1.0`, `v0.2.0`)
- Building standalone executables for distribution
- Running full test suite before release

## Workflow

1. **Verify Clean State**: Ensure no uncommitted changes
2. **Update Version**: Bump version in `setup.py`
3. **Run Tests**: Execute `python3 tests/run_all_tests.py`
4. **Build Executable**: Run PyInstaller with correct paths
5. **Git Operations**: Commit, tag, and push to remote
6. **Report**: Provide download link and release notes

## Commands

### Full Release
```
/release 0.1.0
```

### Build Only
```
/release build
```

### Version Bump Only
```
/release bump 0.2.0
```

## Safety Checks

- **No Force Push**: Never force push to master/main
- **Tests Pass**: Abort if test suite fails
- **Clean Working Tree**: Warn if uncommitted changes exist

## Example Session

```
User: /release 0.1.0
Agent:
- Checked working tree - clean
- Updated version in setup.py to 0.1.0
- Ran test suite - all 88 tests passed
- Built Linux executable using PyInstaller
- Created commit and tag v0.1.0
- Pushed to origin
- Executable available at: dist/OpenLens-v0.1.0-Linux
```

## Notes

- Requires virtual environment with PyInstaller installed
- Builds Linux binary by default (Windows requires separate host)
- Uses semantic versioning (semver.org)
