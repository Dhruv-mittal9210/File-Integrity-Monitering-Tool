# fim/__main__.py
import logging
from . import cli

def _setup_logging():
    # Minimal default logging for local dev and CLI visibility.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

def main():
    _setup_logging()
    cli.main()

if __name__ == "__main__":
    main()
