# simnexus_gui

An optional PySide6 GUI for watching **simnexus** workflow progress live.

It is a thin reader on top of [`simnexus.progress`](../simnexus/progress.py): it
never runs a workflow, it only follows the `status.json` files a running
workflow writes into its results tree. Because it lives outside the `simnexus`
package, **PySide6 stays an optional dependency** — installing simnexus does not
pull in Qt.

## Install

```bash
pip install simnexus[gui]      # simnexus + PySide6
# or, if simnexus is already installed:
pip install PySide6
```

## Run (standalone)

```bash
python -m simnexus_gui                     # opens a directory picker
python -m simnexus_gui path/to/results     # watches a results tree immediately
```

Point it at either:

* a **`SimulationIterator` results root** (the `{NAME}/` directory that holds
  `job_0/`, `job_1/`, …) — it shows the `job k of n` counter and follows the
  currently running job's actions; or
* **any directory holding a graph's `status.json`** (e.g. a `WorkArea` /
  `DirectedGraph` run directory) — it shows that graph's actions directly.

## Use as a drop-in window in your own Qt app

Two reusable widgets are exported:

```python
from simnexus_gui import RunProgressWidget, StatusView

# Self-contained: owns a QTimer + RunWatcher, just add it to a layout.
progress = RunProgressWidget("path/to/results")
progress.state_changed.connect(lambda state: print("run is", state))
some_layout.addWidget(progress)

progress.stop()      # pause polling (e.g. when hidden)
progress.start()     # resume
progress.set_results_root("other/results")   # watch a different run
```

* **`RunProgressWidget`** — the drop-in window. Give it a results directory and
  it polls that tree on a `QTimer` (default 500 ms) and keeps the display
  current. Emits `state_changed(str)` when the run's top-level state changes.
* **`StatusView`** — a passive renderer of a single status dict (name, state,
  a `no heartbeat` warning, and a progress row per action). It does no I/O and
  owns no timer; feed it dicts from a
  [`simnexus.progress.StatusWatcher`](../simnexus/progress.py) via
  `set_status(...)`. Use this if you want to manage polling yourself.

## How it fits together

```
workflow process              GUI process (this package)
─────────────────             ──────────────────────────
StatusReporter  ──►  status.json  ──►  RunWatcher.poll()  ──►  RunProgressWidget
(simnexus.progress)   (atomic)         (simnexus.progress)      └─ StatusView
```

The GUI follows exactly the reader-side contract documented in
`simnexus/progress.py`: `RunWatcher.poll()` is non-blocking and driven from the
Qt event loop, re-reading a file only when its `(mtime, inode, size)` signature
changes, so polling every few hundred milliseconds is cheap.
