
from dspy.signatures.signature import Signature


class AdapterParseError(Exception):
    """Exception raised when adapter cannot parse the LM response."""

    def __init__(
        self,
        adapter_name: str,
        signature: Signature,
        lm_response: str,
        message: str | None = None,
        parsed_result: str | None = None,
    ):
        self.adapter_name = adapter_name
        self.signature = signature
        self.lm_response = lm_response
        self.parsed_result = parsed_result

        message = f"{message}\n\n" if message else ""
        message = (
            f"{message}"
            f"Adapter {adapter_name} failed to parse the LM response. \n\n"
            f"LM Response: {lm_response} \n\n"
            f"Expected to find output fields in the LM response: [{', '.join(signature.output_fields.keys())}] \n\n"
        )

        if parsed_result is not None:
            message += f"Actual output fields parsed from the LM response: [{', '.join(parsed_result.keys())}] \n\n"

        super().__init__(message)


class CacheError(Exception):
    """Exception raised when cache operations fail."""

    pass


class CacheKeyGenerationError(CacheError):
    """Exception raised when cache key generation fails."""

    def __init__(self, request: dict, original_error: Exception):
        self.request = request
        self.original_error = original_error
        message = f"Failed to generate cache key for request. Error: {type(original_error).__name__}: {original_error}"
        super().__init__(message)


class CachePutError(CacheError):
    """Exception raised when putting a value into the cache fails."""

    def __init__(self, value, original_error: Exception):
        self.value = value
        self.original_error = original_error
        message = f"Failed to store value in cache. Error: {type(original_error).__name__}: {original_error}"
        super().__init__(message)
