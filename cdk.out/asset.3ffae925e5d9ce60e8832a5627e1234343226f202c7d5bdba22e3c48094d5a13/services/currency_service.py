"""Currency conversion service using SSM Parameter Store for exchange rates."""

import logging
from decimal import ROUND_HALF_UP, Decimal

logger = logging.getLogger(__name__)


class CurrencyService:
    """Fetches USD-to-BRL exchange rate from SSM and converts amounts.

    Caches the rate for the lifetime of a single Lambda invocation.
    Falls back to a configurable default rate if SSM is unreachable.
    """

    FALLBACK_RATE = Decimal("5.05")
    SSM_PATH = "/costwatch/brl-exchange-rate"

    def __init__(self, ssm_client) -> None:
        self._ssm = ssm_client
        self._cached_rate: Decimal | None = None

    def get_exchange_rate(self) -> Decimal:
        """Return the USD-to-BRL exchange rate, fetching from SSM on first call.

        On failure, logs a warning and returns the fallback rate.
        """
        if self._cached_rate is not None:
            return self._cached_rate

        try:
            resp = self._ssm.get_parameter(Name=self.SSM_PATH, WithDecryption=True)
            self._cached_rate = Decimal(resp["Parameter"]["Value"])
        except Exception:
            logger.warning(
                "Failed to fetch exchange rate from SSM at %s — using fallback rate %s",
                self.SSM_PATH,
                self.FALLBACK_RATE,
            )
            self._cached_rate = self.FALLBACK_RATE

        return self._cached_rate

    @staticmethod
    def convert(amount_usd: Decimal, rate: Decimal) -> Decimal:
        """Convert USD to BRL, rounding to 4 decimal places with ROUND_HALF_UP."""
        return (amount_usd * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
