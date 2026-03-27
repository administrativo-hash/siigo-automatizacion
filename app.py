# 🔹 IMPORTS 
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml
import requests
import re

# 🔹 CONFIG SIIGO
SIIGO_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IkM3QzFFQTY5M0FCMDREQTM5RkRBNTc3RDc4NTM0NEYxRkI5MDcwQzhSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ing4SHFhVHF3VGFPZjJsZDllRk5FOGZ1UWNNZyJ9.eyJuYmYiOjE3NzQ1NTQ3MzIsImV4cCI6MTc3NDY0MTEzMiwiaXNzIjoiaHR0cDovL21zLXNlY3VyaXR5OjUwMDAiLCJhdWQiOiJodHRwOi8vbXMtc2VjdXJpdHk6NTAwMC9yZXNvdXJjZXMiLCJjbGllbnRfaWQiOiJTaWlnb0FQSSIsInN1YiI6IjE3ODU2MDUiLCJhdXRoX3RpbWUiOjE3NzQ1NTQ3MzIsImlkcCI6ImxvY2FsIiwibmFtZSI6ImFkbWluaXN0cmF0aXZvQGNyZXd3ZWxsbmVzcy5jbHViIiwibWFpbF9zaWlnbyI6ImFkbWluaXN0cmF0aXZvQGNyZXd3ZWxsbmVzcy5jbHViIiwiY2xvdWRfdGVuYW50X2NvbXBhbnlfa2V5IjoiQ1JFV1dFTExORVNTQ0xVQlNBUyIsInVzZXJzX2lkIjoiMTA3MiIsInRlbmFudF9pZCI6IjB4MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA0MzQyMDYiLCJ1c2VyX2xpY2Vuc2VfdHlwZSI6IjAiLCJwbGFuX3R5cGUiOiIxNC\",\"tenant_state\":\"1\",\"multitenant_id\":\"492\",\"companies\":\"0\",\"api_subscription_key\":\"1db6a66944c6466cbd973a81a5acfe7e\",\"api_user_created_at\":\"1696015495\",\"accountant\":\"false\",\"jti\":\"7A136EC7E42E3B786DE33BA4C6F825C6\",\"iat\":1774554732,\"scope\":[\"SiigoAPI\"],\"amr\":[\"custom\"]}.gfVWcgLvjhewDPcpGE9T8sCoRTFu3U4iui1TZrwRDy1JbvqncPI6KVqF6VPFIHMPGhOrXc5ftoykPLRDbXcRm0oVa24iu5A0zBjdtQ-YUcnTgDGyb84rKuys-XdYa3fWlPDCkA8RMr-uP3sEMxAaawnyuM1flQjETyY9tvxfcAnxPk3ZzxaE3iemiSMRkAKZPFrTG8kIx9FyxSeu7WqEAJEhvcx68CnkU93HSqyoumysHCs7kSjVev18Q09sGD2bGYaDDXuodSxdv-f8Igk01f2tbhtQKeiAO-MK1f1qNcsyu-wCWl3hPQy8rMUthDqf4BESzuq0Ur_0SAwJvGLAcg"
SIIGO_URL = "https://api.siigo.com/v1/purchases"

HEADERS = {
    "Authorization": f"Bearer {SIIGO_TOKEN}",
    "Username": "administrativo@crewwellness.club",
    "Content-Type": "application/json",
    "Partner-Id": "CrewWellnessAPI"
}

def enviar_a_siigo(factura):

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

    # 🔥 TOTAL CALCULADO EXACTO (CLAVE)
    total = round(subtotal + iva_total, 2)
    total = float(f"{total:.2f}")

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

    # 🔥 ITEM CON TOTAL EXACTO (NO SUBTOTAL)
    item = {
        "code": "72057201",
        "description": "Compra consolidada",
        "quantity": 1,
        "price": total,
        "type": "Account"
    }

    data["items"] = [item]

    response = requests.post(SIIGO_URL, json=data, headers=HEADERS)

    print("DEBUG → SUBTOTAL:", subtotal)
    print("DEBUG → IVA:", iva_total)
    print("DEBUG → TOTAL:", total)

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