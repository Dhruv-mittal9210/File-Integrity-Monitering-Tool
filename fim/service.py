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


class FIMService(win32serviceutil.ServiceFramework):

    _svc_name_ = "FIM"
    _svc_display_name_ = "File Integrity Monitoring Service"
    _svc_description_ = "Monitors file integrity and detects unauthorized changes"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        servicemanager.LogInfoMsg("FIM Service stopping")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("FIM Service started")
        self.main()

    def main(self):
        while self.running:
            servicemanager.LogInfoMsg("FIM Service heartbeat")
            # wait up to 5 seconds, exit early if stop requested
            if win32event.WaitForSingleObject(self.stop_event, 5000) == win32event.WAIT_OBJECT_0:
                break


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(FIMService)
