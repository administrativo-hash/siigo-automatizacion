# 🔹 IMPORTS
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml
import requests

# 🔹 CONFIG SIIGO (AQUÍ VA)
SIIGO_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IkM3QzFFQTY5M0FCMDREQTM5RkRBNTc3RDc4NTM0NEYxRkI5MDcwQzhSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ing4SHFhVHF3VGFPZjJsZDllRk5FOGZ1UWNNZyJ9.eyJuYmYiOjE3NzQ1NTQ3MzIsImV4cCI6MTc3NDY0MTEzMiwiaXNzIjoiaHR0cDovL21zLXNlY3VyaXR5OjUwMDAiLCJhdWQiOiJodHRwOi8vbXMtc2VjdXJpdHk6NTAwMC9yZXNvdXJjZXMiLCJjbGllbnRfaWQiOiJTaWlnb0FQSSIsInN1YiI6IjE3ODU2MDUiLCJhdXRoX3RpbWUiOjE3NzQ1NTQ3MzIsImlkcCI6ImxvY2FsIiwibmFtZSI6ImFkbWluaXN0cmF0aXZvQGNyZXd3ZWxsbmVzcy5jbHViIiwibWFpbF9zaWlnbyI6ImFkbWluaXN0cmF0aXZvQGNyZXd3ZWxsbmVzcy5jbHViIiwiY2xvdWRfdGVuYW50X2NvbXBhbnlfa2V5IjoiQ1JFV1dFTExORVNTQ0xVQlNBUyIsInVzZXJzX2lkIjoiMTA3MiIsInRlbmFudF9pZCI6IjB4MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA0MzQyMDYiLCJ1c2VyX2xpY2Vuc2VfdHlwZSI6IjAiLCJwbGFuX3R5cGUiOiIxNCIsInRlbmFudF9zdGF0ZSI6IjEiLCJtdWx0aXRlbmFudF9pZCI6IjQ5MiIsImNvbXBhbmllcyI6IjAiLCJhcGlfc3Vic2NyaXB0aW9uX2tleSI6IjFkYjZhNjY5NDRjNjQ2NmNiZDk3M2E4MWE1YWNmZTdlIiwiYXBpX3VzZXJfY3JlYXRlZF9hdCI6IjE2OTYwMTU0OTUiLCJhY2NvdW50YW50IjoiZmFsc2UiLCJqdGkiOiI3QTEzNkVDN0U0MkUzQjc4NkRFMzNCQTRDNkY4MjVDNiIsImlhdCI6MTc3NDU1NDczMiwic2NvcGUiOlsiU2lpZ29BUEkiXSwiYW1yIjpbImN1c3RvbSJdfQ.gfVWcgLvjhewDPcpGE9T8sCoRTFu3U4iui1TZrwRDy1JbvqncPI6KVqF6VPFIHMPGhOrXc5ftoykPLRDbXcRm0oVa24iu5A0zBjdtQ-YUcnTgDGyb84rKuys-XdYa3fWlPDCkA8RMr-uP3sEMxAaawnyuM1flQjETyY9tvxfcAnxPk3ZzxaE3iemiSMRkAKZPFrTG8kIx9FyxSeu7WqEAJEhvcx68CnkU93HSqyoumysHCs7kSjVev18Q09sGD2bGYaDDXuodSxdv-f8Igk01f2tbhtQKeiAO-MK1f1qNcsyu-wCWl3hPQy8rMUthDqf4BESzuq0Ur_0SAwJvGLAcg"
SIIGO_URL = "https://api.siigo.com/v1/purchases"

HEADERS = {
    "Authorization": SIIGO_TOKEN,
    "Username": "administrativo@crewwellness.club",
    "Content-Type": "application/json",
    "Partner-Id": "CrewWellnessAPI"
}
def enviar_a_siigo(factura):
    import re

    # 🔹 EXTRAER PREFIJO Y NÚMERO DESDE XML
    numero_raw = factura.get("numero_factura", "")

    match = re.match(r"([A-Za-z]*)(\d+)", numero_raw)

    if match:
        prefijo = match.group(1) or "FC"
        numero = int(match.group(2))
    else:
        prefijo = "FC"
        numero = 1

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
                "value": factura["totales"]["total_pagar"],
                "due_date": factura["fecha"]
            }
        ]
    }

    # 🔹 MAPEO DE LÍNEAS
    for linea in factura["lineas"]:
        data["items"].append({
            "code": "72057201",
            "description": linea["descripcion"],
            "quantity": linea["cantidad"],
            "price": linea["precio_unitario"],
            "type": "Account"
        })

    response = requests.post(SIIGO_URL, json=data, headers=HEADERS)

    print("SIIGO STATUS:", response.status_code)
    print("SIIGO RESP:", response.text)

    return response.status_code, response.text


app = Flask(__name__)

@app.route('/xml', methods=['POST'])
def recibir_xml():
    data = request.json
    nombre = data.get("nombre", "sin_nombre")
    xml_string = data.get("xml", "")

    try:
        factura = parsear_factura_xml(xml_string)

        # 🔥 AQUÍ SE ENVÍA A SIIGO
        siigo_status, siigo_resp = enviar_a_siigo(factura)

        return jsonify({
            "status": "ok",
            "siigo_status": siigo_status,
            "siigo_response": siigo_resp
        }), 200

    except Exception as e:
        print(f"❌ Error procesando {nombre}: {e}")
        return jsonify({"status": "error", "mensaje": str(e)}), 400


@app.route('/')
def home():
    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)