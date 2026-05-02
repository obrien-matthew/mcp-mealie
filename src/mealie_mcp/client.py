"""Client wrapper for the Mealie API."""


class MealieError(Exception):
    """Mealie API error."""


class MealieClient:
    """Validated, formatted interface to the Mealie API."""

    def __init__(self) -> None:
        pass

    def ping(self) -> str:
        """Placeholder method to verify the client works."""
        return "pong"
