.PHONY: clean clean-test clean-build help

help:
	@echo "Targets:"
	@echo "  clean        Remove caches, test artifacts, and build output"
	@echo "  clean-test   Remove only test-generated artifacts"
	@echo "  clean-build  Remove only build/distribution artifacts"

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
