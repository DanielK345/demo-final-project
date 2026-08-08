class BaseRepository:
    """Lightweight repository scaffold for future persistence work."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}
