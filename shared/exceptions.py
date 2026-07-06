class PlatformError(Exception):
    """Base exception for Engineer Department Platform."""


class ConfigurationError(PlatformError):
    """Raised when required configuration is missing or invalid."""


class ServiceError(PlatformError):
    """Raised when a service layer operation fails."""


class ExternalServiceError(ServiceError):
    """Raised when LINE, Google Sheet, OpenAI, Gmail, or another external service fails."""
