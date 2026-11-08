from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from invoice_generator.domain.calculation import amount_in_words, calculate
from invoice_generator.domain.models import (
    DraftLine,
    TaxMode,
    ValidationError,
    financial_year_start,
)


@pytest.mark.parametrize(
    "mode,components", [(TaxMode.CGST_SGST, (1800, 1800, 0)), (TaxMode.IGST, (0, 0, 3600))]
)
def test_explicit_tax_split(mode, components):
    result = calculate((DraftLine("Goods", Decimal(2), Decimal(100), Decimal(18)),), mode)
    assert result.taxable_paise == 20000
    assert (result.cgst_paise, result.sgst_paise, result.igst_paise) == components
    assert result.total_paise == 23600
    assert result.amount_in_words == "Rupees Two Hundred Thirty Six Only"


def test_rounding_reconciles_from_displayed_components():
    result = calculate(
        (DraftLine("Small amount", Decimal(1), Decimal("0.06"), Decimal(18)),), TaxMode.CGST_SGST
    )
    assert result.cgst_paise == result.sgst_paise == 1
    assert result.total_paise == 8
    assert (
        result.total_paise
        == result.taxable_paise + result.cgst_paise + result.sgst_paise + result.igst_paise
    )


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "1000001"])
def test_invalid_quantities_are_rejected(bad):
    with pytest.raises(ValidationError):
        calculate((DraftLine("Goods", Decimal(bad), Decimal(100), Decimal(18)),), TaxMode.IGST)


@pytest.mark.parametrize(
    "paise,expected",
    [
        (0, "Rupees Zero Only"),
        (101, "Rupees One and One Paise Only"),
        (
            12345678,
            "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six "
            "and Seventy Eight Paise Only",
        ),
        (1000000000, "Rupees One Crore Only"),
    ],
)
def test_indian_amount_words(paise, expected):
    assert amount_in_words(paise) == expected


def test_financial_year_boundary_is_based_on_invoice_date():
    assert financial_year_start(date(2026, 3, 31)) == 2025
    assert financial_year_start(date(2026, 4, 1)) == 2026


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e20", "1.12345", "-2", ""])
def test_public_boundary_rejects_invalid_decimals(backend, sample, value):
    bad = replace(sample, lines=(replace(sample.lines[0], unit_price=value),))
    result = backend.queries.calculate(bad)
    assert result.error.code == "VALIDATION"
    assert result.error.field == "lines.1.unit_price"
