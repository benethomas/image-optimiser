"""Background sweeper that deletes stale optimized files.

Files are named with a UUID token and served for a short window after which
they are useless. A daemon thread removes anything older than FILE_TTL_SECONDS
so the temp folder never grows unbounded.
"""
import os
import threading
import time
from pathlib import Path


def start_cleanup(app):
    # Under Flask's debug reloader the module is imported twice; only the
    # child process (WERKZEUG_RUN_MAIN=true) should run the sweeper. Outside
    # the reloader the var is unset and we start normally.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    temp_dir = Path(app.config["UPLOAD_FOLDER"])
    ttl = app.config["FILE_TTL_SECONDS"]
    interval = app.config["CLEANUP_INTERVAL_SECONDS"]

    def sweep():
        while True:
            cutoff = time.time() - ttl
            for path in temp_dir.glob("*"):
                try:
                    if path.is_file() and path.stat().st_mtime < cutoff:
                        path.unlink()
                except OSError:
                    # File vanished or is locked; ignore and retry next pass.
                    pass
            time.sleep(interval)

    thread = threading.Thread(target=sweep, name="temp-cleanup", daemon=True)
    thread.start()
