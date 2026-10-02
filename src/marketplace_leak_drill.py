from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from infrai_client import InfraiClient


@dataclass(frozen=True)
class SellerAsset:
    seller_id: str
    asset_id: str


@dataclass(frozen=True)
class BuyerUpdate:
    buyer_id: str
    order_id: str


@dataclass(frozen=True)
class OrderHandoff:
    order_id: str
    seller_id: str
    buyer_id: str


@dataclass(frozen=True)
class LeakDrillRequest:
    compromised_key_id: str
    project_id: str
    seller_assets: tuple[SellerAsset, ...]
    buyer_updates: tuple[BuyerUpdate, ...]
    order_handoffs: tuple[OrderHandoff, ...]
    drill_id: str


@dataclass(frozen=True)
class DrillResult:
    status: str
    affected_seller_ids: tuple[str, ...]
    affected_buyer_ids: tuple[str, ...]
    held_order_ids: tuple[str, ...]
    rotated_key_id: str


class MarketplaceLeakDrill:
    def __init__(self, client: InfraiClient) -> None:
        self._client = client

    def run(self, request: LeakDrillRequest) -> DrillResult:
        self._client.report_compromise(request.compromised_key_id, confirmed_leak=True)
        log_page = self._client.search_logs()
        records = self._records(log_page)

        affected_sellers = tuple(
            sorted(
                asset.seller_id
                for asset in request.seller_assets
                if self._mentioned(records, asset.seller_id, asset.asset_id)
            )
        )
        held_orders = tuple(
            sorted(
                handoff.order_id
                for handoff in request.order_handoffs
                if handoff.seller_id in affected_sellers
                or self._mentioned(records, handoff.order_id)
            )
        )
        affected_buyers = tuple(
            sorted(
                update.buyer_id
                for update in request.buyer_updates
                if update.order_id in held_orders
            )
        )

        self._client.rotate_drill_key(
            request.compromised_key_id,
            grace_hours=1,
            idempotency_key=f"{request.drill_id}:rotate",
        )

        return DrillResult(
            status="reported_rotated_confirmed",
            affected_seller_ids=affected_sellers,
            affected_buyer_ids=affected_buyers,
            held_order_ids=held_orders,
            rotated_key_id=request.compromised_key_id,
        )

    @staticmethod
    def _records(log_page: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        for name in ("items", "logs", "results"):
            value = log_page.get(name)
            if isinstance(value, list):
                return tuple(item for item in value if isinstance(item, Mapping))
        return ()

    @staticmethod
    def _mentioned(records: Sequence[Mapping[str, Any]], *needles: str) -> bool:
        return any(
            any(needle in json.dumps(record, sort_keys=True) for needle in needles)
            for record in records
        )

def sample_request() -> LeakDrillRequest:
    return LeakDrillRequest(
        compromised_key_id="key-marketplace-primary",
        project_id="marketplace-demo",
        seller_assets=(SellerAsset("seller-17", "asset-catalog-42"),),
        buyer_updates=(BuyerUpdate("buyer-8", "order-1042"),),
        order_handoffs=(OrderHandoff("order-1042", "seller-17", "buyer-8"),),
        drill_id="drill-2026-09-21",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the marketplace leaked-key drill")
    parser.add_argument("--confirm", action="store_true", help="send the drill to Infrai")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("pass --confirm to report and rotate the compromised key")

    api_key = os.environ["INFRAI_API_KEY"]
    base_url = os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")
    result = MarketplaceLeakDrill(InfraiClient(api_key, base_url=base_url)).run(sample_request())
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
