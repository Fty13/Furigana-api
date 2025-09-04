# app.py
import re
import os
import logging
from flask import Flask, render_template, request, jsonify, make_response
from flask_cors import CORS
import fugashi
import unidic

logging.basicConfig(level=logging.INFO)
app = Flask(__name__, template_folder="templates", static_folder="static")

# Enable CORS globally (safe for this use-case). We'll also add headers in after_request.
CORS(app, resources={r"/furigana": {"origins": "*"}})

# Initialize MeCab with UniDic
try:
    tagger = fugashi.Tagger(unidic.DICDIR)
    logging.info("MeCab Tagger initialized successfully.")
except Exception as e:
    tagger = None
    logging.exception("Failed to initialize MeCab tagger: %s", e)


def katakana_to_hiragana(katakana_text: str) -> str:
    """Convert Katakana string to Hiragana."""
    return ''.join(
        chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c
        for c in (katakana_text or "")
    )


def generate_furigana_html(text: str) -> str:
    """Return HTML string with <ruby> tags for Kanji that have readings."""
    if not tagger:
        return "MeCab tagger is not available."

    kanji_pattern = re.compile(r"[\u4e00-\u9faf]")
    parsed_html = ""
    for word in tagger(text):
        surface = word.surface
        # fugashi's feature.kana gives reading in Katakana (when available)
        reading = katakana_to_hiragana(getattr(word.feature, "kana", "") or "")
        if kanji_pattern.search(surface) and reading and surface != reading:
            parsed_html += f"<ruby><rb>{surface}</rb><rt>{reading}</rt></ruby>"
        else:
            parsed_html += surface
    return parsed_html


@app.route("/", methods=["GET"])
def index():
    """Serve the HTML UI (unchanged)."""
    return render_template("index.html")


@app.route("/furigana", methods=["OPTIONS", "POST", "GET"])
def furigana_api():
    """
    API endpoint:
      - OPTIONS: respond to preflight
      - POST: accept JSON {"text": "..."} OR form data (text / japanese_text)
      - GET: accept ?text=... for quick browser testing
    Returns JSON: {"result": "<ruby>...</ruby>"} or {"error": "..."}
    """
    # Handle preflight explicitly (flask-cors also does this, but it's nice to be explicit)
    if request.method == "OPTIONS":
        resp = make_response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    # Get text from JSON, form, or querystring
    text = ""
    if request.method == "GET":
        text = request.args.get("text", "") or ""
    else:  # POST
        if request.is_json:
            payload = request.get_json(silent=True)
            if isinstance(payload, dict):
                text = payload.get("text", "") or ""
        if not text:
            # fallback to form fields (useful if someone sends form-encoded body)
            text = request.form.get("text") or request.form.get("japanese_text") or ""

    if not text:
        return jsonify({"error": "Missing 'text'"}), 400

    if not tagger:
        return jsonify({"error": "MeCab tagger not available on server"}), 500

    try:
        result_html = generate_furigana_html(text)
        return jsonify({"result": result_html})
    except Exception as e:
        logging.exception("Error while generating furigana: %s", e)
        return jsonify({"error": "Internal error"}), 500


@app.after_request
def _add_cors_headers(response):
    """
    Add permissive CORS headers to every response.
    This ensures chrome-extension:// origins and others receive Access-Control-Allow-Origin.
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
