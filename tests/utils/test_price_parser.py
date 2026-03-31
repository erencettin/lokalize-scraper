from utils.price_parser import PriceParser


def test_parse_prices_single_value() -> None:
    min_price, max_price = PriceParser.parse_prices("500 TRY")
    assert min_price == 500.0
    assert max_price == 500.0


def test_parse_prices_range_with_thousand_and_decimal() -> None:
    min_price, max_price = PriceParser.parse_prices("1.200,50 TL - 2.450,75 TL")
    assert min_price == 1200.5
    assert max_price == 2450.75


def test_parse_prices_does_not_mark_free_for_non_zero_values() -> None:
    min_price, max_price = PriceParser.parse_prices("500")
    assert min_price == 500.0
    assert max_price == 500.0


def test_resolve_text_price_marks_free() -> None:
    price = PriceParser.resolve_text_price(
        price_text="Etkinlik Ucretsiz",
        currency="TRY",
        source="unit_test",
        legal_mode="public_web_text",
        strategy="text_scan",
        confidence=0.7,
        is_authoritative=False,
        is_derived=True,
    )
    assert price.is_free is True
    assert price.is_unknown is False
    assert price.min_value == 0.0
    assert price.max_value == 0.0


def test_resolve_text_price_unknown_marker() -> None:
    price = PriceParser.resolve_text_price(
        price_text="Fiyat bilgisi yok",
        currency="TRY",
        source="unit_test",
        legal_mode="public_web_text",
        strategy="text_scan",
        confidence=0.7,
        is_authoritative=False,
        is_derived=True,
    )
    assert price.is_unknown is True
    assert price.min_value is None
    assert price.max_value is None
