from flask import Flask, request, jsonify
import requests
import re
import xml.etree.ElementTree as ET
from parser_xml import parsear_factura_xml

app = Flask(__name__)

# CONFIGURACIÓN
SIIGO_URL_PURCHASES = "https://api.siigo.com/v1/purchases"
SIIGO_URL_CUSTOMERS = "https://api.siigo.com/v1/customers"
AUTH_URL = "https://api.siigo.com/auth"
USERNAME = "administrativo@crewwellness.club"
ACCESS_KEY = "YTE0YWRlOWYtZTA3MC00NGIyLWJiMDMtOTlmZDU0YTkyOWIzOjw2a3gyVTwsVk4="

def obtener_token():
    payload = {"username": USERNAME, "access_key": ACCESS_KEY}
    res = requests.post(AUTH_URL, json=payload, timeout=10)
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

def enviar_a_siigo(factura, xml_string):
    # ... (obtención de nit, prefijo, numero igual)

    items = []
    base = factura["base"]
    # Definimos las tarifas y sus factores decimales
    tarifas = [("19", 8326, 0.19), ("5", 8327, 0.05), ("0", 14057, 0.0)]
    
    total_para_el_pago = 0
    
    for tarifa_str, tax_id, factor in tarifas:
        valor_base = float(base.get(tarifa_str, 0))
        if valor_base > 0:
            # Calculamos el IVA de esta agrupación
            iva_de_esta_tarifa = round(valor_base * factor, 2)
            # Sumamos al total que enviaremos en el nodo 'payments'
            total_para_el_pago += (valor_base + iva_de_esta_tarifa)
            
            items.append({
                "code": "72057201",
                "description": f"Compra gravada {tarifa_str}%",
                "quantity": 1,
                "price": valor_base,
                "type": "Account",
                "taxes": [{"id": tax_id}]
            })

    # Sincronización final: El pago es la suma exacta de nuestros items
    pago_final = round(total_para_el_pago, 2)

    payload_compra = {
        "document": {"id": 15481},
        "date": factura["fecha"],
        "provider_invoice": {"prefix": prefijo, "number": numero},
        "supplier": {"identification": nit_real},
        "cost_center": 1132,
        "items": items,
        "payments": [{
            "id": 20868, 
            "value": pago_final, # <--- Esto garantiza que la resta sea CERO
            "due_date": factura["fecha"]
        }]
    }
    
      

    headers = construir_headers()
    res = requests.post(SIIGO_URL_PURCHASES, json=payload_compra, headers=headers, timeout=20)

    if res.status_code == 400:
        res_json = res.json()
        errores = res_json.get("errors", [])
        if any(e.get("code") == "invalid_reference" for e in errores):
            if crear_proveedor_en_siigo(factura, nit_real, headers):
                res = requests.post(SIIGO_URL_PURCHASES, json=payload_compra, headers=headers, timeout=20)
        if any("already exists" in e.get("message", "").lower() for e in errores):
            return 200, {"mensaje": "Duplicado"}

    return res.status_code, res.json()

@app.route('/xml', methods=['POST'])
def recibir_xml():
    data = request.json
    try:
        factura = parsear_factura_xml(data.get("xml", ""))
        status, respuesta = enviar_a_siigo(factura, data.get("xml", ""))
        return jsonify({"status": "ok" if status < 300 else "error", "siigo": respuesta}), status
    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)