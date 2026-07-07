import xml.etree.ElementTree as ET
import re
from decimal import Decimal, ROUND_HALF_UP

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}

def redondear(valor):
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def extraer_xml_interno(xml_string):
    root = ET.fromstring(xml_string.strip().lstrip("\ufeff"))

    desc = root.find(".//cac:Attachment/cac:ExternalReference/cbc:Description", NS)

    if desc is not None and desc.text:
        xml_limpio = desc.text.strip().lstrip("\ufeff")

        interno_root = ET.fromstring(xml_limpio)

        responses = interno_root.findall(".//{*}ResponseCode")
        for r in responses:
            if r.text in ["FAK57", "FAK58"]:
                return interno_root, root, f"Error DIAN detectado: {r.text}"

        return interno_root, root, None

    return root, root, None

def extraer_valor(root, paths):
    for path in paths:
        el = root.find(path, NS)
        if el is not None and el.text:
            try:
                return Decimal(el.text)
            except Exception:
                continue
    return Decimal("0.00")

def extraer_iva_real(invoice_root):
    iva = Decimal("0.00")

    for tax_total in invoice_root.findall(".//cac:TaxTotal", NS):
        tax_amount = tax_total.find("cbc:TaxAmount", NS)
        if tax_amount is not None and tax_amount.text:
            iva += Decimal(tax_amount.text)

    return redondear(iva)

def extraer_bases_por_tarifa(invoice_root):
    bases = {}

    for tax_subtotal in invoice_root.findall(".//cac:TaxSubtotal", NS):
        taxable_el = tax_subtotal.find("cbc:TaxableAmount", NS)
        percent_el = tax_subtotal.find(".//cac:TaxCategory/cbc:Percent", NS)

        if taxable_el is None or not taxable_el.text:
            continue

        base = Decimal(taxable_el.text)

        if percent_el is not None and percent_el.text:
            tarifa = str(int(Decimal(percent_el.text)))
        else:
            tarifa = "0"

        if tarifa not in bases:
            bases[tarifa] = Decimal("0.00")

        bases[tarifa] += base

    for tarifa in list(bases.keys()):
        bases[tarifa] = redondear(bases[tarifa])

    return bases

def extraer_totales(invoice_root):
    line_extension = extraer_valor(invoice_root, [
        ".//cac:LegalMonetaryTotal/cbc:LineExtensionAmount"
    ])

    tax_exclusive = extraer_valor(invoice_root, [
        ".//cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount"
    ])

    tax_inclusive = extraer_valor(invoice_root, [
        ".//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount"
    ])

    payable = extraer_valor(invoice_root, [
        ".//cac:LegalMonetaryTotal/cbc:PayableAmount"
    ])

    anticipo = extraer_valor(invoice_root, [
        ".//cac:LegalMonetaryTotal/cbc:PrepaidAmount"
    ])

    iva = extraer_iva_real(invoice_root)

    return {
        "line_extension": float(redondear(line_extension)),
        "tax_exclusive": float(redondear(tax_exclusive)),
        "tax_inclusive": float(redondear(tax_inclusive)),
        "iva": float(redondear(iva)),
        "total_xml": float(redondear(payable)),
        "anticipo": float(redondear(anticipo)),
    }

def ajustar_base_cero(invoice_root, bases):
    line_extension = extraer_valor(invoice_root, [
        ".//cac:LegalMonetaryTotal/cbc:LineExtensionAmount"
    ])

    suma_bases = sum(bases.values(), Decimal("0.00"))

    diferencia = redondear(line_extension - suma_bases)

    if diferencia > 0:
        if "0" not in bases:
            bases["0"] = Decimal("0.00")
        bases["0"] = redondear(bases["0"] + diferencia)

    return bases

def parsear_factura_xml(xml_string):
    invoice_root, _, error_dian = extraer_xml_interno(xml_string)

    if error_dian:
        return {"error": error_dian}

    totales = extraer_totales(invoice_root)
    bases = extraer_bases_por_tarifa(invoice_root)
    bases = ajustar_base_cero(invoice_root, bases)

    def get_txt(path, default=""):
        node = invoice_root.find(path, NS)
        return node.text.strip() if node is not None and node.text else default

    nit_raw = get_txt(".//cac:AccountingSupplierParty//cbc:CompanyID", "000000000")

    return {
        "fecha": get_txt(".//cbc:IssueDate", "2026-01-01"),
        "numero_factura": get_txt(".//cbc:ID", "1"),
        "proveedor": {
            "nit": re.sub(r"\D", "", nit_raw.split("-")[0]),
            "nombre": get_txt(
                ".//cac:AccountingSupplierParty//cbc:RegistrationName",
                "PROVEEDOR"
            ),
        },
        "totales": totales,
        "base": bases,
    }