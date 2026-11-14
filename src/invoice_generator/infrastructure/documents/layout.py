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
