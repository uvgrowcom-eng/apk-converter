import os
import time
import shutil
import sys
from pathlib import Path
from flask import Flask, request, render_template, send_file, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

BASE_DIR = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ✅ Import converter
try:
    from converter import APKtoAABConverter
    converter = APKtoAABConverter()
    print("✅ Converter loaded successfully")
except Exception as e:
    print(f"❌ Converter failed to load: {e}")
    converter = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    if converter:
        return jsonify({
            'status': 'OK',
            'tools': {
                'apktool': converter.apktool.exists(),
                'aapt2': converter.aapt2.exists(),
                'bundletool': converter.bundletool.exists(),
                'android_jar': converter.android_jar.exists()
            }
        })
    return jsonify({'status': 'ERROR', 'message': 'Converter not loaded'}), 500

@app.route('/api/convert', methods=['POST'])
def convert():
    try:
        if not converter:
            return jsonify({'error': 'Converter not initialized'}), 500
        
        if 'apk' not in request.files:
            return jsonify({'error': 'No APK file uploaded'}), 400
        
        file = request.files['apk']
        if not file.filename.endswith('.apk'):
            return jsonify({'error': 'Invalid file type. Only APK allowed'}), 400
        
        # ✅ Save APK
        apk_name = f"{int(time.time())}_{secure_filename(file.filename)}"
        apk_path = UPLOADS_DIR / apk_name
        file.save(apk_path)
        print(f"✅ APK saved: {apk_path}")
        
        min_sdk = int(request.form.get('minSdk', 21))
        target_sdk = int(request.form.get('targetSdk', 33))
        print(f"📊 Min SDK: {min_sdk}, Target SDK: {target_sdk}")
        
        # ✅ Convert APK to AAB
        result = converter.convert(apk_path, min_sdk, target_sdk)
        
        # ✅ Clean up uploaded APK
        apk_path.unlink()
        
        if result and result.exists():
            return jsonify({
                'success': True,
                'message': 'Conversion completed!',
                'aab': result.name,
                'download_url': f'/download/{result.name}',
                'size': result.stat().st_size
            })
        else:
            return jsonify({'error': 'Conversion failed - no output file'}), 500
            
    except Exception as e:
        print(f"❌ Conversion error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = OUTPUT_DIR / filename
        if file_path.exists():
            return send_file(file_path, as_attachment=True)
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/apks/<filename>')
def download_apks(filename):
    try:
        # Search in output directory
        for folder in OUTPUT_DIR.iterdir():
            if folder.is_dir():
                file_path = folder / filename
                if file_path.exists():
                    return send_file(file_path, as_attachment=True)
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)