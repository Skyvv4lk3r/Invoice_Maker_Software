from dataclasses import dataclass, field


@dataclass(frozen=True)
class InvoiceLayout:
    name: str = "My invoice layout"
    accent: str = "183C39"
    tint: str = "ECF4F0"
    font_family: str = "sans"
    font_size: int = 9
    margin_mm: int = 16
    header_alignment: str = "left"
    party_layout: str = "columns"
    row_spacing: int = 8
    footer_text: str = "Thank you for your business."
    show_notes: bool = True
    show_terms: bool = True
    show_signature: bool = True
    logo_png: str = field(default="", repr=False)
    columns: tuple[str, ...] = (
        "description",
        "quantity",
        "unit_price",
        "gst_rate",
        "taxable",
        "total",
    )
    section_order: tuple[str, ...] = ("parties", "metadata", "items", "totals", "notes", "terms")
