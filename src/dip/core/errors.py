"""Shared exception hierarchy for DIP."""


class DIPError(Exception):
    """Base class for expected DIP failures."""


class ConfigurationError(DIPError):
    """Raised when application configuration is invalid."""


class ProviderError(DIPError):
    """Raised when an external data provider fails."""
