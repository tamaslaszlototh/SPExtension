"""Shelf+ loader: the small, rarely changing part that lives in Painter's plugins folder.

It installs ``bundled/`` into ``%APPDATA%\\ShelfPlus\\versions\\<v>`` and starts the
highest good version from there (see ``_versions.py``). Everything else lives in
the versioned application package.
"""

import importlib
import logging
import logging.handlers
import os
import sys
from pathlib import Path

# Painter's "Reload plugins" re-executes this module but not its submodules.
# Drop them so the import below always picks up fresh code.
for _name in [n for n in sys.modules if n.startswith(__name__ + ".")]:
    del sys.modules[_name]
_versions = importlib.import_module(__name__ + "._versions")

LOG_FILE_NAME = "shelfplus.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3

_manager = None
_log_handler = None
_message_box = None


def data_dir():
    return Path(os.environ.get("APPDATA") or Path.home()) / "ShelfPlus"


def _setup_logging(directory):
    global _log_handler
    logs = directory / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        logs / LOG_FILE_NAME, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger = logging.getLogger("ShelfPlus")
    for stale in list(logger.handlers):  # left over if this module was re-executed
        logger.removeHandler(stale)
        stale.close()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    _log_handler = handler
    return logs / LOG_FILE_NAME


def _teardown_logging():
    global _log_handler
    if _log_handler is not None:
        logging.getLogger("ShelfPlus").removeHandler(_log_handler)
        _log_handler.close()
        _log_handler = None


def _show_message(text):
    """Non-blocking message box. The reference is kept so it is not collected."""
    global _message_box
    try:
        from PySide6 import QtWidgets

        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Shelf+", text)
        box.setModal(False)
        box.show()
        _message_box = box
    except Exception:
        logging.getLogger("ShelfPlus.loader").exception("Could not show message: %s", text)


def start_plugin():
    global _manager
    if _manager is not None:
        close_plugin()
    directory = data_dir()
    log_path = _setup_logging(directory)
    log = logging.getLogger("ShelfPlus.loader")
    log.info("Loader %s starting from %s", _versions.LOADER_VERSION, Path(__file__).parent)
    _manager = _versions.VersionManager(Path(__file__).parent, directory)
    result = _manager.start({"log_path": str(log_path)})
    if result.message:
        log.warning(result.message)
        _show_message(result.message)


def close_plugin():
    global _manager, _message_box
    if _manager is not None:
        _manager.stop()
        _manager = None
    if _message_box is not None:
        try:
            _message_box.close()
            _message_box.deleteLater()
        except Exception:
            pass
        _message_box = None
    logging.getLogger("ShelfPlus.loader").info("Loader stopped")
    _teardown_logging()
