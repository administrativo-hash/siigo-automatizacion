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
    base = factura["base"]
    
    config_impuestos = [
        ("19", 8326, 0.19),  # IVA 19%
        ("5", 8327, 0.05),   # IVA 5%
        ("8", 8341, 0.08),   # INC 8%
        ("0", 14057, 0.0)    # Exento
    ]
    
    for t_nombre, tax_id, factor in config_impuestos:
        valor_base = float(base.get(t_nombre, 0))
        if valor_base > 0:
            items.append({
                "code": "72057201",
                "description": f"Compra gravada {t_nombre}%",
                "quantity": 1,
                "price": round(valor_base, 2),
                "type": "Account",
                "taxes": [{"id": tax_id}]
            })

    # Valor inicial desde el XML
    pago_final = round(float(factura["totales"]["total_xml"]), 2)
    
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
    
    # --- PRIMER INTENTO ---
    res = requests.post(SIIGO_URL_PURCHASES, json=payload, headers=headers, timeout=20)
    
    # --- SOLUCIÓN DINÁMICA PARA DIFERENCIA DE DECIMALES ---
    if res.status_code == 400:
        res_json = res.json()
        # Siigo anida los errores en la llave 'siigo'
        errores = res_json.get("siigo", {}).get("errors", [])
        if not errores: errores = res_json.get("errors", []) # Por si cambia el formato
        
        for error in errores:
            if error.get("code") == "invalid_total_payments":
                mensaje_error = error.get("message", "")
                # Buscamos el valor calculado por Siigo al final del mensaje (ej: 717800.02)
                match_decimal = re.search(r"(\d+\.\d+)$", mensaje_error)
                if match_decimal:
                    nuevo_valor = float(match_decimal.group(1))
                    print(f"Ajuste de centavos detectado: Cambiando {pago_final} por {nuevo_valor}")
                    payload["payments"][0]["value"] = nuevo_valor
                    # Reintento con el valor que Siigo exige
                    res = requests.post(SIIGO_URL_PURCHASES, json=payload, headers=headers, timeout=20)
                    break

    # --- MANEJO DE PROVEEDOR NUEVO (Si el error persiste o es nuevo) ---
    if res.status_code == 400:
        res_json = res.json()
        errores = res_json.get("siigo", {}).get("errors", [])
        if not errores: errores = res_json.get("errors", [])
        
        if any(e.get("code") == "invalid_reference" for e in errores):
            print(f"Proveedor {nit_real} no existe. Creando...")
            if crear_proveedor_en_siigo(factura, nit_real, headers):
                # Reintento final después de crear el proveedor
                res = requests.post(SIIGO_URL_PURCHASES, json=payload, headers=headers, timeout=20)
    
    return res.status_code, res.json()

@app.route('/xml', methods=['POST'])
def recibir_xml():
    try:
        xml_data = request.json.get("xml", "")
        if not xml_data:
            return jsonify({"status": "error", "mensaje": "No se recibió XML"}), 400
            
        factura = parsear_factura_xml(xml_data)
        status, respuesta = enviar_a_siigo(factura)
        return jsonify({"status": "ok" if status < 300 else "error", "siigo": respuesta}), status
    except Exception as e:
        print(f"Error procesando petición: {str(e)}")
        return jsonify({"status": "error", "mensaje": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)