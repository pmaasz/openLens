Database
========

.. automodule:: openlens.database
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``DatabaseManager`` owns the SQLite schema and migrations for lenses,
assemblies, and tolerance metadata. The GUI's ``LensStorage`` facade wraps it.

The default database path is resolved by ``openlens.paths.resolve_db_path``;
tests and embedders can pass an explicit path.
