Updates
=======

.. automodule:: openlens.updater
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``UpdateChecker`` asks the GitHub Releases API for the newest published release,
compares its tag with ``openlens.__version__``, and selects the asset built for
the current operating system and architecture. ``UpdateInstaller`` turns a
downloaded asset into either a detached replace-and-restart helper (Linux and
Windows), an extracted macOS application bundle, or a release-page fallback for
source and pip installs.

The module deliberately has no Qt dependency. ``StartupDialog`` runs the network
work in ``AnalysisWorker`` and renders the result; the core behavior remains
testable with an injected URL opener.
