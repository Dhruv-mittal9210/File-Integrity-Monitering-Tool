import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import win32serviceutil
import win32service
import win32event
import servicemanager
import time

import threading

from fim.watch import watch
from fim.storage.json_store import load_json
from fim.utils import normalize_rel_path


class FIMService(win32serviceutil.ServiceFramework):

    _svc_name_ = "FIM"
    _svc_display_name_ = "File Integrity Monitoring Service"
    _svc_description_ = "Monitors file integrity and detects unauthorized changes"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.watch_thread = None
        self.supervisor_thread = None
        self.shutdown_event = threading.Event()
        self.watch_lock = threading.Lock()
        self.watch_last_error = None
        self.restart_backoff_seconds = 2

    def SvcStop(self):
        servicemanager.LogInfoMsg("FIM Service stopping")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        self.shutdown_event.set()
        win32event.SetEvent(self.stop_event)


    def SvcDoRun(self):
        servicemanager.LogInfoMsg("FIM Service started")
        
        self.start_watch_thread()

        self.supervisor_thread = threading.Thread(
            target=self.supervise_watch,
            daemon=True
        )
        self.supervisor_thread.start()

        self.main()

    def main(self):
        while self.running:
            servicemanager.LogInfoMsg("FIM Service heartbeat")
            # wait up to 5 seconds, exit early if stop requested
            if win32event.WaitForSingleObject(self.stop_event, 5000) == win32event.WAIT_OBJECT_0:
                break

        self.shutdown_event.set()
        self.join_threads()
        servicemanager.LogInfoMsg("FIM Service stopped cleanly")

    def start_watch_thread(self):
        with self.watch_lock:
            self.watch_last_error = None
            self.watch_thread = threading.Thread(
                target=self.run_watch_guarded,
                daemon=True
            )
            self.watch_thread.start()
            servicemanager.LogInfoMsg("Watch thread started")

    def supervise_watch(self):
        while not self.shutdown_event.is_set():
            time.sleep(1)
            if self.shutdown_event.is_set():
                break

            if self.watch_thread is None:
                continue

            if not self.watch_thread.is_alive() and not self.shutdown_event.is_set():
                error_msg = "Watch thread exited unexpectedly"
                if self.watch_last_error:
                    error_msg = f"{error_msg}: {self.watch_last_error}"
                servicemanager.LogErrorMsg(error_msg)

                servicemanager.LogInfoMsg(
                    f"Restarting watch thread after {self.restart_backoff_seconds}s backoff"
                )
                time.sleep(self.restart_backoff_seconds)

                if self.shutdown_event.is_set():
                    break

                self.start_watch_thread()

        servicemanager.LogInfoMsg("Supervisor thread exiting")

    def join_threads(self):
        if self.supervisor_thread is not None:
            self.supervisor_thread.join(timeout=5)
            if self.supervisor_thread.is_alive():
                servicemanager.LogErrorMsg("Supervisor thread did not exit in time")
            else:
                servicemanager.LogInfoMsg("Supervisor thread stopped")

        if self.watch_thread is not None:
            self.watch_thread.join(timeout=5)
            if self.watch_thread.is_alive():
                servicemanager.LogErrorMsg("Watch thread did not exit in time")
            else:
                servicemanager.LogInfoMsg("Watch thread stopped")

    def run_watch_guarded(self):
        try:
            self.run_watch()
        except Exception as exc:
            self.watch_last_error = repr(exc)
            servicemanager.LogErrorMsg(f"Watch thread crashed: {self.watch_last_error}")

    def run_watch(self):
        """
        Load baseline and start watch() loop.
        Runs in a background thread.
        """

        baseline_path = Path("baseline.json")
        baseline = load_json(baseline_path)

        if baseline is None:
            servicemanager.LogErrorMsg("Baseline not found. Service cannot start watch mode.")
            return

        baseline_files_raw = baseline.get("files", {})
        baseline_files = {
            normalize_rel_path(k): v for k, v in baseline_files_raw.items()
        }

        target = Path(baseline.get("target", ".")).resolve()

        servicemanager.LogInfoMsg(f"Starting watch on {target}")
        servicemanager.LogInfoMsg("Watch thread started successfully")

        watch(target, baseline_files, exclude=None, log_path=None)



if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(FIMService)
