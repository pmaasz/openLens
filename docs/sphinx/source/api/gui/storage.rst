Lens Storage
============

.. automodule:: src.gui.storage
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The LensStorage class provides persistence utilities for saving and loading
lens data in the GUI application.

Example Usage
-------------

.. code-block:: python

    from src.gui.storage import LensStorage

    storage = LensStorage()

    # Save lens data
    lens_data = {'radius_1': 50.0, 'radius_2': -50.0, ...}
    storage.save_lens(lens_data, 'my_lens.json')

    # Load lens data
    loaded = storage.load_lens('my_lens.json')
