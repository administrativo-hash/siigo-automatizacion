import xml.etree.ElementTree as ET
import re

NS = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}

def limpiar_xml(texto):
    return texto.strip().replace('<?xml version="1.0" encoding="UTF-8"?>', '').strip()

def extraer_xml_interno(xml_string):
    root = ET.fromstring(xml_string.strip().lstrip('\ufeff'))

    desc = root.find(
        './/cac:Attachment/cac:ExternalReference/cbc:Description', NS
    )

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
    total_iva = 0

    for tax_total in invoice_root.findall(".//cac:TaxTotal", NS):
        percent = tax_total.find(".//cbc:Percent", NS)
        tax_amount = tax_total.find(".//cbc:TaxAmount", NS)

        if percent is not None and tax_amount is not None:
            try:
                pct = float(percent.text)
                if pct in [19, 5]:  # SOLO IVA válido
                    total_iva += float(tax_amount.text)
            except:
                continue

    return round(total_iva, 2)

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

    return round(subtotal,2), round(iva_total,2), round(total,2)

def parsear_factura_xml(xml_string):

    invoice_root, _ = extraer_xml_interno(xml_string)

    subtotal, iva_total, total = extraer_totales(invoice_root)

    numero = invoice_root.find(".//cbc:ID", NS)
    numero_factura = numero.text.strip() if numero is not None else "1"

    fecha = invoice_root.find(".//cbc:IssueDate", NS)
    fecha = fecha.text if fecha is not None else "2026-01-01"

    nit_raw = invoice_root.find(
        ".//cac:AccountingSupplierParty//cbc:CompanyID", NS
    )

    nit_raw = nit_raw.text.strip() if nit_raw is not None else "000000000"

    # 🔥 limpiar DV
    nit = re.sub(r'\D', '', nit_raw.split('-')[0])

    nombre = invoice_root.find(
        ".//cac:AccountingSupplierParty//cbc:RegistrationName", NS
    )
    nombre = nombre.text.strip() if nombre is not None else "PROVEEDOR"

    print("---- PARSER ----")
    print("NIT limpio:", nit)
    print("PROVEEDOR:", nombre)
    print("FACTURA:", numero_factura)
    print("SUBTOTAL:", subtotal)
    print("IVA:", iva_total)
    print("TOTAL:", total)

    return {
        "fecha": fecha,
        "numero_factura": numero_factura,
        "proveedor": {"nit": nit, "nombre": nombre},
        "totales": {"subtotal": subtotal, "total_pagar": total},
        "iva_total": iva_total
    }