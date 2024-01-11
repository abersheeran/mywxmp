import httpx


class GenerateClientError(Exception):
    """
    Generate error
    """


class GenerateNetworkError(GenerateClientError):
    """
    Request network error
    """


class GenerateResponseError(GenerateClientError):
    """
    Response error
    """

    def __init__(self, message: str, response: httpx.Response) -> None:
        self.message = message
        self.response = response
        super().__init__(f"{response.status_code} {response.text}")


class GenerateSafeError(GenerateClientError):
    """
    Safe error
    """

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        super().__init__(f"{response.status_code} {response.text}")
