# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

clipboard_data = {"text": ""}

@app.route("/clipboard", methods=["GET"])
def get_clipboard():
    return jsonify(clipboard_data)

@app.route("/clipboard", methods=["POST"])
def set_clipboard():
    data = request.get_json()
    clipboard_data["text"] = data.get("text", "")
    return jsonify({"status": "ok"})
