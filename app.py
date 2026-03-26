# 🔹 IMPORTS
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml
import requests
import re

# 🔹 CONFIG SIIGO
SIIGO_TOKEN = "TU_TOKEN_AQUI"
SIIGO_URL = "https://api.siigo.com/v1/purchases"

HEADERS = {
    "Authorization": f"Bearer {SIIGO_TOKEN}",
    "Username": "administrativo@crewwellness.club",
    "Content-Type": "application/json",
    "Partner-Id": "CrewWellnessAPI"
}

# 🔹 FUNCIÓN PRINCIPAL
def enviar_a_siigo(factura):

    # 🔹 EXTRAER PREFIJO Y NÚMERO
    numero_raw = factura.get("numero_factura", "")
    match = re.match(r"([A-Za-z]*)(\d+)", numero_raw)

    if match:
        prefijo = match.group(1) or "FC"
        numero = int(match.group(2))
    else:
        prefijo = "FC"
        numero = 1

    # 🔹 TOMAR TOTALES DEL XML (ESTANDAR DIAN)
    subtotal = factura["totales"]["subtotal"]
    iva_total = factura["iva_total"]
    total = factura["totales"]["total_pagar"]

    # 🔹 ARMAR DATA SIIGO (MODELO CONSOLIDADO)
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
        "items": [],
        "payments": [
            {
                "id": 20868,
                "value": total,
                "due_date": factura["fecha"]
            }
        ]
    }

    # 🔹 ITEM CONSOLIDADO
    item = {
        "code": "72057201",
        "description": "Compra consolidada",
        "quantity": 1,
        "price": subtotal,
        "type": "Account"
    }

    # 🔹 IVA
    if iva_total > 0:
        item["taxes"] = [{"id": 13156}]

    data["items"] = [item]

    # 🔹 ENVÍO A SIIGO
    response = requests.post(SIIGO_URL, json=data, headers=HEADERS)

    print("SIIGO STATUS:", response.status_code)
    print("SIIGO RESP:", response.text)

    return response.status_code, response.text


# 🔹 FLASK
app = Flask(__name__)

@app.route('/xml', methods=['POST'])
def recibir_xml():
    data = request.json
    nombre = data.get("nombre", "sin_nombre")
    xml_string = data.get("xml", "")

    try:
        factura = parsear_factura_xml(xml_string)

        siigo_status, siigo_resp = enviar_a_siigo(factura)

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