from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuración
MAX_TEXT_LENGTH = 10000
CLIPBOARD_FILE = 'clipboard_data.json'

# Inicializar datos
def load_clipboard_data():
    """Cargar datos del portapapeles desde archivo"""
    try:
        if os.path.exists(CLIPBOARD_FILE):
            with open(CLIPBOARD_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"text": "", "last_updated": None}
    except Exception as e:
        logger.error(f"Error cargando datos: {e}")
        return {"text": "", "last_updated": None}

def save_clipboard_data(data):
    """Guardar datos del portapapeles en archivo"""
    try:
        with open(CLIPBOARD_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error guardando datos: {e}")
        return False

# Cargar datos iniciales
clipboard_data = load_clipboard_data()

@app.route("/", methods=["GET"])
def home():
    """Endpoint de información de la API"""
    return jsonify({
        "message": "Clipboard API funcionando",
        "version": "2.0",
        "endpoints": {
            "GET /clipboard": "Obtener texto del portapapeles",
            "POST /clipboard": "Guardar texto en el portapapeles",
            "GET /status": "Estado de la API"
        }
    })

@app.route("/clipboard", methods=["GET"])
def get_clipboard():
    """Obtener el texto del portapapeles"""
    try:
        return jsonify({
            "text": clipboard_data.get("text", ""),
            "last_updated": clipboard_data.get("last_updated"),
            "length": len(clipboard_data.get("text", ""))
        })
    except Exception as e:
        logger.error(f"Error obteniendo clipboard: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route("/clipboard", methods=["POST"])
def set_clipboard():
    """Guardar texto en el portapapeles"""
    try:
        # Validar contenido JSON
        if not request.is_json:
            return jsonify({"error": "Contenido debe ser JSON"}), 400
        
        data = request.get_json()
        
        if not data or "text" not in data:
            return jsonify({"error": "Campo 'text' es requerido"}), 400
        
        text = data["text"]
        
        # Validar tipo de datos
        if not isinstance(text, str):
            return jsonify({"error": "El texto debe ser una cadena"}), 400
        
        # Validar longitud
        if len(text) > MAX_TEXT_LENGTH:
            return jsonify({
                "error": f"Texto demasiado largo. Máximo {MAX_TEXT_LENGTH} caracteres"
            }), 400
        
        # Actualizar datos
        clipboard_data["text"] = text
        clipboard_data["last_updated"] = datetime.now().isoformat()
        
        # Guardar en archivo
        if save_clipboard_data(clipboard_data):
            logger.info(f"Texto guardado: {len(text)} caracteres")
            return jsonify({
                "status": "success",
                "message": "Texto guardado exitosamente",
                "length": len(text),
                "timestamp": clipboard_data["last_updated"]
            })
        else:
            return jsonify({"error": "Error guardando datos"}), 500
            
    except Exception as e:
        logger.error(f"Error guardando clipboard: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route("/status", methods=["GET"])
def get_status():
    """Obtener el estado de la API"""
    return jsonify({
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "clipboard_length": len(clipboard_data.get("text", "")),
        "last_updated": clipboard_data.get("last_updated"),
        "max_length": MAX_TEXT_LENGTH
    })

@app.route("/clear", methods=["POST"])
def clear_clipboard():
    """Limpiar el portapapeles"""
    try:
        clipboard_data["text"] = ""
        clipboard_data["last_updated"] = datetime.now().isoformat()
        
        if save_clipboard_data(clipboard_data):
            logger.info("Portapapeles limpiado")
            return jsonify({
                "status": "success",
                "message": "Portapapeles limpiado exitosamente"
            })
        else:
            return jsonify({"error": "Error limpiando datos"}), 500
            
    except Exception as e:
        logger.error(f"Error limpiando clipboard: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint no encontrado"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Método no permitido"}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "False").lower() == "true"
    
    logger.info(f"Iniciando servidor en puerto {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
