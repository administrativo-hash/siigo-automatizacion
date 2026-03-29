# ==========================================
# 🔹 AUTOMATIZACIÓN SIIGO NUBE - CREW WELLNESS
# 🔹 Versión: 3.0 (Full Auto-Recovery & Idempotency)
# ==========================================

from flask import Flask, request, jsonify
import requests
import re
import xml.etree.ElementTree as ET
import os
from parser_xml import parsear_factura_xml

app = Flask(__name__)

# 🔹 CONFIGURACIÓN
SIIGO_URL_PURCHASES = "https://api.siigo.com/v1/purchases"
SIIGO_URL_CUSTOMERS = "https://api.siigo.com/v1/customers"
AUTH_URL = "https://api.siigo.com/auth"

# Credenciales (Se recomienda usar variables de entorno en producción)
USERNAME = "administrativo@crewwellness.club"
ACCESS_KEY = "YTE0YWRlOWYtZTA3MC00NGIyLWJiMDMtOTlmZDU0YTkyOWIzOjw2a3gyVTwsVk4="

# ==========================================
# 🔹 FUNCIONES DE APOYO (AUTH & HEADERS)
# ==========================================

def obtener_token():
    payload = {
        "username": USERNAME,
        "access_key": ACCESS_KEY
    }
    try:
        response = requests.post(AUTH_URL, json=payload, timeout=10)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise Exception("Token no encontrado en la respuesta")
        return token
    except Exception as e:
        print(f"❌ Error crítico de autenticación: {e}")
        raise

def construir_headers():
    token = obtener_token()
    return {
        "Authorization": f"Bearer {token}",
        "Username": USERNAME,
        "Content-Type": "application/json",
        "Partner-Id": "CrewWellnessAPI"
    }

# ==========================================
# 🔹 LÓGICA DE PROVEEDORES (CUSTOMERS)
# ==========================================

def crear_proveedor_en_siigo(factura, nit_real, headers):
    """ Crea el proveedor si no existe, detectando si es Persona o Empresa. """
    nombre = factura["proveedor"]["nombre"]
    
    # Lógica DIAN: NIT empresa = 9 dígitos (Tipo 31). Cédula > 9 (Tipo 13).
    es_empresa = len(nit_real) == 9
    person_type = "Company" if es_empresa else "Person"
    id_type_code = "31" if es_empresa else "13"

    payload = {
        "type": "Supplier",
        "person_type": person_type,
        "id_type": {"code": id_type_code},
        "identification": nit_real,
        "name": [nombre],
        "address": {
            "address": "No informado",
            "city": {"country_code": "Co", "state_code": "11", "city_code": "11001"}
        },
        "phones": [{"number": "0000000"}],
        "contacts": [{
            "first_name": nombre,
            "last_name": "Procesado API",
            "email": "sin-email@crewwellness.club",
            "phone": {"number": "0000000"}
        }],
        "fiscal_responsibilities": [{"code": "R-99-PN"}],
        "vat_responsible": False
    }

    try:
        res = requests.post(SIIGO_URL_CUSTOMERS, json=payload, headers=headers, timeout=15)
        if res.status_code in [200, 201]:
            print(f"✅ Proveedor {nit_real} ({nombre}) creado exitosamente.")
            return True
        print(f"❌ Error al crear proveedor {nit_real}: {res.text}")
        return False
    except Exception as e:
        print(f"❌ Excepción en creación de proveedor: {e}")
        return False

# ==========================================
# 🔹 EXTRACCIÓN Y PROCESAMIENTO
# ==========================================

def obtener_nit_desde_xml(xml_string):
    """ Extrae el NIT limpio sin DV desde el XML de la DIAN. """
    ns = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }
    root = ET.fromstring(xml_string.strip())
    desc = root.find('.//cac:Attachment/cac:ExternalReference/cbc:Description', ns)
    invoice_root = ET.fromstring(desc.text.strip()) if desc is not None and desc.text else root
    nit_raw = invoice_root.find('.//cac:AccountingSupplierParty//cbc:CompanyID', ns).text.strip()
    return re.sub(r'\D', '', nit_raw.split('-')[0])

