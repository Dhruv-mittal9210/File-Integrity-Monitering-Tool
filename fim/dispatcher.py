from __future__ import annotations

from fim.events import FileEvent


def dispatch_event(event: FileEvent) -> None:
    for handler in (_log_to_file, _log_to_event_viewer, _send_telegram_alert):
        try:
            handler(event)
        except Exception:
            pass


def _log_to_file(event: FileEvent) -> None:
    pass


def _log_to_event_viewer(event: FileEvent) -> None:
    pass


def _send_telegram_alert(event: FileEvent) -> None:
    pass
