MCP Server
==========

OpenLens can expose its lens database, preset library, and performance
calculators through the
`Model Context Protocol (MCP) <https://modelcontextprotocol.io/>`_, so an AI
assistant can list, create, and analyse lenses from the same SQLite store as
the GUI.

Installation
------------

The server is an optional extra:

.. code-block:: bash

   pip install "openlens[mcp]"

Starting the server
-------------------

The server speaks MCP over stdio. Start it from the package:

.. code-block:: bash

   python -m openlens.mcp_server

or through the CLI entry point:

.. code-block:: bash

   openlens-cli mcp
   # or
   python -m openlens.lens_editor mcp

Point the MCP client at that command. The server opens ``openlens.db`` by
default, the same database the GUI uses.

Tools
-----

``list_lenses``
   List every standalone lens in the database.

``get_lens``
   Return one lens by id.

``create_lens``
   Validate and persist a spherical or flat lens. A radius of ``0`` or
   ``inf`` is a flat surface.

``delete_lens``
   Delete a lens by id.

``calculate_metrics``
   Return the focal length, f-number, Airy disk, depth of field, and
   resolution metrics for a stored lens.

``list_presets``
   List the built-in lens presets, optionally filtered by category.

``load_preset``
   Return a preset lens; pass ``save=true`` to store a copy in the database.

Example request
---------------

.. code-block:: json

   {
     "name": "create_lens",
     "arguments": {
       "name": "MCP singlet",
       "radius_of_curvature_1": 50.0,
       "radius_of_curvature_2": -50.0,
       "thickness": 5.0,
       "diameter": 25.0
     }
   }
