"""Document appearance only; deliberately independent of Qt application styling."""

from invoice_generator.application.contracts.dto import PartyDetails


def money(paise: int) -> str:
    rupees, remainder = divmod(paise, 100)
    digits = str(rupees)
    tail = digits[-3:]
    prefix = digits[:-3]
    groups = []
    while prefix:
        groups.insert(0, prefix[-2:])
        prefix = prefix[:-2]
    grouped = ",".join([*groups, tail])
    return f"{grouped}.{remainder:02d}"


def party_lines(name: str, details: PartyDetails) -> list[str]:
    lines = [name]
    if details.address:
        lines.append(details.address)
    if details.state:
        lines.append(details.state)
    if details.gstin:
        lines.append("GSTIN: " + details.gstin)
    if details.email or details.phone:
        lines.append(" | ".join(value for value in (details.email, details.phone) if value))
    return lines


def palette(template_id: str) -> tuple[str, str]:
    return ("183C39", "ECF4F0") if template_id == "modern" else ("303C4B", "F0F1F3")


def effective_layout(model):
    from invoice_generator.application.contracts.layout import InvoiceLayout

    if model.layout is not None:
        return model.layout
    ink, tint = palette(model.template_id)
    return InvoiceLayout(accent=ink, tint=tint)


COLUMN_TITLES = {
    "description": "ITEM / HSN-SAC",
    "quantity": "QTY / UNIT",
    "unit_price": "RATE (INR)",
    "gst_rate": "GST %",
    "taxable": "TAXABLE",
    "total": "TOTAL",
}
COLUMN_WEIGHTS = {
    "description": 56,
    "quantity": 25,
    "unit_price": 26,
    "gst_rate": 16,
    "taxable": 27,
    "total": 28,
}


def line_values(line):
    description = line.description
    if line.hsn_sac:
        description += f"\n{line.item_type.title()} • {line.hsn_sac}"
    return {
        "description": description,
        "quantity": f"{line.quantity} {line.unit}",
        "unit_price": line.unit_price,
        "gst_rate": line.gst_rate,
        "taxable": money(line.taxable_paise),
        "total": money(line.total_paise),
    }
