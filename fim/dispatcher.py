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
    try:
        from win32evtlog import (
            EVENTLOG_ERROR_TYPE,
            EVENTLOG_INFORMATION_TYPE,
            EVENTLOG_WARNING_TYPE,
        )
        from win32evtlogutil import ReportEvent

        if event.event_type == "CREATED":
            event_type = EVENTLOG_INFORMATION_TYPE
        elif event.event_type == "MODIFIED":
            event_type = EVENTLOG_WARNING_TYPE
        elif event.event_type == "DELETED":
            event_type = EVENTLOG_ERROR_TYPE
        else:
            event_type = EVENTLOG_INFORMATION_TYPE

        parts = [
            f"Event type: {event.event_type}",
            f"Path: {event.path}",
            f"Timestamp: {event.timestamp}",
        ]
        if event.hash_before is not None:
            parts.append(f"Hash before: {event.hash_before}")
        if event.hash_after is not None:
            parts.append(f"Hash after: {event.hash_after}")
        message = "\n".join(parts)

        ReportEvent(
            "FIM",
            0,
            eventCategory=0,
            eventType=event_type,
            strings=[message],
        )
    except Exception:
        pass


def _send_telegram_alert(event: FileEvent) -> None:
    pass
