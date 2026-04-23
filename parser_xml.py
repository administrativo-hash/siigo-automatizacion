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
            interno_root = ET.fromstring(xml_limpio)
            responses = interno_root.findall('.//{*}ResponseCode')
            for r in responses:
                if r.text in ['FAK57', 'FAK58']:
                    return interno_root, root, f"Error DIAN detectado: {r.text}"
            return interno_root, root, None
        except:
            raise
    return root, root, None

def extraer_valor(root, paths):
    for path in paths:
        el = root.find(path, NS)
        if el is not None and el.text:
            try: return float(el.text)
            except: continue
    return 0.0

def extraer_iva_real(invoice_root):
    iva = invoice_root.find(".//cac:TaxTotal/cbc:TaxAmount", NS)
    return round(float(iva.text), 2) if iva is not None and iva.text else 0.0

def extraer_bases_por_tarifa(invoice_root):
    bases = {}
    for line in invoice_root.findall(".//cac:InvoiceLine", NS):
        base_el = line.find(".//cbc:LineExtensionAmount", NS)
        if base_el is None or not base_el.text: continue
        base = Decimal(base_el.text)
        percent_el = line.find(".//cac:TaxCategory/cbc:Percent", NS)
        tarifa = str(int(float(percent_el.text))) if percent_el is not None and percent_el.text else "0"
        if tarifa not in bases: bases[tarifa] = Decimal("0.00")
        bases[tarifa] += base
    return bases

def extraer_totales(invoice_root):
    subtotal = extraer_valor(invoice_root, [".//cac:LegalMonetaryTotal/cbc:LineExtensionAmount"])
    iva = extraer_iva_real(invoice_root)
    payable = extraer_valor(invoice_root, [".//cac:LegalMonetaryTotal/cbc:PayableAmount"])
    anticipo = extraer_valor(invoice_root, [".//cac:LegalMonetaryTotal/cbc:PrepaidAmount"])
    return round(subtotal, 2), round(iva, 2), round(payable, 2), round(anticipo, 2)

def parsear_factura_xml(xml_string):
    invoice_root, _, error_dian = extraer_xml_interno(xml_string)
    if error_dian: return {"error": error_dian}

    # Sincronizado: Recibe los 4 valores (subtotal, iva, payable, anticipo)
    subtotal, iva_total, payable_xml, anticipo = extraer_totales(invoice_root)
    bases = extraer_bases_por_tarifa(invoice_root)

    def get_txt(path, default=""):
        node = invoice_root.find(path, NS)
        return node.text.strip() if node is not None and node.text else default

    nit_raw = get_txt(".//cac:AccountingSupplierParty//cbc:CompanyID", "000000000")
    
    return {
        "fecha": get_txt(".//cbc:IssueDate", "2026-01-01"),
        "numero_factura": get_txt(".//cbc:ID", "1"),
        "proveedor": {
            "nit": re.sub(r'\D', '', nit_raw.split('-')[0]),
            "nombre": get_txt(".//cac:AccountingSupplierParty//cbc:RegistrationName", "PROVEEDOR")
        },
        "totales": {"subtotal": subtotal, "total_xml": payable_xml, "anticipo": anticipo},
        "base": bases
    }