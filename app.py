# 🔹 IMPORTS
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml
import requests

# 🔹 CONFIG SIIGO (AQUÍ VA)
SIIGO_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IkM3QzFFQTY5M0FCMDREQTM5RkRBNTc3RDc4NTM0NEYxRkI5MDcwQzhSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ing4SHFhVHF3VGFPZjJsZDllRk5FOGZ1UWNNZyJ9.eyJuYmYiOjE3NzQzNjYxODQsImV4cCI6MTc3NDQ1MjU4NCwiaXNzIjoiaHR0cDovL21zLXNlY3VyaXR5OjUwMDAiLCJhdWQiOiJodHRwOi8vbXMtc2VjdXJpdHk6NTAwMC9yZXNvdXJjZXMiLCJjbGllbnRfaWQiOiJTaWlnb0FQSSIsInN1YiI6IjE3ODU2MDUiLCJhdXRoX3RpbWUiOjE3NzQzNjYxODQsImlkcCI6ImxvY2FsIiwibmFtZSI6ImFkbWluaXN0cmF0aXZvQGNyZXd3ZWxsbmVzcy5jbHViIiwibWFpbF9zaWlnbyI6ImFkbWluaXN0cmF0aXZvQGNyZXd3ZWxsbmVzcy5jbHViIiwiY2xvdWRfdGVuYW50X2NvbXBhbnlfa2V5IjoiQ1JFV1dFTExORVNTQ0xVQlNBUyIsInVzZXJzX2lkIjoiMTA3MiIsInRlbmFudF9pZCI6IjB4MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA0MzQyMDYiLCJ1c2VyX2xpY2Vuc2VfdHlwZSI6IjAiLCJwbGFuX3R5cGUiOiIxNCIsInRlbmFudF9zdGF0ZSI6IjEiLCJtdWx0aXRlbmFudF9pZCI6IjQ5MiIsImNvbXBhbmllcyI6IjAiLCJhcGlfc3Vic2NyaXB0aW9uX2tleSI6IjFkYjZhNjY5NDRjNjQ2NmNiZDk3M2E4MWE1YWNmZTdlIiwiYXBpX3VzZXJfY3JlYXRlZF9hdCI6IjE2OTYwMTU0OTUiLCJhY2NvdW50YW50IjoiZmFsc2UiLCJqdGkiOiJGRTMwNTgxN0RGN0JBRTM4RDk1ODg0MkU5MDFDRjRBNSIsImlhdCI6MTc3NDM2NjE4NCwic2NvcGUiOlsiU2lpZ29BUEkiXSwiYW1yIjpbImN1c3RvbSJdfQ.J1mQQI0sMKV68N2Ex8Wfez0ztn_dzmyPQWsBJjKWTemX4cd-otkoR-xRBvH3j5kwPY72IaRQ9kaFQc3ZxE5bUw-raebzCFPBAravGqgofqnrkOk9e8sDQLIDPKwMOBPAw_8jmDY1QTbhKTndjJ47NW2V6neO15CZHxhZrafVG6gsf33YG0dv6AymoW4o4ErzAZFp45wFpSfrvP9x26g2--tWYx5YRm8WQEnIOBG2h2aTDHaxRV9C6jVAcOSCMwuo8mDg5hXpqPJBWC5UEEGio163nMi96b0LeXz-ir6ZPJWGI5Cxd8vxxKQtbaOP0NAdJg5zZMaREUQQq-K6HRXRYA"
SIIGO_URL = "https://api.siigo.com/v1/purchases"

HEADERS = {
    "Authorization": f"Bearer {SIIGO_TOKEN}",
    "Username": "administrativo@crewwellness.club",
    "Content-Type": "application/json",
    "Partner-Id": "CrewWellnessAPI"
}

# 🔹 FUNCIÓN SIIGO
def enviar_a_siigo(factura):
    data = {
        "document": {
            "id": 15481
        },
        "date": factura["fecha"],
        "provider_invoice": {
            "prefix": "FC",
            "number": int(factura["numero_factura"]) if factura["numero_factura"].isdigit() else 1
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

    # 🔥 MAPEO DE LÍNEAS → ACCOUNT
    for linea in factura["lineas"]:
        data["items"].append({
            "code": "72057201",  # cuenta contable
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