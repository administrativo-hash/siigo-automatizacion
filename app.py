# 🔹 IMPORTS 
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml
import requests
import re
import xml.etree.ElementTree as ET

# 🔹 CONFIG SIIGO
SIIGO_TOKEN = "TU_TOKEN_AQUI"
SIIGO_URL = "https://api.siigo.com/v1/purchases"

HEADERS = {
    "Authorization": f"Bearer {SIIGO_TOKEN}",
    "Username": "administrativo@crewwellness.club",
    "Content-Type": "application/json",
    "Partner-Id": "CrewWellnessAPI"
}

# 🔹 FUNCIÓN: calcular payment correcto desde XML
def calcular_payment_desde_xml(xml_string):
    ns = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    root = ET.fromstring(xml_string)

    # XML interno (Invoice)
    description = root.find('.//cac:Attachment/cac:ExternalReference/cbc:Description', ns).text
    invoice_root = ET.fromstring(description)

    # PayableAmount
    payable = float(invoice_root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns).text)

    # Retenciones
    withholding_node = invoice_root.find('.//cac:WithholdingTaxTotal/cbc:TaxAmount', ns)
    retenciones = float(withholding_node.text) if withholding_node is not None else 0.0

    payment = payable - retenciones

    return round(payment, 2)

# 🔹 FUNCIÓN: enviar a Siigo
def enviar_a_siigo(factura, xml_string):

    numero_raw = factura.get("numero_factura", "")
    match = re.match(r"([A-Za-z]*)(\d+)", numero_raw)

    if match:
        prefijo = match.group(1) or "FC"
        numero = int(match.group(2))
    else:
        prefijo = "FC"
        numero = 1

    subtotal = round(factura["totales"]["subtotal"], 2)
    iva_total = round(factura["iva_total"], 2)

    total = round(subtotal + iva_total, 2)
    total = float(f"{total:.2f}")

    # ✅ cálculo correcto del pago
    payment_correcto = calcular_payment_desde_xml(xml_string)

    data = {
        "document": {
            "id": 15481
        },
        "date": factura["fecha"],
        "provider_invoice": {
            "prefix": prefijo,
            "number": numero
        },
        "supplier": {
            "identification": factura["proveedor"]["nit"]
        },
        "cost_center": 1132,
        "items": [
            {
                "code": "72057201",
                "description": "Compra consolidada",
                "quantity": 1,
                "price": total,
                "type": "Account"
            }
        ],
        "payments": [
            {
                "id": 1,
                "value": payment_correcto
            }
        ]
    }

    # 🔍 DEBUG
    print("DEBUG → SUBTOTAL:", subtotal)
    print("DEBUG → IVA:", iva_total)
    print("DEBUG → TOTAL:", total)
    print("DEBUG → PAYMENT:", payment_correcto)

    response = requests.post(SIIGO_URL, json=data, headers=HEADERS)

    print("SIIGO STATUS:", response.status_code)
    print("SIIGO RESP:", response.text)

    return response.status_code, response.text

# 🔹 APP FLASK
app = Flask(__name__)

@app.route('/xml', methods=['POST'])
def recibir_xml():
    data = request.json
    nombre = data.get("nombre", "sin_nombre")
    xml_string = data.get("xml", "")

    try:
        factura = parsear_factura_xml(xml_string)

        # ✅ se pasa xml_string correctamente
        siigo_status, siigo_resp = enviar_a_siigo(factura, xml_string)

        return jsonify({
            "status": "ok",
            "siigo_status": siigo_status,
            "siigo_response": siigo_resp
        }), 200

    except Exception as e:
        print(f"❌ Error procesando {nombre}: {e}")
        return jsonify({
            "status": "error",
            "mensaje": str(e)
        }), 400

@app.route('/')
def home():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)