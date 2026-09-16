"""Application-specific exceptions."""


class OverseerError(Exception):
    """Base error for expected OVERSEER failures."""


class SourcePolicyError(OverseerError):
    """The live source policy does not permit safe acquisition."""


class SourceResponseError(OverseerError):
    """The source returned an invalid or unsafe response."""


class RecordNotFoundError(OverseerError):
    """No local record matched the requested identifier."""

