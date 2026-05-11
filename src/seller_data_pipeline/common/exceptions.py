class SellerDataPipelineError(Exception):
    """Base application exception."""


class ConfigurationError(SellerDataPipelineError):
    """Raised when required configuration is missing or invalid."""


class ExternalServiceError(SellerDataPipelineError):
    """Raised when an external API call fails."""
