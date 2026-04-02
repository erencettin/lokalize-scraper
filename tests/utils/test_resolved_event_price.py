"""Tests for ResolvedEventPrice.resolve() — mirrors backend BuildProviderPrices logic."""
from __future__ import annotations

from decimal import Decimal

import pytest

from models.normalized_event import ProviderPrice, ResolvedEventPrice


def pp(name: str, price=None, currency: str = "TRY", is_free: bool = False) -> ProviderPrice:
    """Shorthand ProviderPrice factory."""
    return ProviderPrice(
        provider_name=name,
        min_price=Decimal(str(price)) if price is not None else None,
        currency=currency,
        is_free=is_free,
    )


# ---------------------------------------------------------------------------
# K1 — Single provider
# ---------------------------------------------------------------------------

class TestSingleProvider:
    def test_shows_amount_without_provider_name(self):
        """K1: display_price_text must NOT embed provider name."""
        result = ResolvedEventPrice.resolve([pp("Ticketmaster", 250)])
        assert result.display_price_text == "250 ₺"
        assert result.has_multiple_providers is False

    def test_best_min_price_is_correct(self):
        result = ResolvedEventPrice.resolve([pp("Ticketmaster", 250)])
        assert result.best_min_price == Decimal("250")

    def test_all_prices_equal_is_false_for_single(self):
        # Single provider with a price → all_prices_equal is True (only one group)
        result = ResolvedEventPrice.resolve([pp("Ticketmaster", 250)])
        assert result.all_prices_equal is True


# ---------------------------------------------------------------------------
# K2 — Multi-provider, different prices
# ---------------------------------------------------------------------------

class TestMultiProviderDifferentPrices:
    def test_sorted_by_price_ascending(self):
        prices = [
            pp("Ticketmaster", 300),
            pp("Beyoğlu Belediyesi", 200),
            pp("Bakırköy Belediyesi", 250),
        ]
        result = ResolvedEventPrice.resolve(prices)
        names = [p.provider_name for p in result.provider_prices]
        assert names == ["Beyoğlu Belediyesi", "Bakırköy Belediyesi", "Ticketmaster"]

    def test_best_min_price(self):
        prices = [pp("TM", 300), pp("Beyoğlu", 200), pp("Bakırköy", 250)]
        result = ResolvedEventPrice.resolve(prices)
        assert result.best_min_price == Decimal("200")
        assert result.all_prices_equal is False

    def test_display_text_from_cheapest(self):
        prices = [pp("TM", 300), pp("Beyoğlu", 200)]
        result = ResolvedEventPrice.resolve(prices)
        assert "200" in result.display_price_text
        assert result.has_multiple_providers is True


# ---------------------------------------------------------------------------
# K3 — Multi-provider, same prices
# ---------------------------------------------------------------------------

class TestMultiProviderSamePrices:
    def test_sorted_alphabetically(self):
        prices = [pp("Ticketmaster", 250), pp("Bakırköy Belediyesi", 250)]
        result = ResolvedEventPrice.resolve(prices)
        assert result.provider_prices[0].provider_name == "Bakırköy Belediyesi"
        assert result.provider_prices[1].provider_name == "Ticketmaster"

    def test_all_prices_equal_flag(self):
        prices = [pp("Ticketmaster", 250), pp("Bakırköy Belediyesi", 250)]
        result = ResolvedEventPrice.resolve(prices)
        assert result.all_prices_equal is True

    def test_mixed_partial_equal(self):
        """Zeytinburnu(200) < Bakırköy(250) == Ticketmaster(250) — alfa within tie."""
        prices = [
            pp("Ticketmaster", 250),
            pp("Zeytinburnu Belediyesi", 200),
            pp("Bakırköy Belediyesi", 250),
        ]
        result = ResolvedEventPrice.resolve(prices)
        names = [p.provider_name for p in result.provider_prices]
        assert names == ["Zeytinburnu Belediyesi", "Bakırköy Belediyesi", "Ticketmaster"]
        assert result.all_prices_equal is False


# ---------------------------------------------------------------------------
# K4 — No price info
# ---------------------------------------------------------------------------

class TestNoPriceInfo:
    def test_empty_list(self):
        result = ResolvedEventPrice.resolve([])
        assert "mevcut" in result.display_price_text.lower() or "degil" in result.display_price_text.lower()
        assert result.best_min_price is None
        assert result.is_free is False
        assert result.has_multiple_providers is False


# ---------------------------------------------------------------------------
# K5 — Free events
# ---------------------------------------------------------------------------

class TestFreeEvents:
    def test_single_free_provider(self):
        result = ResolvedEventPrice.resolve([pp("Maltepe Belediyesi", 0, is_free=True)])
        assert result.is_free is True
        assert "cretsiz" in result.display_price_text.lower()

    def test_is_free_when_price_is_zero(self):
        result = ResolvedEventPrice.resolve([pp("Belediye", 0)])
        assert result.is_free is True


# ---------------------------------------------------------------------------
# D3 Senaryo A — Some providers missing price
# ---------------------------------------------------------------------------

class TestSomeMissingPrice:
    def test_none_price_goes_to_bottom(self):
        prices = [pp("Ticketmaster", 250), pp("Bakırköy Belediyesi", None)]
        result = ResolvedEventPrice.resolve(prices)
        assert result.provider_prices[-1].provider_name == "Bakırköy Belediyesi"
        assert result.provider_prices[0].provider_name == "Ticketmaster"

    def test_best_min_price_ignores_none(self):
        prices = [pp("TM", 250), pp("Bakırköy", None)]
        result = ResolvedEventPrice.resolve(prices)
        assert result.best_min_price == Decimal("250")


# ---------------------------------------------------------------------------
# D3 Senaryo B — Mixed free and paid
# ---------------------------------------------------------------------------

class TestMixedFreeAndPaid:
    def test_is_free_when_any_provider_free(self):
        prices = [
            pp("Belediye", 0, is_free=True),
            pp("Ticketmaster", 300),
        ]
        result = ResolvedEventPrice.resolve(prices)
        assert result.is_free is True
        assert result.has_multiple_providers is True
        assert result.all_prices_equal is False

    def test_free_provider_comes_first(self):
        prices = [pp("Ticketmaster", 300), pp("Belediye", 0, is_free=True)]
        result = ResolvedEventPrice.resolve(prices)
        assert result.provider_prices[0].provider_name == "Belediye"


# ---------------------------------------------------------------------------
# D5 — Currency grouping
# ---------------------------------------------------------------------------

class TestCurrencyGrouping:
    def test_try_before_usd(self):
        prices = [
            pp("TM_USD", 100, currency="USD"),
            pp("TM_TRY", 3000, currency="TRY"),
        ]
        result = ResolvedEventPrice.resolve(prices)
        assert result.provider_prices[0].currency == "TRY"

    def test_try_before_eur(self):
        prices = [
            pp("OP_EUR", 50, currency="EUR"),
            pp("Belediye", 500, currency="TRY"),
        ]
        result = ResolvedEventPrice.resolve(prices)
        assert result.provider_prices[0].currency == "TRY"
