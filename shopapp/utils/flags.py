from __future__ import annotations

from dataclasses import dataclass

from ..models import FeatureFlag


@dataclass
class _FlagAccessor:
    def on(self, key: str) -> bool:
        flag = FeatureFlag.query.filter_by(key=key).first()
        return bool(flag and flag.enabled)


flags = _FlagAccessor()
