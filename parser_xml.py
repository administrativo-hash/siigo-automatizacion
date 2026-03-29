import xml.etree.ElementTree as ET
import re
from decimal import Decimal

NS = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}

def extraer_xml_interno(xml_string):
    root = ET.fromstring(xml_string.strip().lstrip('\ufeff'))
    desc = root.find('.//cac:Attachment/cac:ExternalReference/cbc:Description', NS)
    if desc is not None and desc.text:
        xml_limpio = desc.text.strip().lstrip('\ufeff')
        try:
            return ET.fromstring(xml_limpio), root
        except Exception as e:
            print("❌ Error parseando XML interno:", e)
            print("Contenido problemático:", xml_limpio[:200])
            raise
    return root, root

def extraer_valor(root, paths):
    for path in paths:
        el = root.find(path, NS)
        if el is not None and el.text:
            try:
                return float(el.text)
            except:
                continue
    return 0

def extraer_iva_real(invoice_root):
    iva = invoice_root.find(".//cac:TaxTotal/cbc:TaxAmount", NS)
    if iva is not None and iva.text:
        return round(float(iva.text), 2)
    return 0

def extraer_bases_por_tarifa(invoice_root):
    bases = {}
    for line in invoice_root.findall(".//cac:InvoiceLine", NS):
        base_el = line.find(".//cbc:LineExtensionAmount", NS)
        if base_el is None or not base_el.text:
            continue
        base = Decimal(base_el.text)
        percent_el = line.find(".//cac:TaxCategory/cbc:Percent", NS)
        if percent_el is not None and percent_el.text:
            tarifa = str(int(float(percent_el.text)))
        else:
            tarifa = "0"
        if tarifa not in bases:
            bases[tarifa] = Decimal("0.00")
        bases[tarifa] += base
    for t in ["19", "5", "0"]:
        bases.setdefault(t, Decimal("0.00"))
    return bases

def extraer_totales(invoice_root):
    subtotal = extraer_valor(invoice_root, [
        ".//cac:LegalMonetaryTotal/cbc:LineExtensionAmount"
    ])
    total = extraer_valor(invoice_root, [
        ".//cac:LegalMonetaryTotal/cbc:PayableAmount"
    ])
    iva_total = extraer_iva_real(invoice_root)

    if subtotal == 0 and total > 0 and iva_total > 0:
        subtotal = round(total - iva_total, 2)
    if total == 0 and subtotal > 0:
        total = subtotal + iva_total

    return round(subtotal, 2), round(iva_total, 2), round(total, 2)

def parsear_factura_xml(xml_string):
    invoice_root, _ = extraer_xml_interno(xml_string)

    subtotal, iva_total, total = extraer_totales(invoice_root)
    bases = extraer_bases_por_tarifa(invoice_root)  # ✅ llamada explícita aquí

    numero = invoice_root.find(".//cbc:ID", NS)
    numero_factura = numero.text.strip() if numero is not None else "1"

    fecha = invoice_root.find(".//cbc:IssueDate", NS)
    fecha = fecha.text if fecha is not None else "2026-01-01"

    nit_raw = invoice_root.find(".//cac:AccountingSupplierParty//cbc:CompanyID", NS)
    nit_raw = nit_raw.text.strip() if nit_raw is not None else "000000000"
    nit = re.sub(r'\D', '', nit_raw.split('-')[0])

    nombre = invoice_root.find(".//cac:AccountingSupplierParty//cbc:RegistrationName", NS)
    nombre = nombre.text.strip() if nombre is not None else "PROVEEDOR"

    print("---- PARSER ----")
    print("NIT limpio:", nit)
    print("PROVEEDOR:", nombre)
    print("FACTURA:", numero_factura)
    print("SUBTOTAL:", subtotal)
    print("IVA:", iva_total)
    print("TOTAL:", total)
    print("BASES:", bases)

    return {
        "fecha": fecha,
        "numero_factura": numero_factura,
        "proveedor": {"nit": nit, "nombre": nombre},
        "totales": {"subtotal": subtotal, "total_pagar": total},
        "iva_total": iva_total,
        "base": bases
    }