from flask import Flask, request, jsonify
import requests
import re
from parser_xml import parsear_factura_xml

app = Flask(__name__)

# CONFIGURACIÓN
AUTH_URL = "https://api.siigo.com/auth"
SIIGO_URL_PURCHASES = "https://api.siigo.com/v1/purchases"
SIIGO_URL_CUSTOMERS = "https://api.siigo.com/v1/customers"
USERNAME = "administrativo@crewwellness.club"
ACCESS_KEY = "YTE0YWRlOWYtZTA3MC00NGIyLWJiMDMtOTlmZDU0YTkyOWIzOjw2a3gyVTwsVk4"

DOCUMENT_ID = 15481
COST_CENTER_ID = 1132
PAYMENT_ID = 20868
ACCOUNT_CODE = "72057201"

TAX_IDS = {
    "19": 8326,
    "5": 8327,
    "8": 8341,
}

def obtener_token():
    res = requests.post(
        AUTH_URL,
        json={"username": USERNAME, "access_key": ACCESS_KEY},
        timeout=20
    )
    res.raise_for_status()
    return res.json().get("access_token")

def construir_headers():
    return {
        "Authorization": f"Bearer {obtener_token()}",
        "Username": USERNAME,
        "Content-Type": "application/json",
        "Partner-Id": "CrewWellnessAPI"
    }

def crear_proveedor_en_siigo(factura, nit_real, headers):
    nombre = factura["proveedor"]["nombre"]

    payload = {
        "type": "Supplier",
        "person_type": "Company" if len(nit_real) == 9 else "Person",
        "id_type": "31" if len(nit_real) == 9 else "13",
        "identification": str(nit_real),
        "name": [nombre],
        "address": {
            "address": "No informado",
            "city": {
                "country_code": "Co",
                "state_code": "11",
                "city_code": "11001"
            }
        },
        "phones": [{"number": "0000000"}],
        "contacts": [{
            "first_name": nombre,
            "last_name": "API",
            "email": "administrativo@crewwellness.club"
        }],
        "fiscal_responsibilities": [{"code": "R-99-PN"}],
        "vat_responsible": False
    }

    res = requests.post(
        SIIGO_URL_CUSTOMERS,
        json=payload,
        headers=headers,
        timeout=30
    )

    return res.status_code in [200, 201]

def obtener_errores_siigo(respuesta_json):
    if not isinstance(respuesta_json, dict):
        return []

    errores = respuesta_json.get("siigo", {}).get("errors", [])

    if not errores:
        errores = respuesta_json.get("errors", [])

    return errores

def construir_items(factura):
    items = []
    bases = factura.get("base", {})

    for tarifa, tax_id in TAX_IDS.items():
        valor_base = round(float(bases.get(tarifa, 0)), 2)

        if valor_base > 0:
            items.append({
                "code": ACCOUNT_CODE,
                "description": f"Compra gravada {tarifa}%",
                "quantity": 1,
                "price": valor_base,
                "type": "Account",
                "taxes": [{"id": tax_id}]
            })

    valor_base_0 = round(float(bases.get("0", 0)), 2)

    if valor_base_0 > 0:
        items.append({
            "code": ACCOUNT_CODE,
            "description": "Compra no gravada / excluida / cargos / redondeos",
            "quantity": 1,
            "price": valor_base_0,
            "type": "Account"
        })

    return items

def enviar_a_siigo(factura):
    if "error" in factura:
        return 422, {"mensaje": factura["error"]}

    nit_real = factura["proveedor"]["nit"]

    match = re.match(r"([A-Za-z]*)(\d+)", factura["numero_factura"])
    prefijo = match.group(1) if match and match.group(1) else "FC"
    numero = int(match.group(2)) if match else 1

    items = construir_items(factura)
    pago_final = round(float(factura["totales"]["total_xml"]), 2)

    if not items:
        return 422, {
            "mensaje": "No se construyeron ítems para enviar a SIIGO",
            "factura": factura["numero_factura"],
            "bases": factura.get("base", {}),
            "totales": factura.get("totales", {})
        }

    payload = {
        "document": {"id": DOCUMENT_ID},
        "date": factura["fecha"],
        "provider_invoice": {
            "prefix": prefijo,
            "number": numero
        },
        "supplier": {
            "identification": nit_real
        },
        "cost_center": COST_CENTER_ID,
        "items": items,
        "payments": [{
            "id": PAYMENT_ID,
            "value": pago_final,
            "due_date": factura["fecha"]
        }]
    }

    print("\n========== PAYLOAD SIIGO ==========")
    print("Factura:", factura["numero_factura"])
    print("Proveedor:", nit_real)
    print("Bases:", factura.get("base", {}))
    print("Totales:", factura.get("totales", {}))
    print("Items:", items)
    print("Payment:", pago_final)
    print("===================================\n")

    headers = construir_headers()

    res = requests.post(
        SIIGO_URL_PURCHASES,
        json=payload,
        headers=headers,
        timeout=60
    )

    if res.status_code == 400:
        try:
            res_json = res.json()
        except Exception:
            return res.status_code, {"mensaje": res.text}

        errores = obtener_errores_siigo(res_json)

        if any(e.get("code") == "invalid_reference" for e in errores):
            print(f"Proveedor {nit_real} no existe. Creando proveedor...")

            if crear_proveedor_en_siigo(factura, nit_real, headers):
                res = requests.post(
                    SIIGO_URL_PURCHASES,
                    json=payload,
                    headers=headers,
                    timeout=60
                )

    try:
        return res.status_code, res.json()
    except Exception:
        return res.status_code, {"mensaje": res.text}

@app.route("/xml", methods=["POST"])
def recibir_xml():
    try:
        data = request.get_json(silent=True) or {}
        xml_data = data.get("xml", "")

        if not xml_data:
            return jsonify({
                "status": "error",
                "mensaje": "No se recibió XML"
            }), 400

        factura = parsear_factura_xml(xml_data)
        status, respuesta = enviar_a_siigo(factura)

        return jsonify({
            "status": "ok" if status < 300 else "error",
            "siigo": respuesta
        }), status

    except Exception as e:
        print(f"Error procesando petición: {str(e)}")
        return jsonify({
            "status": "error",
            "mensaje": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)