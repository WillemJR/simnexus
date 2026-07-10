"""
Optional PySide6 GUI for watching simnexus workflow progress.

This package is intentionally kept *outside* the ``simnexus`` package so that
PySide6 stays an optional dependency: nothing in ``simnexus`` imports it, and
installing simnexus does not pull in Qt. Install the GUI extra with::

    pip install simnexus[gui]        # adds PySide6

The GUI is a thin reader on top of :mod:`simnexus.progress`. It never runs a
workflow itself; it only follows the ``status.json`` files a running workflow
writes into its results tree (see :class:`simnexus.progress.RunWatcher`). Point
it at the results root of a ``SimulationIterator`` or at any directory holding a
graph's ``status.json``.

Reusable pieces (import and drop into a larger Qt application):

* :class:`~simnexus_gui.progress_window.StatusView` -- renders one status dict
  (a graph's ``name``/``state`` plus a progress row per action). Feed it dicts
  from a :class:`~simnexus.progress.StatusWatcher`.
* :class:`~simnexus_gui.progress_window.RunProgressWidget` -- a self-contained
  ``QWidget`` that owns a ``QTimer``, polls a results tree, and displays the
  iterator's job counts plus the current job's actions. This is the drop-in
  window.

Standalone use::

    python -m simnexus_gui <results_dir>

The Qt imports are deferred to :mod:`simnexus_gui.progress_window`, so importing
this package without PySide6 raises a clear, actionable error only when you
actually reach for the widgets.
"""

__all__ = [ 'StatusView', 'RunProgressWidget', 'main' ]


def __getattr__( name ):
    # Lazy re-export so `import simnexus_gui` does not require PySide6 until a
    # widget is actually requested; then surface a helpful install hint.
    if name in __all__:
        try:
            from . import progress_window
        except ImportError as err:                       # pragma: no cover
            raise ImportError(
                'The simnexus GUI requires PySide6. Install it with '
                '"pip install simnexus[gui]" (or "pip install PySide6").'
            ) from err
        return getattr( progress_window, name )
    raise AttributeError( f'module {__name__!r} has no attribute {name!r}' )
