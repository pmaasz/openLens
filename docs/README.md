# OpenLens Documentation

**Sphinx is the source of truth.** Everything under `sphinx/` is the maintained
documentation; the Markdown files that remain exist only because the README and
older links point at them, and mirror their RST counterparts.

## Build and View Locally

```bash
pip install sphinx sphinx-rtd-theme
cd sphinx
make html
xdg-open build/html/index.html   # Linux
open build/html/index.html       # macOS
```

## Documentation policy

- New user guides, tutorials, architecture notes and contributor docs go into
  `sphinx/source/` as `.rst` files, listed in a `toctree` in
  `sphinx/source/index.rst`.
- Do not add new Markdown files under `docs/`. Update the RST page instead.
- Status snapshots ("vX completed N features") are not documentation. Feature
  history lives in `CHANGELOG.md`, release notes and the issue tracker.
- When a Markdown mirror and its RST page disagree, the RST page wins and the
  mirror is updated or shortened.

## Sphinx Structure

- **Getting Started** - installation and quick start
- **User Guide** - GUI walkthrough, lens types and ray tracing
- **Nikon Series E 50mm** - worked multi-element prescription example
- **Architecture** - system design, data flow and module organization
- **Contributing** - coding standards, testing and pull-request process
- **API Reference** - generated from the `openlens` docstrings

## Reference Markdown

| File | Status |
|------|--------|
| `README.md` | This index. |
| `CONTRIBUTING.md` | Mirror of `sphinx/source/contributing.rst`; kept because the root README links to it. |
| `TESTING.md` | Mirror of the testing sections in `sphinx/source/contributing.rst`; linked from the README test badge. |
| `ARCHITECTURE.md` | Mirror of `sphinx/source/architecture.rst`. |
| `API_DOCUMENTATION.md` | Hand-written library guide (installation, examples). The Sphinx API reference is authoritative for signatures. |
| `FEATURE_ABERRATIONS.md` | Technical reference for the aberration calculations, not yet migrated. |

The feature-status and ray-tracing implementation notes that used to live here
were duplicates of the Sphinx pages and of `CHANGELOG.md`, so they are gone.
The Nikon prescription note moved to
`sphinx/source/nikon_series_e_50mm.rst`.
