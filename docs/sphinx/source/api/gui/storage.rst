Lens Storage
============

.. automodule:: openlens.gui.storage
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``LensStorage`` is the GUI-facing facade over
:class:`openlens.database.DatabaseManager`. It loads ``Lens`` and
``OpticalSystem`` objects, saves the complete library, deletes records, and
reports the last failure through ``last_error``.

SQLite is the source of truth. ``storage_file=None`` resolves the per-user
database through :func:`openlens.paths.resolve_db_path`; tests and embedders can
pass an isolated path.

Example
-------

.. code-block:: python

    from openlens.gui.storage import LensStorage

    storage = LensStorage("scratch.db")
    items = storage.load_lenses()

    if not storage.save_lenses(items, reconcile=True):
        print(storage.last_error)
