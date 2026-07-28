import xml.etree.ElementTree as ET
import re
from decimal import Decimal, ROUND_HALF_UP

def redondear(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def extraer_xml_interno(xml_string):
    try:
        root = ET.fromstring(xml_string.strip().lstrip("\ufeff"))
    except ET.ParseError:
        return None, None, "Error crítico: El XML principal está malformado o truncado."

    desc = root.find(".//{*}Attachment/{*}ExternalReference/{*}Description")

    if desc is not None and desc.text:
        try:
            xml_limpio = desc.text.strip().lstrip("\ufeff")
            interno_root = ET.fromstring(xml_limpio)
        except ET.ParseError:
            return root, root, "Error crítico: El XML interno de la factura está incompleto o truncado."

        responses = interno_root.findall(".//{*}ResponseCode")
        for r in responses:
            if r.text in ["FAK57", "FAK58"]:
                return interno_root, root, f"Error DIAN detectado: {r.text}"

        return interno_root, root, None

    return root, root, None

def extraer_valor(root, xpath_expr):
    el = root.find(xpath_expr)
    if el is not None and el.text:
        try:
            return Decimal(el.text)
        except Exception:
            return Decimal("0.00")
    return Decimal("0.00")

def extraer_iva_real(invoice_root):
    iva = Decimal("0.00")
    for tax_total in invoice_root.findall("./{*}TaxTotal"):
        tax_amount = tax_total.find("./{*}TaxAmount")
        if tax_amount is not None and tax_amount.text:
            iva += Decimal(tax_amount.text)
    return redondear(iva)

def extraer_bases_por_tarifa(invoice_root):
    bases = {}
    for tax_total in invoice_root.findall("./{*}TaxTotal"):
        for tax_subtotal in tax_total.findall("./{*}TaxSubtotal"):
            taxable_el = tax_subtotal.find("./{*}TaxableAmount")
            percent_el = tax_subtotal.find(".//{*}TaxCategory/{*}Percent")

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

def ajustar_base_cero(invoice_root, bases):
    """
    Agrega a la base '0' la diferencia entre LineExtensionAmount y la suma de
    las bases gravadas: esto corresponde a bienes/servicios excluidos, no
    gravados, o cargos legítimos de la factura. Esta diferencia SIEMPRE debe
    ser >= 0 (nunca es un ajuste artificial de redondeo).
    """
    line_extension = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}LineExtensionAmount')
    suma_bases = sum(bases.values(), Decimal("0.00"))
    diferencia = redondear(line_extension - suma_bases)

    if diferencia > 0:
        bases["0"] = redondear(bases.get("0", Decimal("0.00")) + diferencia)

    return bases

def calcular_total_siigo(bases):
    """
    Replica EXACTAMENTE la fórmula que Siigo va a aplicar sobre los items que
    realmente se le envían (base x tarifa, redondeado). Este valor -y NO el
    PayableAmount legal del XML- es el que debe ir en payments.value, porque
    payments debe cuadrar con lo que Siigo recalcula a partir de "items",
    no con el total del documento DIAN.

    IMPORTANTE: aquí NO se fuerza a que este total coincida con el
    PayableAmount del XML. Antes se intentaba "corregir" la diferencia
    inyectando una base "0" negativa, pero Siigo rechaza montos negativos
    en items (error invalid_amount / "discount amount is invalid"). La
    diferencia de centavos que pueda quedar contra el total legal del XML
    es inevitable (redondeo de Siigo por base consolidada vs redondeo del
    proveedor línea por línea) y es inmaterial para efectos contables.
    """
    base_19 = Decimal(str(bases.get("19", 0)))
    base_5 = Decimal(str(bases.get("5", 0)))
    base_8 = Decimal(str(bases.get("8", 0)))
    base_0 = Decimal(str(bases.get("0", 0)))

    iva_19 = redondear(base_19 * Decimal("0.19"))
    iva_5 = redondear(base_5 * Decimal("0.05"))
    iva_8 = redondear(base_8 * Decimal("0.08"))

    total_siigo = base_19 + iva_19 + base_5 + iva_5 + base_8 + iva_8 + base_0
    return redondear(total_siigo)

def extraer_totales(invoice_root, bases):
    line_extension = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}LineExtensionAmount')
    tax_exclusive = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}TaxExclusiveAmount')
    tax_inclusive = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}TaxInclusiveAmount')
    payable = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}PayableAmount')
    anticipo = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}PrepaidAmount')
    charge_total = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}ChargeTotalAmount')
    allowance_total = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}AllowanceTotalAmount')
    rounding = extraer_valor(invoice_root, './/{*}LegalMonetaryTotal/{*}PayableRoundingAmount')

    iva = extraer_iva_real(invoice_root)
    total_siigo = calcular_total_siigo(bases)
    payable_redondeado = redondear(payable)

    return {
        "line_extension": float(redondear(line_extension)),
        "tax_exclusive": float(redondear(tax_exclusive)),
        "tax_inclusive": float(redondear(tax_inclusive)),
        "iva": float(redondear(iva)),
        "total_xml": float(payable_redondeado),
        "total_siigo": float(total_siigo),
        # Solo informativo / para monitoreo, no se usa para construir el payload
        "diferencia_vs_xml": float(redondear(total_siigo - payable_redondeado)),
        "anticipo": float(redondear(anticipo)),
        "charge_total": float(redondear(charge_total)),
        "allowance_total": float(redondear(allowance_total)),
        "rounding": float(redondear(rounding)),
    }

def parsear_factura_xml(xml_string):
    invoice_root, _, error_dian = extraer_xml_interno(xml_string)

    if error_dian:
        return {"error": error_dian}

    if invoice_root is None:
        return {"error": "No se pudo procesar el archivo por estructura XML inválida."}

    bases = extraer_bases_por_tarifa(invoice_root)
    bases = ajustar_base_cero(invoice_root, bases)

    totales = extraer_totales(invoice_root, bases)

    def get_txt(path, default=""):
        node = invoice_root.find(path)
        return node.text.strip() if node is not None and node.text else default

    nit_raw = get_txt('.//{*}AccountingSupplierParty//{*}CompanyID', "000000000")
    fecha = get_txt('.//{*}IssueDate', "2026-01-01")
    numero_factura = get_txt('.//{*}ID', "1")
    nombre_proveedor = get_txt('.//{*}AccountingSupplierParty//{*}RegistrationName', "PROVEEDOR")

    return {
        "fecha": fecha,
        "numero_factura": numero_factura,
        "proveedor": {
            "nit": re.sub(r"\D", "", nit_raw.split("-")[0]),
            "nombre": nombre_proveedor,
        },
        "totales": totales,
        "base": bases,
    }