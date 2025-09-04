import re
import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import fugashi
import unidic

app = Flask(__name__)
CORS(app)  # Enable CORS for API access

# Initialize MeCab with UniDic
try:
    tagger = fugashi.Tagger(unidic.DICDIR)
except Exception as e:
    tagger = None
    print("Error: MeCab or dictionary not found.")
    print(e)


def katakana_to_hiragana(katakana_text):
    """Converts Katakana to Hiragana."""
    return ''.join(
        chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c
        for c in katakana_text
    )


def generate_furigana_html(text):
    """Generate HTML with furigana for given Japanese text."""
    if not tagger:
        return "MeCab tagger is not available."

    kanji_pattern = re.compile(r'[\u4e00-\u9faf]')
    parsed_html = ""
    for word in tagger(text):
        surface = word.surface
        reading = katakana_to_hiragana(word.feature.kana or '')
        if kanji_pattern.search(surface) and reading and surface != reading:
            parsed_html += f"<ruby><rb>{surface}</rb><rt>{reading}</rt></ruby>"
        else:
            parsed_html += surface
    return parsed_html


def generate_furigana_json(text):
    """Generate JSON with furigana for given Japanese text."""
    if not tagger:
        return []

    kanji_pattern = re.compile(r'[\u4e00-\u9faf]')
    result = []
    for word in tagger(text):
        surface = word.surface
        reading = katakana_to_hiragana(word.feature.kana or '')
        if kanji_pattern.search(surface) and reading and surface != reading:
            result.append({"word": surface, "furigana": reading})
        else:
            result.append({"word": surface, "furigana": None})
    return result


@app.route('/', methods=['GET', 'POST'])
def index():
    """Web interface for testing furigana."""
    original_text = ""
    furigana_result = ""
    if request.method == 'POST':
        original_text = request.form.get('japanese_text', '')
        if original_text and tagger:
            furigana_result = generate_furigana_html(original_text)
    return render_template('index.html',
                           original_text=original_text,
                           furigana_result=furigana_result)


@app.route('/furigana', methods=['POST'])
def furigana_api():
    """API endpoint for getting furigana as JSON."""
    if not tagger:
        return jsonify({"error": "MeCab tagger not available"}), 500

    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    text = data["text"]
    result = generate_furigana_json(text)
    return jsonify({"result": result})


if __name__ == "__main__":
    # Use the PORT environment variable provided by Render
    port = int(os.environ.get("PORT", 5000))
    # Run Flask without debug mode in production
    app.run(host="0.0.0.0", port=port)
