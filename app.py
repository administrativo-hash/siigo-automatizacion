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
ACCESS_KEY = "YTE0YWRlOWYtZTA3MC00NGIyLWJiMDMtOTlmZDU0YTkyOWIzOjw2a3gyVTwsVk4="

def obtener_token():
    res = requests.post(AUTH_URL, json={"username": USERNAME, "access_key": ACCESS_KEY}, timeout=10)
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
        "address": {"address": "No informado", "city": {"country_code": "Co", "state_code": "11", "city_code": "11001"}},
        "phones": [{"number": "0000000"}],
        "contacts": [{"first_name": nombre, "last_name": "API", "email": "administrativo@crewwellness.club"}],
        "fiscal_responsibilities": [{"code": "R-99-PN"}],
        "vat_responsible": False
    }
    res = requests.post(SIIGO_URL_CUSTOMERS, json=payload, headers=headers, timeout=15)
    return res.status_code in [200, 201]

def enviar_a_siigo(factura):
    if "error" in factura: return 422, {"mensaje": factura["error"]}

    nit_real = factura["proveedor"]["nit"]
    match = re.match(r"([A-Za-z]*)(\d+)", factura["numero_factura"])
    prefijo = match.group(1) if match and match.group(1) else "FC"
    numero = int(match.group(2)) if match else 1
    
    items = []
    # Usamos el subtotal y el iva_total que el parser ya extrajo correctamente del XML
    subtotal_total = factura["totales"]["subtotal"]
    iva_total = factura.get("iva_total", 0) # El parser ya suma todos los impuestos aquí
    
    # Creamos un único ítem con el subtotal global para evitar líos de redondeo por línea
    items.append({
        "code": "72057201",
        "description": "Compra de bienes y servicios (Procesado por API)",
        "quantity": 1,
        "price": subtotal_total,
        "type": "Account",
        "taxes": [{"id": 8326}] # Usamos el ID de IVA 19% como estándar o el que prefieras
    })

    # IMPORTANTE: El pago debe ser la suma exacta de lo que Siigo calculará internamente.
    # Como Siigo aplica el impuesto al "price", recalculamos el pago final:
    pago_final = round(subtotal_total + iva_total, 2)

    payload = {
        "document": {"id": 15481},
        "date": factura["fecha"],
        "provider_invoice": {"prefix": prefijo, "number": numero},
        "supplier": {"identification": nit_real},
        "cost_center": 1132,
        "items": items,
        "payments": [{"id": 20868, "value": pago_final, "due_date": factura["fecha"]}]
    }

    headers = construir_headers()
    res = requests.post(SIIGO_URL_PURCHASES, json=payload, headers=headers, timeout=20)
    
    # ... (lógica de reintento por proveedor nuevo se mantiene igual)
    if res.status_code == 400:
        if any(e.get("code") == "invalid_reference" for e in res.json().get("errors", [])):
            if crear_proveedor_en_siigo(factura, nit_real, headers):
                res = requests.post(SIIGO_URL_PURCHASES, json=payload, headers=headers, timeout=20)
    
    return res.status_code, res.json()

@app.route('/xml', methods=['POST'])
def recibir_xml():
    try:
        factura = parsear_factura_xml(request.json.get("xml", ""))
        status, respuesta = enviar_a_siigo(factura)
        return jsonify({"status": "ok" if status < 300 else "error", "siigo": respuesta}), status
    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)