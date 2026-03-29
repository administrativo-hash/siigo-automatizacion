# 🔹 IMPORTS
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml
import requests
import re
import xml.etree.ElementTree as ET
import os

# 🔹 CONFIG SIIGO
SIIGO_URL = "https://api.siigo.com/v1/purchases"
SIIGO_USERNAME = os.environ.get("SIIGO_USERNAME", "administrativo@crewwellness.club")
SIIGO_ACCESS_KEY = os.environ.get("SIIGO_ACCESS_KEY", "")  # ✅ nunca hardcodear

def obtener_token():
    url = "https://api.siigo.com/auth"
    payload = {
    "username": SIIGO_USERNAME,
    "access_key": SIIGO_ACCESS_KEY
}
    response = requests.post(url, json=payload)
    print("AUTH STATUS:", response.status_code)
    print("ACCESS_KEY LEÍDA:", os.environ.get("SIIGO_ACCESS_KEY", "❌ VACÍA")[:10])
    response.raise_for_status()
    return response.json().get("access_token")
    
    # DEBUG TEMPORAL
    print("AUTH STATUS:", response.status_code)
    print("AUTH BODY:", response.text)
    print("ACCESS_KEY LEÍDA:", SIIGO_ACCESS_KEY[:10] if SIIGO_ACCESS_KEY else "❌ VACÍA")
    print("USERNAME LEÍDO:", SIIGO_USERNAME)
    
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise Exception("No se pudo obtener el token de SIIGO")
    return token

def construir_headers():
    token = obtener_token()  # ✅ token fresco en cada ejecución
    return {
        "Authorization": f"Bearer {token}",
        "Username": SIIGO_USERNAME,
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

    invoice_root = ET.fromstring(desc.text.strip()) if desc is not None and desc.text else root

    nit_raw = invoice_root.find(
        './/cac:AccountingSupplierParty//cbc:CompanyID', ns
    ).text.strip()

    # ✅ quitar DV y dejar solo dígitos
    return re.sub(r'\D', '', nit_raw.split('-')[0])


# 🔹 FUNCIÓN PRINCIPAL
def enviar_a_siigo(factura, xml_string):

    nit_real = obtener_nit_desde_xml(xml_string)

    numero_raw = factura.get("numero_factura", "")
    match = re.match(r"([A-Za-z]*)(\d+)", numero_raw)
    prefijo = match.group(1) if match and match.group(1) else "FC"
    numero = int(match.group(2)) if match else 1

    subtotal = round(factura["totales"]["subtotal"], 2)
    iva_total = round(factura["iva_total"], 2)
    

    # 🔹 payment = total (retenciones ya descontadas en el parser)
    payment_correcto = round(subtotal + iva_total, 2)

    print("DEBUG → NIT:", nit_real)
    print("DEBUG → SUBTOTAL (base):", subtotal)
    print("DEBUG → IVA XML:", iva_total)
    print("DEBUG → PAYMENT:", payment_correcto)

    item = {
        "code": "72057201",
        "description": "Compra consolidada",
        "quantity": 1,
        "price": subtotal,  # ✅ base sin IVA
        "type": "Account"
    }
    if iva_total > 0:
        item["taxes"] = [{"id": 8326}]  # ⚠️ validar tax_id en tu cuenta SIIGO

    data = {
        "document": {"id": 15481},
        "date": factura["fecha"],
        "provider_invoice": {
            "prefix": prefijo,
            "number": numero
        },
        "supplier": {
            "identification": nit_real
        },
        "cost_center": 1132,
        "items": [item],
        "payments": [
            {
                "id": 20868,
                "value": payment_correcto,
                "due_date": factura["fecha"]
            }
        ]
    }

    # ✅ token fresco en cada envío
    headers = construir_headers()
    response = requests.post(SIIGO_URL, json=data, headers=headers)

    print("SIIGO STATUS:", response.status_code)
    print("SIIGO RESP:", response.text)

    return response.status_code, response.text


# 🔹 FLASK
app = Flask(__name__)

@app.route('/xml', methods=['POST'])
def recibir_xml():
    data = request.json
    nombre = data.get("nombre", "sin_nombre")
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

@app.route('/debug-env')
def debug_env():
    return jsonify({
        "SIIGO_ACCESS_KEY": os.environ.get("SIIGO_ACCESS_KEY", "❌ NO ENCONTRADA"),
        "SIIGO_USERNAME": os.environ.get("SIIGO_USERNAME", "❌ NO ENCONTRADA")
    })