def enviar_a_siigo(factura, xml_string):
    """ Función principal con reintento y control de duplicidad. """
    nit_real = obtener_nit_desde_xml(xml_string)
    
    # Manejo de Prefijo y Número
    numero_raw = factura.get("numero_factura", "")
    match = re.match(r"([A-Za-z]*)(\d+)", numero_raw)
    prefijo = match.group(1) if match and match.group(1) else "FC"
    numero = int(match.group(2)) if match else 1
    
    # Cálculo de Totales e Items
    base = factura.get("base", {})
    payment_correcto = round(
        (float(base.get("19", 0)) * 1.19) + 
        (float(base.get("5", 0)) * 1.05) + 
        float(base.get("0", 0)), 2
    )

    items = []
    tarifas = [("19", 8326, "19%"), ("5", 8327, "5%"), ("0", 14057, "excluida")]
    for tarifa, tax_id, desc in tarifas:
        if base.get(tarifa, 0) > 0:
            items.append({
                "code": "72057201", # Ajustar según tu catálogo de Siigo
                "description": f"Compra gravada {desc}",
                "quantity": 1,
                "price": float(base[tarifa]),
                "type": "Account",
                "taxes": [{"id": tax_id}]
            })

    # Si por alguna razón no hay items, enviamos fallback
    if not items:
        items.append({
            "code": "72057201",
            "description": "Compra consolidada",
            "quantity": 1,
            "price": round(factura["totales"]["subtotal"], 2),
            "type": "Account"
        })

    payload_compra = {
        "document": {"id": 15481},
        "date": factura["fecha"],
        "provider_invoice": {"prefix": prefijo, "number": numero},
        "supplier": {"identification": nit_real},
        "cost_center": 1132,
        "items": items,
        "payments": [{"id": 20868, "value": payment_correcto, "due_date": factura["fecha"]}]
    }

    headers = construir_headers()
    
    # --- PRIMER INTENTO ---
    print(f"🚀 Enviando factura {prefijo}{numero} de {nit_real}...")
    response = requests.post(SIIGO_URL_PURCHASES, json=payload_compra, headers=headers, timeout=20)

    # --- LÓGICA DE CONTROL (400 Bad Request) ---
    if response.status_code == 400:
        try:
            res_json = response.json()
            errores = res_json.get("errors", [])
            
            # 1. ¿El proveedor no existe?
            proveedor_no_existe = any(
                e.get("code") == "invalid_reference" and "supplier" in str(e.get("params")) 
                for e in errores
            )

            if proveedor_no_existe:
                print(f"⚠️ Proveedor {nit_real} no existe. Iniciando creación...")
                if crear_proveedor_en_siigo(factura, nit_real, headers):
                    print("🔄 Reintentando envío de la factura...")
                    response = requests.post(SIIGO_URL_PURCHASES, json=payload_compra, headers=headers, timeout=20)
                    return response.status_code, response.text
            
            # 2. ¿La factura ya existe? (Idempotencia)
            documento_duplicado = any(
                "already exists" in e.get("message", "").lower() or 
                e.get("code") == "already_exists" 
                for e in errores
            )

            if documento_duplicado:
                print(f"ℹ️ Factura {prefijo}{numero} ya estaba en Siigo. No se duplicará.")
                return 200, {"mensaje": "Documento ya registrado previamente"}

        except Exception as e:
            print(f"❌ Error parseando respuesta de error: {e}")

    return response.status_code, response.text

# ==========================================
# 🔹 ENDPOINTS FLASK
# ==========================================

@app.route('/xml', methods=['POST'])
def recibir_xml():
    data = request.json
    if not data or "xml" not in data:
        return jsonify({"status": "error", "mensaje": "Falta el campo XML"}), 400
    
    nombre_archivo = data.get("nombre", "desconocido")
    xml_content = data.get("xml", "").strip()

    try:
        # Parseo de datos desde el XML usando tu parser existente
        factura = parsear_factura_xml(xml_content)
        
        # Envío a Siigo con toda la lógica de autorrecuperación
        status, respuesta = enviar_a_siigo(factura, xml_content)

        return jsonify({
            "status": "ok" if status in [200, 201] else "error",
            "archivo": nombre_archivo,
            "siigo_status": status,
            "siigo_response": respuesta
        }), status

    except Exception as e:
        print(f"❌ Error procesando {nombre_archivo}: {e}")
        return jsonify({"status": "error", "mensaje": str(e)}), 500

@app.route('/')
def health_check():
    return "🚀 Siigo Automation Server is Running", 200

if __name__ == "__main__":
    # En producción usar Gunicorn o similar
    app.run(host="0.0.0.0", port=5000, debug=True)