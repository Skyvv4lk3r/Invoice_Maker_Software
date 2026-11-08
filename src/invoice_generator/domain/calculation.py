"""Draft arithmetic for an explicitly chosen split/rate, not GST classification."""

from decimal import Decimal

from invoice_generator.domain.models import (
    MAX_PAISE,
    DraftLine,
    InvoiceTotals,
    LineTotals,
    TaxMode,
    ValidationError,
    paise,
)

ONES = (
    "Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen "
    "Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen"
).split()
TENS = "Zero Ten Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _words(value: int) -> str:
    if value < 20:
        return ONES[value]
    if value < 100:
        return TENS[value // 10] + (" " + _words(value % 10) if value % 10 else "")
    for divisor, label in [
        (10_000_000, "Crore"),
        (100_000, "Lakh"),
        (1000, "Thousand"),
        (100, "Hundred"),
    ]:
        if value >= divisor:
            tail = " " + _words(value % divisor) if value % divisor else ""
            return f"{_words(value // divisor)} {label}{tail}"
    raise ValueError("Unsupported value")


def amount_in_words(total_paise: int) -> str:
    if not 0 <= total_paise <= MAX_PAISE:
        raise ValidationError("amount", "Amount is outside the supported draft range.")
    rupees, remainder = divmod(total_paise, 100)
    words = f"Rupees {_words(rupees)}"
    if remainder:
        words += f" and {_words(remainder)} Paise"
    return words + " Only"


def calculate(lines: tuple[DraftLine, ...], mode: TaxMode) -> InvoiceTotals:
    if not 1 <= len(lines) <= 200:
        raise ValidationError("lines", "Add between 1 and 200 items.")
    if not isinstance(mode, TaxMode):
        raise ValidationError("tax_mode", "Select an explicit tax split.")
    results = []
    for index, line in enumerate(lines, 1):
        if not line.description.strip() or len(line.description) > 500:
            raise ValidationError(f"lines.{index}.description", "Use 1 to 500 characters.")
        for key, value, lower, upper in [
            ("quantity", line.quantity, Decimal("0.0001"), Decimal("1000000")),
            ("unit_price", line.unit_price, Decimal(0), Decimal("999999999.99")),
            ("gst_rate", line.gst_rate, Decimal(0), Decimal(100)),
        ]:
            if not value.is_finite() or not lower <= value <= upper:
                raise ValidationError(
                    f"lines.{index}.{key}", f"{key} is outside its supported range."
                )
        base = paise(line.quantity * line.unit_price)
        taxable = Decimal(base) / 100
        cgst = sgst = igst = 0
        if mode == TaxMode.CGST_SGST:
            cgst = sgst = paise(taxable * line.gst_rate / 200)
        else:
            igst = paise(taxable * line.gst_rate / 100)
        results.append(LineTotals(base, cgst, sgst, igst, base + cgst + sgst + igst))
    total = sum(row.total_paise for row in results)
    if total > MAX_PAISE:
        raise ValidationError("amount", "Draft total exceeds the supported amount.")
    return InvoiceTotals(
        tuple(results),
        sum(row.taxable_paise for row in results),
        sum(row.cgst_paise for row in results),
        sum(row.sgst_paise for row in results),
        sum(row.igst_paise for row in results),
        total,
        amount_in_words(total),
    )
