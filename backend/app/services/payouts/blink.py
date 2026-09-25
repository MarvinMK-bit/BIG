"""Blink Lightning client: sends sats to a Lightning address.

Staging by default (see settings). The API key is held as a SecretStr and is only unwrapped to
build the request header; it is never logged, returned or put in an error message.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import httpx2 as httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

MAINNET_HOST = "api.blink.sv"
STAGING_HOST = "api.staging.blink.sv"
TIMEOUT_SECONDS = 30.0

PaymentStatus = Literal["success", "failed", "pending", "already_paid"]
Network = Literal["staging", "mainnet", "other"]

# lnAddressPaymentSend takes only amount, lnAddress and walletId (checked against Blink's public
# schema); there is no memo field, and sending one would fail validation.
MUTATION = """
mutation LnAddressPaymentSend($input: LnAddressPaymentSendInput!) {
  lnAddressPaymentSend(input: $input) {
    status
    errors { code message path }
    transaction { id }
  }
}
"""

_BLINK_STATUSES: dict[str, PaymentStatus] = {
    "SUCCESS": "success",
    "ALREADY_PAID": "already_paid",  # Blink saw this payment before: success, never an error
    "PENDING": "pending",
    "FAILURE": "failed",
}


@dataclass
class PaymentResult:
    status: PaymentStatus
    errors: list[str]
    raw: dict[str, Any]
    # Blink's PaymentSendResult, when it answered with one
    blink_status: str | None = None
    # Blink's transaction id, used as the reward's payment_ref
    transaction_id: str | None = None

    @property
    def paid(self) -> bool:
        return self.status in ("success", "already_paid")


def network_of(url: str) -> Network:
    host = (urlparse(url).hostname or "").lower()
    if host == MAINNET_HOST:
        return "mainnet"
    if host == STAGING_HOST:
        return "staging"
    return "other"


def config_problem(settings: Settings | None = None) -> str | None:
    """Why payouts can't be sent right now, or None if they can."""
    settings = settings or get_settings()
    if not settings.PAYOUTS_ENABLED:
        return "Payouts are disabled on this server (PAYOUTS_ENABLED is false)."
    if settings.BLINK_API_KEY is None or not settings.BLINK_API_KEY.get_secret_value():
        return "Payouts are not configured: BLINK_API_KEY is not set."
    if not settings.BLINK_WALLET_ID:
        return "Payouts are not configured: BLINK_WALLET_ID is not set."
    return None


def _error_messages(errors: Any) -> list[str]:
    if not isinstance(errors, list):
        return []
    out = []
    for e in errors:
        if isinstance(e, dict):
            code = e.get("code")
            message = str(e.get("message") or "Unknown error")
            out.append(f"{message} ({code})" if code else message)
    return out


async def send_to_lightning_address(
    address: str, amount_sats: int, memo: str | None = None
) -> PaymentResult:
    """Send amount_sats from the configured wallet to a Lightning address.

    `memo` is accepted for callers but not sent: lnAddressPaymentSend has no memo input.

    A result of "pending" means the outcome is unknown and the sats may still arrive. That covers
    Blink's PENDING and any failure after the request may have reached Blink (timeouts, 5xx,
    unreadable responses). "failed" is only used when the payment definitely did not go out.
    """
    settings = get_settings()
    problem = config_problem(settings)
    if problem:
        raise RuntimeError(problem)
    assert settings.BLINK_API_KEY is not None and settings.BLINK_WALLET_ID is not None

    payload = {
        "query": MUTATION,
        "variables": {
            "input": {
                "walletId": settings.BLINK_WALLET_ID,
                "lnAddress": address,
                "amount": amount_sats,
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": settings.BLINK_API_KEY.get_secret_value(),
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(settings.BLINK_API_URL, json=payload, headers=headers)
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        # Never connected, so nothing was sent
        logger.warning("Blink payment not sent: could not connect (%s)", type(exc).__name__)
        return PaymentResult("failed", [f"Could not connect to Blink ({type(exc).__name__})."], {})
    except httpx.TransportError as exc:
        logger.warning("Blink payment outcome unknown: %s", type(exc).__name__)
        return PaymentResult(
            "pending",
            [f"No answer from Blink ({type(exc).__name__}); the payment may have gone through."],
            {},
        )

    if response.status_code >= 500:
        logger.warning("Blink payment outcome unknown: HTTP %d", response.status_code)
        return PaymentResult(
            "pending",
            [f"Blink returned HTTP {response.status_code}; the payment may have gone through."],
            {},
        )

    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        if response.is_success:
            return PaymentResult(
                "pending", ["Blink's response could not be read; the payment may have gone through."], {}
            )
        return PaymentResult("failed", [f"Blink rejected the request (HTTP {response.status_code})."], {})

    result = (body.get("data") or {}).get("lnAddressPaymentSend")
    if not isinstance(result, dict):
        # Rejected before running (auth, validation): no payment was made
        errors = _error_messages(body.get("errors")) or [
            f"Blink rejected the request (HTTP {response.status_code})."
        ]
        logger.warning("Blink payment rejected before sending: HTTP %d", response.status_code)
        return PaymentResult("failed", errors, body)

    blink_status = result.get("status")
    errors = _error_messages(result.get("errors"))
    transaction = result.get("transaction")
    transaction_id = transaction.get("id") if isinstance(transaction, dict) else None

    if blink_status in _BLINK_STATUSES:
        status = _BLINK_STATUSES[blink_status]
    elif errors:
        status = "failed"
    else:
        status = "pending"
        errors = ["Blink gave no payment status; the payment may have gone through."]
    if status == "failed" and not errors:
        errors = ["Blink reported the payment as failed."]

    logger.info("Blink payment of %d sats: %s", amount_sats, blink_status or status)
    return PaymentResult(status, errors, body, blink_status=blink_status, transaction_id=transaction_id)
