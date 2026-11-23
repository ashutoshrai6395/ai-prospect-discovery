class ProviderFailure(Exception):
    """A configured provider failed to return usable data."""


class MissingConfiguration(Exception):
    """A required discovery or language provider is unavailable."""


class RequestLimit(Exception):
    """The process-wide discovery request budget has been reached."""
