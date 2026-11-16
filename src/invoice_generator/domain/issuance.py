"""Validation for the deliberately narrow domestic, ordinary taxable supply workflow."""

from datetime import date

from invoice_generator.domain.models import DraftInvoice, TaxMode, ValidationError

STATES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}
UTGST = {"04", "26", "31", "35", "38"}


def state_code(raw):
    text = raw.strip()
    if text[:2] in STATES and (len(text) == 2 or not text[2].isdigit()):
        return text[:2]
    for key, name in STATES.items():
        if text.casefold() == name.casefold():
            return key
    raise ValidationError(
        "state", "Enter a supported Indian state name or two-digit GST state code."
    )


def check_gstin(gstin):
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(gstin) != 15 or any(ch not in alphabet for ch in gstin):
        return False
    factor, total = 2, 0
    for char in reversed(gstin[:-1]):
        product = alphabet.index(char) * factor
        total += product // 36 + product % 36
        factor = 1 if factor == 2 else 2
    return alphabet[(36 - total % 36) % 36] == gstin[-1]


def validate_issuance(
    draft: DraftInvoice, firm_name, firm_gstin, signatory, shipping_address, today=None
):
    today = today or date.today()
    if draft.invoice_date > today:
        raise ValidationError("invoice_date", "Cannot issue an invoice dated in the future.")
    if (
        not draft.firm_details.address
        or not draft.customer_details.address
        or not shipping_address.strip()
    ):
        raise ValidationError("address", "Complete the supplier, customer and delivery addresses.")
    if draft.firm_name != firm_name or draft.firm_details.gstin != firm_gstin:
        raise ValidationError("firm", "The draft must match your saved firm name and GSTIN.")
    if not check_gstin(firm_gstin):
        raise ValidationError("firm.gstin", "Enter a GSTIN with a valid checksum in Firm settings.")
    origin, destination = state_code(draft.firm_details.state), state_code(draft.place_of_supply)
    if firm_gstin[:2] != origin:
        raise ValidationError("firm.state", "Supplier state must match the GSTIN state code.")
    recipient_state = state_code(draft.customer_details.state)
    customer_gstin = draft.customer_details.gstin
    if customer_gstin and (
        not check_gstin(customer_gstin) or customer_gstin[:2] != recipient_state
    ):
        raise ValidationError("customer.gstin", "Check the customer's GSTIN checksum and state.")
    if origin == destination and origin in UTGST:
        raise ValidationError("tax_mode", "Intraterritory UTGST invoices are not supported yet.")
    expected = TaxMode.CGST_SGST if origin == destination else TaxMode.IGST
    if draft.tax_mode != expected:
        raise ValidationError(
            "tax_mode", f"Supplier state and place of supply require {expected.value}."
        )
    if not signatory.strip():
        raise ValidationError("signatory", "Set an authorised signatory in Firm settings.")
    for index, line in enumerate(draft.lines, 1):
        if not line.hsn_sac or not line.unit or line.gst_rate <= 0:
            raise ValidationError(
                f"line.{index}",
                (
                    "Issued taxable invoices require HSN/SAC, units and a positive "
                    "tax rate. Exempt and nil-rated supplies are not supported."
                ),
            )
        if line.item_type == "SERVICES" and (
            len(line.hsn_sac) != 6 or not line.hsn_sac.startswith("99")
        ):
            raise ValidationError(
                f"line.{index}.hsn_sac", "Use the six-digit SAC beginning with 99 for services."
            )
        if line.item_type == "GOODS" and len(line.hsn_sac) not in (4, 6, 8):
            raise ValidationError(
                f"line.{index}.hsn_sac", "Use a four, six or eight-digit HSN for goods."
            )
