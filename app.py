import os
import time
import shutil
from pathlib import Path
from flask import Flask, request, render_template, send_file, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from converter import APKtoAABConverter

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

BASE_DIR = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

converter = APKtoAABConverter()

if not (converter.tools_dir / "bundletool.jar").exists():
    converter.download_tools()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({
        'status': 'OK',
        'tools': {
            'apktool': converter.apktool.exists(),
            'aapt2': converter.aapt2.exists(),
            'bundletool': converter.bundletool.exists(),
            'android_jar': converter.android_jar.exists()
        }
    })

@app.route('/api/convert', methods=['POST'])
def convert():
    try:
        if 'apk' not in request.files:
            return jsonify({'error': 'No APK file'}), 400
        
        file = request.files['apk']
        if not file.filename.endswith('.apk'):
            return jsonify({'error': 'Invalid file type'}), 400
        
        apk_name = f"{int(time.time())}_{secure_filename(file.filename)}"
        apk_path = UPLOADS_DIR / apk_name
        file.save(apk_path)
        
        min_sdk = int(request.form.get('minSdk', 21))
        target_sdk = int(request.form.get('targetSdk', 33))
        
        result = converter.convert(apk_path, min_sdk, target_sdk)
        
        apk_path.unlink()
        
        if result:
            return jsonify({
                'success': True,
                'aab': result.name,
                'download_url': f'/download/{result.name}',
                'size': result.stat().st_size
            })
        else:
            return jsonify({'error': 'Conversion failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)