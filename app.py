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

# ✅ Import converter with options
try:
    from converter import APKtoAABConverter
    converter = APKtoAABConverter(compression_level=9, keep_temp=False)
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
        generate_apks = request.form.get('generateApks', 'true').lower() == 'true'
        print(f"📊 Min SDK: {min_sdk}, Target SDK: {target_sdk}")
        print(f"📱 Generate APKS: {generate_apks}")
        
        # ✅ Convert APK to AAB
        result = converter.convert(apk_path, min_sdk, target_sdk, generate_apks)
        
        # ✅ Clean up uploaded APK
        apk_path.unlink()
        
        if result and result.exists():
            # ✅ Check if APKS was also generated
            apks_path = result.parent / f"{result.stem}.apks"
            apks_download_url = f'/download/apks/{apks_path.name}' if apks_path.exists() else None
            
            return jsonify({
                'success': True,
                'message': 'Conversion completed!',
                'aab': result.name,
                'download_url': f'/download/{result.name}',
                'apks': apks_path.name if apks_path.exists() else None,
                'apks_download_url': apks_download_url,
                'size': result.stat().st_size,
                'timestamp': time.time()
            })
        else:
            return jsonify({'error': 'Conversion failed - no output file'}), 500
            
    except Exception as e:
        print(f"❌ Conversion error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/batch', methods=['POST'])
def batch_convert():
    """✅ Batch conversion endpoint"""
    try:
        if not converter:
            return jsonify({'error': 'Converter not initialized'}), 500
        
        if 'apks' not in request.files:
            return jsonify({'error': 'No APK files uploaded'}), 400
        
        files = request.files.getlist('apks')
        if not files:
            return jsonify({'error': 'No files selected'}), 400
        
        min_sdk = int(request.form.get('minSdk', 21))
        target_sdk = int(request.form.get('targetSdk', 33))
        
        results = []
        apk_paths = []
        
        for file in files:
            if not file.filename.endswith('.apk'):
                continue
            apk_name = f"{int(time.time())}_{secure_filename(file.filename)}"
            apk_path = UPLOADS_DIR / apk_name
            file.save(apk_path)
            apk_paths.append(apk_path)
            results.append({'apk': file.filename, 'status': 'pending'})
        
        # ✅ Convert all
        for i, apk_path in enumerate(apk_paths):
            try:
                result = converter.convert(apk_path, min_sdk, target_sdk, True)
                results[i]['status'] = 'success' if result else 'failed'
                results[i]['aab'] = result.name if result else None
                apk_path.unlink()
            except Exception as e:
                results[i]['status'] = 'error'
                results[i]['error'] = str(e)
                apk_path.unlink()
        
        return jsonify({
            'success': True,
            'message': 'Batch conversion completed!',
            'results': results,
            'total': len(results),
            'successful': sum(1 for r in results if r['status'] == 'success')
        })
        
    except Exception as e:
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
        file_path = OUTPUT_DIR / filename
        if file_path.exists():
            return send_file(file_path, as_attachment=True)
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)