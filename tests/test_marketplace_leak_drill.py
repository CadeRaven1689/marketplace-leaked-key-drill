from typing import Any, Mapping

from marketplace_leak_drill import MarketplaceLeakDrill, sample_request


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def report_compromise(self, key_id: str, *, confirmed_leak: bool) -> Mapping[str, Any]:
        self.calls.append(("report", {"key_id": key_id, "confirmed_leak": confirmed_leak}))
        return {"accepted": True}

    def search_logs(self) -> Mapping[str, Any]:
        self.calls.append(("search", {}))
        return {
            "items": [
                {"seller_id": "seller-17", "asset_id": "asset-catalog-42"},
                {"order_id": "order-unrelated"},
            ]
        }

    def rotate_drill_key(
        self, key_id: str, *, grace_hours: int, idempotency_key: str
    ) -> Mapping[str, Any]:
        self.calls.append(
            (
                "rotate",
                {
                    "key_id": key_id,
                    "grace_hours": grace_hours,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        return {"id": key_id}


def test_affected_seller_holds_order_and_selects_buyer_update() -> None:
    client = RecordingClient()

    result = MarketplaceLeakDrill(client).run(sample_request())  # type: ignore[arg-type]

    assert result.status == "reported_rotated_confirmed"
    assert result.affected_seller_ids == ("seller-17",)
    assert result.held_order_ids == ("order-1042",)
    assert result.affected_buyer_ids == ("buyer-8",)
    assert result.rotated_key_id == "key-marketplace-primary"
    assert [name for name, _ in client.calls] == ["report", "search", "rotate"]
    assert client.calls[-1][1] == {
        "key_id": "key-marketplace-primary",
        "grace_hours": 1,
        "idempotency_key": "drill-2026-09-21:rotate",
    }
