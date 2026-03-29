# 🔹 IMPORTS
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml
import requests
import re
import xml.etree.ElementTree as ET
import os

# 🔹 CONFIG SIIGO
SIIGO_URL = "https://api.siigo.com/v1/purchases"

def obtener_token():
    url = "https://api.siigo.com/auth"
    payload = {
        "username": os.environ.get("SIIGO_USERNAME", "administrativo@crewwellness.club"),
        "access_key": os.environ.get("Nzg2NzVhMzItYzU3OC00NzE0LTlhYmMtOTA1M2JmZmYxNDJhOjRBVDdjVXk3JUs=", "")
    }
    response = requests.post(url, json=payload)
    print("AUTH STATUS:", response.status_code)
    print("ACCESS_KEY LEÍDA:", os.environ.get("SIIGO_ACCES_KEY", "❌ VACÍA")[:10])
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise Exception("No se pudo obtener el token de SIIGO")
    return token

def construir_headers():
    token = obtener_token()
    return {
        "Authorization": f"Bearer {token}",
        "Username": os.environ.get("SIIGO_USERNAME", "administrativo@crewwellness.club"),
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
    payment_correcto = float(factura["totales"]["total_pagar"])

    print("DEBUG → NIT:", nit_real)
    print("DEBUG → SUBTOTAL (base):", subtotal)
    print("DEBUG → IVA XML:", iva_total)
    print("DEBUG → PAYMENT:", payment_correcto)

    # 🔹 CONSTRUCCIÓN DE ITEMS POR TARIFA
    base = factura.get("base", {})
    items = []

    # IVA 19%
    if base.get("19", 0) > 0:
        items.append({
            "code": "72057201",
            "description": "Compra gravada 19%",
            "quantity": 1,
            "price": float(base["19"]),
            "type": "Account",
            "taxes": [{"id": 8326}]
        })

    # IVA 5%
    if base.get("5", 0) > 0:
        items.append({
            "code": "72057201",
            "description": "Compra gravada 5%",
            "quantity": 1,
            "price": float(base["5"]),
            "type": "Account",
            "taxes": [{"id": 8327}]
        })

    # EXCLUIDO / EXENTO
    if base.get("0", 0) > 0:
        items.append({
            "code": "72057201",
            "description": "Compra excluida",
            "quantity": 1,
            "price": float(base["0"]),
            "type": "Account",
            "taxes": [{"id": 14057}]
        })

    # Fallback si base no está definida
    if not items:
        items.append({
            "code": "72057201",
            "description": "Compra consolidada",
            "quantity": 1,
            "price": subtotal,
            "type": "Account",
            **({"taxes": [{"id": 8326}]} if iva_total > 0 else {})
        })

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
        "items": items,
        "payments": [
            {
                "id": 20868,
                "value": payment_correcto,
                "due_date": factura["fecha"]
            }
        ]
    }

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


@app.route('/debug-env')
def debug_env():
    return jsonify({
        "SIIGO_ACCES_KEY": os.environ.get("SIIGO_ACCES_KEY", "❌ NO ENCONTRADA")[:10],
        "SIIGO_USERNAME": os.environ.get("SIIGO_USERNAME", "❌ NO ENCONTRADA")
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

