Optical System
==============

.. automodule:: openlens.optical_system
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``OpticalSystem`` stores an ordered list of lens elements and air gaps, an
aperture stop, and an ``OpticalAssembly`` tree for nested groups and alignment.
The flat lists and the tree are kept in sync.

Serialization is dictionary-based (``to_dict``/``from_dict``); SQLite is the
primary persistence layer, while JSON is an interchange format.
