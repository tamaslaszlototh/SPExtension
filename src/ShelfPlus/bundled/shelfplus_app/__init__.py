"""Shelf+ application package, started by the loader from ``versions/<v>/``.

Contract with the loader: ``start_plugin(env)`` and ``close_plugin()``. ``env`` holds
``version``, ``version_dir``, ``data_dir``, ``loader_version`` and ``log_path``.
An exception from ``start_plugin`` makes the loader mark this version bad.
"""

_app = None


def start_plugin(env):
    global _app
    from .adapter.network import QtHttp
    from .adapter.painter import PainterAdapter
    from .app import App
    from .ui.panel import QtPanelView

    app = App(env, PainterAdapter(), QtPanelView, network=QtHttp(f"ShelfPlus/{env['version']}"))
    _app = app
    app.start()


def close_plugin():
    global _app
    app, _app = _app, None
    if app is not None:
        app.close()
