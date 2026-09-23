.PHONY: clean clean-test clean-build help qa qa-gui qa-visual

help:
	@echo "Targets:"
	@echo "  clean        Remove caches, test artifacts, and build output"
	@echo "  clean-test   Remove only test-generated artifacts"
	@echo "  clean-build  Remove only build/distribution artifacts"
	@echo "  qa           Full QA: unit suite + GUI flows + visuals (headless)"
	@echo "  qa-gui       GUI user-flow tests only (replaces click-through)"
	@echo "  qa-visual    Visual regression tests only"

# Remove caches, test artifacts, and build output.
# NOTE: does NOT touch virtualenvs (venv/, .venv/) or user databases
# (openlens.db, lenses.db) - those hold real data/environments.
clean: clean-test clean-build
	find . -type d -name __pycache__ -not -path "./venv/*" -not -path "./.venv/*" -exec rm -rf {} +
	rm -rf .pytest_cache htmlcov .coverage

clean-test:
	rm -f test_*.db test_*.db-shm test_*.db-wal
	rm -f nonexistent_file.db

clean-build:
	rm -rf build dist openlens.egg-info

# Automated QA (headless): replaces the manual click-through checklist.
# See tests/gui_flows/README.md for the manual -> automated mapping.
qa:
	QT_QPA_PLATFORM=offscreen python3 -m pytest tests/gui_flows -v
	QT_QPA_PLATFORM=offscreen OPENLENS_SKIP_SLOW=1 python3 -m unittest discover -s tests -t .

qa-gui:
	QT_QPA_PLATFORM=offscreen python3 -m pytest tests/gui_flows -n auto -q -k "not visual"

qa-visual:
	QT_QPA_PLATFORM=offscreen python3 -m pytest tests/gui_flows/test_visual_regression.py -v
