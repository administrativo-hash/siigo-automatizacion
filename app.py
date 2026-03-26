# app.py
from flask import Flask, request, jsonify
from parser_xml import parsear_factura_xml

app = Flask(__name__)

@app.route('/xml', methods=['POST'])
def recibir_xml():
    data = request.json
    nombre = data.get("nombre", "sin_nombre")
    xml_string = data.get("xml", "")

    try:
        factura = parsear_factura_xml(xml_string)
        print(f"✅ Parseado: {factura['numero_factura']} | "
              f"Proveedor: {factura['proveedor']['nombre']} | "
              f"Total: ${factura['totales']['total_pagar']:,.0f} | "
              f"Líneas: {len(factura['lineas'])}")
        return jsonify({"status": "ok", "factura": factura}), 200
    except Exception as e:
        print(f"❌ Error procesando {nombre}: {e}")
        return jsonify({"status": "error", "mensaje": str(e)}), 400

@app.route('/')
def home():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)