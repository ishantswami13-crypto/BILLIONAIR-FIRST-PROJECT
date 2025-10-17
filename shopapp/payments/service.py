from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from flask import current_app


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    display_name: str
    enabled: bool
    config: Dict[str, str]


class PaymentsService:
    """Facade for managing payment providers and intent lifecycle.

    Concrete gateway integrations will plug into this facade in future iterations.
    """

    def __init__(self, providers: Dict[str, ProviderConfig]) -> None:
        self._providers = providers

    def list_providers(self) -> List[Dict[str, str]]:
        return [
            {
                "name": cfg.name,
                "display_name": cfg.display_name,
                "enabled": cfg.enabled,
            }
            for cfg in self._providers.values()
        ]

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        return self._providers.get(name)


def _load_providers() -> Dict[str, ProviderConfig]:
    cfg = current_app.config
    providers: Dict[str, ProviderConfig] = {}

    razorpay_enabled = bool(cfg.get("RAZORPAY_KEY_ID") and cfg.get("RAZORPAY_KEY_SECRET"))
    providers["razorpay"] = ProviderConfig(
        name="razorpay",
        display_name="Razorpay",
        enabled=razorpay_enabled,
        config={
            "key_id": cfg.get("RAZORPAY_KEY_ID"),
            "key_secret": cfg.get("RAZORPAY_KEY_SECRET"),
        },
    )

    stripe_enabled = bool(cfg.get("STRIPE_SECRET_KEY"))
    providers["stripe"] = ProviderConfig(
        name="stripe",
        display_name="Stripe",
        enabled=stripe_enabled,
        config={
            "secret_key": cfg.get("STRIPE_SECRET_KEY"),
        },
    )

    cash_enabled = True
    providers["cash"] = ProviderConfig(
        name="cash",
        display_name="Cash",
        enabled=cash_enabled,
        config={},
    )

    return providers


def get_payments_service() -> PaymentsService:
    return PaymentsService(_load_providers())
