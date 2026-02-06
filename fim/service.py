"""
Windows Service wrapper for FIM.

Day 11 scope:
- Install / Start / Stop / Remove service
- No watch logic yet
- No baseline loading
- No Telegram
- No recovery logic

The service should:
- Start without crashing
- Run an idle loop (heartbeat)
- Stop gracefully when requested

Day 12 will integrate watch() inside this service.
"""

import win32serviceutil
import win32service
import win32event
import servicemanager
import time

from pathlib import Path
import threading

from .watch import watch
from .storage.json_store import load_json
from .utils import normalize_rel_path


class FIMService(win32serviceutil.ServiceFramework):

    _svc_name_ = "FIM"
    _svc_display_name_ = "File Integrity Monitoring Service"
    _svc_description_ = "Monitors file integrity and detects unauthorized changes"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.watch_thread = None

    def SvcStop(self):
        servicemanager.LogInfoMsg("FIM Service stopping")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.stop_event)


    def SvcDoRun(self):
        servicemanager.LogInfoMsg("FIM Service started")
        
        self.watch_thread = threading.Thread(
            target=self.run_watch,
            daemon=True
        )
        self.watch_thread.start()

        self.main()

    def main(self):
        while self.running:
            servicemanager.LogInfoMsg("FIM Service heartbeat")
            # wait up to 5 seconds, exit early if stop requested
            if win32event.WaitForSingleObject(self.stop_event, 5000) == win32event.WAIT_OBJECT_0:
                break
    
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
