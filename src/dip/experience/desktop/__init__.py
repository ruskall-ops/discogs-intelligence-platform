"""Tkinter desktop experience with import-safe presentation models."""

from .dashboard_renderer import DesktopDashboardCard, DesktopDashboardRenderer

__all__ = ["App", "DesktopDashboardCard", "DesktopDashboardRenderer"]


def __getattr__(name: str):
    if name == "App":
        from .app import App

        return App
    raise AttributeError(name)
