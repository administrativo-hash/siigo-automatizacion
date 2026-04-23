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
            print(f"❌ Error parseando XML interno: {e}")
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
    return 0.0

def extraer_iva_real(invoice_root):
    iva = invoice_root.find(".//cac:TaxTotal/cbc:TaxAmount", NS)
    if iva is not None and iva.text:
        return round(float(iva.text), 2)
    return 0.0

def extraer_bases_por_tarifa(invoice_root):
    bases = {}
    for line in invoice_root.findall(".//cac:InvoiceLine", NS):
        base_el = line.find(".//cbc:LineExtensionAmount", NS)
        if base_el is None or not base_el.text:
            continue
        base = Decimal(base_el.text)
        percent_el = line.find(".//cac:TaxCategory/cbc:Percent", NS)
        tarifa = str(int(float(percent_el.text))) if percent_el is not None and percent_el.text else "0"
        
        if tarifa not in bases:
            bases[tarifa] = Decimal("0.00")
        bases[tarifa] += base
    
    for t in ["19", "5", "0"]:
        bases.setdefault(t, Decimal("0.00"))
    return bases

def extraer_totales(invoice_root):
    # 1. Extraer los valores tal cual vienen en el XML (La fuente de verdad de Siigo)
    subtotal_xml = extraer_valor(invoice_root, [".//cac:LegalMonetaryTotal/cbc:LineExtensionAmount"])
    iva_total_xml = extraer_iva_real(invoice_root)
    payable_amount_xml = extraer_valor(invoice_root, [".//cac:LegalMonetaryTotal/cbc:PayableAmount"])
    anticipo_xml = extraer_valor(invoice_root, [".//cac:LegalMonetaryTotal/cbc:PrepaidAmount"])
    
    # 2. LÓGICA INTELIGENTE:
    # Si hay un anticipo significativo (> 1 peso), significa que es el proveedor del error.
    # En ese caso, forzamos el cálculo de Cuenta por Pagar.
    if anticipo_xml > 1.0:
        total_final = round(subtotal_xml + iva_total_xml, 2)
        print(f"ℹ️ Modo Corrección: Anticipo detectado ({anticipo_xml}). Total forzado: {total_final}")
    else:
        # Si NO hay anticipo (como COMCEL o DOCUPRINT), usamos el PayableAmount original.
        # Esto garantiza que Siigo reciba el valor exacto que espera.
        total_final = payable_amount_xml

    # Validaciones de seguridad por si el XML viene vacío
    if total_final == 0 and subtotal_xml > 0:
        total_final = round(subtotal_xml + iva_total_xml, 2)

    return round(subtotal_xml, 2), round(iva_total_xml, 2), round(total_final, 2)
def extraer_id_type(invoice_root):
    node = invoice_root.find(".//cac:AccountingSupplierParty//cac:PartyTaxScheme//cbc:CompanyID", NS)
    if node is not None:
        scheme = node.attrib.get("schemeName")
        if scheme: return scheme.strip()
    
    nit_node = invoice_root.find(".//cac:AccountingSupplierParty//cbc:CompanyID", NS)
    if nit_node is not None and nit_node.text:
        nit = re.sub(r'\D', '', nit_node.text.split("-")[0])
        return "31" if len(nit) == 9 else "13"
    return "13"

def parsear_factura_xml(xml_string):
    invoice_root, _ = extraer_xml_interno(xml_string)

    # Obtenemos datos financieros
    subtotal, iva_total, total = extraer_totales(invoice_root)
    bases = extraer_bases_por_tarifa(invoice_root)

    # Extracción segura de textos para evitar AttributeError
    def get_txt(path, default=""):
        node = invoice_root.find(path, NS)
        return node.text.strip() if node is not None and node.text else default

    numero_factura = get_txt(".//cbc:ID", "1")
    fecha = get_txt(".//cbc:IssueDate", "2026-01-01")
    
    nit_raw = get_txt(".//cac:AccountingSupplierParty//cbc:CompanyID", "000000000")
    nit = re.sub(r'\D', '', nit_raw.split('-')[0])

    nombre = get_txt(".//cac:AccountingSupplierParty//cbc:RegistrationName", "PROVEEDOR")
    id_type = extraer_id_type(invoice_root).strip()

    return {
        "fecha": fecha,
        "numero_factura": numero_factura,
        "proveedor": {"nit": nit, "nombre": nombre, "id_type": id_type },
        "totales": {"subtotal": subtotal, "total_pagar": total},
        "iva_total": iva_total,
        "base": bases
    }