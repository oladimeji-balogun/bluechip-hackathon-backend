import json
from pathlib import Path
from src.schemas.user_profile import UserProfile


class ProfileStore:
    _store: dict[str, dict] = {}

    @classmethod
    async def load(cls, path: str) -> None:
        p = Path(path)
        if not p.exists():
            print(f"WARNING: Profile store not found at {path}. Starting empty.")
            return
        with open(p) as f:
            cls._store = json.load(f)
        print(f"Loaded {len(cls._store)} profiles.")

    @classmethod
    def get(cls, user_id: str) -> UserProfile | None:
        data = cls._store.get(user_id)
        if data is None:
            return None
        return UserProfile(**data)

    @classmethod
    def count(cls) -> int:
        return len(cls._store)