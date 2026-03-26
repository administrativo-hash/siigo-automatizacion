# parser_xml.py
import re
import xml.etree.ElementTree as ET

NS = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}

def parsear_factura_xml(xml_string: str) -> dict:
    """
    Recibe el contenido XML como string (AttachedDocument colombiano UBL 2.1).
    Retorna un dict con todos los datos necesarios para SIIGO.
    """
    # PASO 1: Extraer Invoice del CDATA
    cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', xml_string, re.DOTALL)
    if not cdata_match:
        raise ValueError("No se encontró CDATA con Invoice embebida")
    
    invoice_xml = cdata_match.group(1)
    root = ET.fromstring(invoice_xml)

    def txt(element, path):
        return element.findtext(path, namespaces=NS)

    # PASO 2: Extraer encabezado
    numero = txt(root, './/cbc:ID')
    fecha = txt(root, './/cbc:IssueDate')
    tipo = txt(root, './/cbc:InvoiceTypeCode')  # "01" = factura venta

    # PASO 3: Proveedor
    sup = root.find('.//cac:AccountingSupplierParty', NS)
    proveedor = {
        "nit": txt(sup, './/cbc:CompanyID'),
        "nombre": txt(sup, './/cbc:RegistrationName'),
    }

    # PASO 4: Totales
    mon = root.find('.//cac:LegalMonetaryTotal', NS)
    totales = {
        "subtotal": float(txt(mon, 'cbc:LineExtensionAmount') or 0),
        "total_con_iva": float(txt(mon, 'cbc:TaxInclusiveAmount') or 0),
        "total_pagar": float(txt(mon, 'cbc:PayableAmount') or 0),
    }

    # PASO 5: IVA total (solo el primer TaxTotal = total factura)
    primer_tax = root.find('.//cac:TaxTotal', NS)
    iva_total = float(txt(primer_tax, 'cbc:TaxAmount') or 0) if primer_tax is not None else 0

    # PASO 6: Líneas
    lineas = []
    for line in root.findall('.//cac:InvoiceLine', NS):
        lineas.append({
            "id": txt(line, 'cbc:ID'),
            "descripcion": txt(line, './/cbc:Description'),
            "cantidad": float(txt(line, 'cbc:InvoicedQuantity') or 0),
            "precio_unitario": float(txt(line, './/cbc:PriceAmount') or 0),
            "subtotal_linea": float(txt(line, 'cbc:LineExtensionAmount') or 0),
            "iva_pct": float(txt(line, './/cbc:Percent') or 0),
            "iva_valor": float(txt(line, './/cbc:TaxAmount') or 0),
        })

    return {
        "numero_factura": numero,
        "fecha": fecha,
        "tipo_documento": tipo,
        "proveedor": proveedor,
        "totales": totales,
        "iva_total": iva_total,
        "lineas": lineas,
    }
