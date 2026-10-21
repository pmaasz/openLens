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

The top-level index is divided by audience:

- **User Documentation** - Getting Started, the GUI/CLI walkthrough, and the
  Nikon Series E 50mm worked example.
- **Technical Documentation** - Architecture, contributing guidelines, and the
  generated API reference.
- **Scientific Documentation** - optical conventions and equations, image-quality
  metrics, and thermal/mechanical effects.

## Reference Markdown

| File | Status |
|------|--------|
| `README.md` | This index. |
| `CONTRIBUTING.md` | Short entry point; the authoritative guide is `sphinx/source/contributing.rst`. Kept because the root README links to it. |
| `TESTING.md` | Short test-command reference; authoritative details are in `sphinx/source/contributing.rst`. |
| `ARCHITECTURE.md` | Short architecture summary; authoritative page is `sphinx/source/architecture.rst`. |
| `API_DOCUMENTATION.md` | Short library entry point; authoritative signatures are in `sphinx/source/api/`. |
| `FEATURE_ABERRATIONS.md` | Technical reference for the aberration calculations, not yet migrated. |

The feature-status and ray-tracing implementation notes that used to live here
were duplicates of the Sphinx pages and of `CHANGELOG.md`, so they are gone.
The Nikon prescription note moved to
`sphinx/source/nikon_series_e_50mm.rst`.
