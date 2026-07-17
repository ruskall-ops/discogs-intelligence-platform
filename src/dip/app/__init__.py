"""Application bootstrap and use-case orchestration."""


def main() -> None:
    """Start the desktop application."""

    from dip.experience.desktop.app import App

    App().mainloop()


__all__ = ["main"]
