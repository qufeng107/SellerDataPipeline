class SellerDataPipelineError(Exception):
    """Base application exception."""


class ConfigurationError(SellerDataPipelineError):
    """Raised when required configuration is missing or invalid."""


class ExternalServiceError(SellerDataPipelineError):
    """Raised when an external API call fails."""


class AzureSqlConnectionError(SellerDataPipelineError):
    """Raised when Azure SQL cannot be opened after connection warm-up handling."""


class AzureSqlSchemaExportError(SellerDataPipelineError):
    """Raised when Azure SQL live schema export fails after connection succeeds."""
