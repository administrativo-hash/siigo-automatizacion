# parser_xml.py
import xml.etree.ElementTree as ET

NS = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}


def extraer_valor(root, paths):
    for path in paths:
        elemento = root.find(path, NS)
        if elemento is not None and elemento.text:
            try:
                return float(elemento.text)
            except:
                continue
    return 0


def extraer_totales(root):

    subtotal = extraer_valor(root, [
        ".//cac:LegalMonetaryTotal/cbc:LineExtensionAmount",
        ".//cbc:LineExtensionAmount"
    ])

    total = extraer_valor(root, [
        ".//cac:LegalMonetaryTotal/cbc:PayableAmount",
        ".//cbc:PayableAmount"
    ])

    iva_total = extraer_valor(root, [
        ".//cac:TaxTotal/cbc:TaxAmount",
        ".//cbc:TaxAmount"
    ])

    # 🔹 Fallback contable
    if subtotal == 0 and total > 0 and iva_total > 0:
        subtotal = total - iva_total

    if total == 0 and subtotal > 0:
        total = subtotal + iva_total

    return round(subtotal, 2), round(iva_total, 2), round(total, 2)


def parsear_factura_xml(xml_string):

    root = ET.fromstring(xml_string)

    # 🔹 TOTALES
    subtotal, iva_total, total = extraer_totales(root)

    # 🔹 NÚMERO FACTURA
    numero = root.find(".//cbc:ID", NS)
    numero_factura = numero.text if numero is not None else "1"

    # 🔹 FECHA
    fecha = root.find(".//cbc:IssueDate", NS)
    fecha = fecha.text if fecha is not None else "2026-01-01"

    # 🔹 PROVEEDOR NIT
    nit = root.find(".//cac:AccountingSupplierParty//cbc:CompanyID", NS)
    nit = nit.text if nit is not None else "000000000"

    # 🔹 NOMBRE PROVEEDOR
    nombre = root.find(".//cac:AccountingSupplierParty//cbc:RegistrationName", NS)
    nombre = nombre.text if nombre is not None else "PROVEEDOR"

    factura = {
        "fecha": fecha,
        "numero_factura": numero_factura,
        "proveedor": {
            "nit": nit,
            "nombre": nombre
        },
        "totales": {
            "subtotal": subtotal,
            "total_pagar": total
        },
        "iva_total": iva_total
    }

    # 🔍 DEBUG (recomendado dejarlo temporal)
    print("---- PARSER ----")
    print("NIT:", nit)
    print("PROVEEDOR:", nombre)
    print("FACTURA:", numero_factura)
    print("SUBTOTAL:", subtotal)
    print("IVA:", iva_total)
    print("TOTAL:", total)

    return factura