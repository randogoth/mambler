from . import main


def run() -> int:
    """Entry point for `python -m mambler`."""
    return main()


if __name__ == "__main__":
    raise SystemExit(run())
