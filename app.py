# 🔹 IMPORTS 
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml
import requests
import re
import xml.etree.ElementTree as ET

# 🔹 CONFIG SIIGO
SIIGO_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IkM3QzFFQTY5M0FCMDREQTM5RkRBNTc3RDc4NTM0NEYxRkI5MDcwQzhSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ing4SHFhVHF3VGFPZjJsZDllRk5FOGZ1UWNNZyJ9.eyJuYmYiOjE3NzQ2MzM0NDEsImV4cCI6MTc3NDcxOTg0MSwiaXNzIjoiaHR0cDovL21zLXNlY3VyaXR5OjUwMDAiLCJhdWQiOiJodHRwOi8vbXMtc2VjdXJpdHk6NTAwMC9yZXNvdXJjZXMiLCJjbGllbnRfaWQiOiJTaWlnb0FQSSIsInN1YiI6IjE3ODU2MDUiLCJhdXRoX3RpbWUiOjE3NzQ2MzM0NDEsImlkcCI6ImxvY2FsIiwibmFtZSI6ImFkbWluaXN0cmF0aXZvQGNyZXd3ZWxsbmVzcy5jbHViIiwibWFpbF9zaWlnbyI6ImFkbWluaXN0cmF0aXZvQGNyZXd3ZWxsbmVzcy5jbHViIiwiY2xvdWRfdGVuYW50X2NvbXBhbnlfa2V5IjoiQ1JFV1dFTExORVNTQ0xVQlNBUyIsInVzZXJzX2lkIjoiMTA3MiIsInRlbmFudF9pZCI6IjB4MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA0MzQyMDYiLCJ1c2VyX2xpY2Vuc2VfdHlwZSI6IjAiLCJwbGFuX3R5cGUiOiIxNCIsInRlbmFudF9zdGF0ZSI6IjEiLCJtdWx0aXRlbmFudF9pZCI6IjQ5MiIsImNvbXBhbmllcyI6IjAiLCJhcGlfc3Vic2NyaXB0aW9uX2tleSI6IjFkYjZhNjY5NDRjNjQ2NmNiZDk3M2E4MWE1YWNmZTdlIiwiYXBpX3VzZXJfY3JlYXRlZF9hdCI6IjE2OTYwMTU0OTUiLCJhY2NvdW50YW50IjoiZmFsc2UiLCJqdGkiOiJFODdBRENCMDUxMUJEQzY4NjM4RjM3N0NDODREMjk0MiIsImlhdCI6MTc3NDYzMzQ0MSwic2NvcGUiOlsiU2lpZ29BUEkiXSwiYW1yIjpbImN1c3RvbSJdfQ.j6qTQjy-Ydnal2SQQrKdPMT51exZPzGRNpWSQiBogrEbg-N6p1H7DWmFVTlgIq0PyHaVSCaJz5Z_RVRZ3W56x2N3ZFJPrheXTMO2htWAHPhvHnfCwP9zmrd3xBlOxRLrwVxgaIh_ScA5trf7BG5b3vKSUv7_eFCirJE5n78MaJkf4kNQ_QOSPMO20S1w3Lgzz5z9PPahJym-qHVaMAuFXXL1veiBTu0Gnah2FcCJmu9pi432Am9XOHnk0Q_G5ZBB4TvZCNMdE_5AcqyDeEIUNPiyuJU4WMshutDl2rgC1DVeq2AGZNCJTXfz97WcY-WMFetVHYijNdiu4nktuSvrKg"
SIIGO_URL = "https://api.siigo.com/v1/purchases"

HEADERS = {
    "Authorization": f"Bearer {SIIGO_TOKEN}",
    "Username": "administrativo@crewwellness.club",
    "Content-Type": "application/json",
    "Partner-Id": "CrewWellnessAPI"
}

# 🔹 EXTRAER NIT DESDE XML (SIN DV)
def obtener_nit_desde_xml(xml_string):
    ns = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    root = ET.fromstring(xml_string.strip())

    desc = root.find('.//cac:Attachment/cac:ExternalReference/cbc:Description', ns)

    if desc is not None and desc.text:
        invoice_root = ET.fromstring(desc.text.strip())
    else:
        invoice_root = root

    nit_raw = invoice_root.find(
        './/cac:AccountingSupplierParty//cbc:CompanyID', ns
    ).text.strip()

    # 🔥 quitar DV y dejar solo números
    nit_limpio = re.sub(r'\D', '', nit_raw.split('-')[0])

    return nit_limpio

# 🔹 FUNCIÓN PRINCIPAL
def enviar_a_siigo(factura, xml_string):

    # 🔹 NIT REAL
    nit_real = obtener_nit_desde_xml(xml_string)

    # 🔹 PREFIJO Y NÚMERO
    numero_raw = factura.get("numero_factura", "")
    match = re.match(r"([A-Za-z]*)(\d+)", numero_raw)

    if match:
        prefijo = match.group(1) or "FC"
        numero = int(match.group(2))
    else:
        prefijo = "FC"
        numero = 1

    # 🔹 VALORES DESDE PARSER (SIN DUPLICAR LÓGICA)
    subtotal = round(factura["totales"]["subtotal"], 2)
    iva_total = round(factura["iva_total"], 2)
    total = round(factura["totales"]["total_pagar"], 2)

    # 🔹 PAYMENT (RESTA RETENCIONES YA INCLUIDAS EN TOTAL)
    # 👉 aquí NO recalculamos XML, usamos lo que ya trae parser
    payment_correcto = total

    # 🔹 DEBUG OBLIGATORIO
    print("DEBUG → NIT:", nit_real)
    print("DEBUG → SUBTOTAL (base):", subtotal)
    print("DEBUG → IVA XML:", iva_total)
    print("DEBUG → TOTAL:", total)
    print("DEBUG → PAYMENT:", payment_correcto)

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
            "identification": nit_real
        },
        "cost_center": 1132,
        "items": [
            {
                "code": "72057201",
                "description": "Compra consolidada",
                "quantity": 1,
                "price": subtotal,  # ✅ BASE SIN IVA
                "type": "Account",
                **(
                    {
                        "taxes": [{"id": 8326}]  # ⚠️ validar en tu SIIGO
                    } if iva_total > 0 else {}
                )
            }
        ],
        "payments": [
            {
                "id": 1,
                "value": payment_correcto
            }
        ]
    }

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

    # 🔥 limpiar XML
    xml_string = data.get("xml", "").strip()

    try:
        factura = parsear_factura_xml(xml_string)

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