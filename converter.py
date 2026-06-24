import os
import subprocess
import sys
import shutil
import zipfile
import json
import urllib.request
import time
import re
from pathlib import Path

class APKtoAABConverter:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.tools_dir = self.base_dir / "tools"
        self.uploads_dir = self.base_dir / "uploads"
        self.output_dir = self.base_dir / "output"
        self.temp_dir = self.base_dir / "temp"
        
        # Keystore for signing
        self.keystore = self.base_dir / "release.jks"
        self.keystore_pass = "123456"
        self.key_alias = "key0"
        
        # Create directories
        for dir_path in [self.tools_dir, self.uploads_dir, self.output_dir, self.temp_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Tool paths
        self.apktool = self.tools_dir / "apktool.jar"
        self.aapt2 = self.tools_dir / "aapt2"  # Linux version for Render
        self.bundletool = self.tools_dir / "bundletool.jar"
        self.android_jar = self.tools_dir / "android.jar"
        
        # Find Java
        self.java = self._find_java()

    def _find_java(self):
        """Find Java installation"""
        java_paths = [
            "/opt/render/project/src/java/jdk-17.0.12+7/bin/java",
            "/usr/bin/java",
            "java"
        ]
        for path in java_paths:
            try:
                subprocess.run([path, "-version"], capture_output=True, check=True)
                print(f"✅ Java found: {path}")
                return path
            except:
                continue
        print("❌ Java not found!")
        sys.exit(1)

    def download_tools(self):
        """Download required Android tools"""
        print("📦 Downloading Android tools...")
        
        tools = {
            "apktool.jar": "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/windows/apktool.bat",
            "bundletool.jar": "https://github.com/google/bundletool/releases/download/1.18.0/bundletool-all-1.18.0.jar",
            "android.jar": "https://github.com/airwire/android-platforms/raw/main/android-33.jar"
        }
        
        for filename, url in tools.items():
            target_path = self.tools_dir / filename
            if target_path.exists():
                continue
            try:
                urllib.request.urlretrieve(url, target_path)
                print(f"  ✅ Downloaded {filename}")
            except Exception as e:
                print(f"  ❌ Failed to download {filename}: {e}")

    def decompile_apk(self, apk_path, output_dir):
        """Decompile APK using apktool"""
        cmd = [
            self.java, "-jar", str(self.apktool),
            "d", str(apk_path),
            "-o", str(output_dir),
            "-f"
        ]
        self._run_command(cmd)

    def _extract_dex_from_apk(self, apk_path, output_dir):
        """Extract DEX files directly from APK"""
        dex_count = 0
        with zipfile.ZipFile(apk_path, 'r') as apk_zip:
            for file_name in apk_zip.namelist():
                if file_name.endswith('.dex'):
                    apk_zip.extract(file_name, output_dir)
                    dex_count += 1
        return dex_count

    def _fix_public_xml(self, public_xml_path):
        """Remove problematic lines with $ from public.xml"""
        with open(public_xml_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        filtered_lines = [line for line in lines if not ('<public' in line and '$' in line)]
        with open(public_xml_path, 'w', encoding='utf-8') as f:
            f.writelines(filtered_lines)

    def _fix_manifest(self, manifest_path):
        """Fix AndroidManifest.xml"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = re.sub(r'<queries>.*?</queries>', '', content, flags=re.DOTALL)
        content = re.sub(r'<property[^>]*/>', '', content)
        if 'android:hasCode' not in content:
            content = re.sub(r'<application', '<application android:hasCode="true"', content)
        content = '\n'.join(line for line in content.split('\n') if line.strip())
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def compile_resources(self, decompile_dir, output_zip):
        """Compile resources using aapt2"""
        res_dir = decompile_dir / "res"
        
        # Fix public.xml
        public_xml = decompile_dir / "res" / "values" / "public.xml"
        if public_xml.exists():
            self._fix_public_xml(public_xml)
        
        cmd = [
            str(self.aapt2), "compile",
            "--dir", str(res_dir),
            "-o", str(output_zip)
        ]
        self._run_command(cmd)

    def _restructure_zip(self, input_zip, output_zip, decompile_dir):
        """Restructure zip for bundletool"""
        extract_dir = input_zip.parent / "extracted"
        extract_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(input_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            # Manifest
            manifest_src = extract_dir / "AndroidManifest.xml"
            if manifest_src.exists():
                new_zip.write(manifest_src, "manifest/AndroidManifest.xml")
            
            # Res folder
            res_src = extract_dir / "res"
            if res_src.exists():
                for file_path in res_src.rglob('*'):
                    if file_path.is_file():
                        new_zip.write(file_path, str(file_path.relative_to(extract_dir)))
            
            # resources.pb
            resources_pb = extract_dir / "resources.pb"
            if resources_pb.exists():
                new_zip.write(resources_pb, "resources.pb")
            
            # DEX files in dex/ folder
            for dex_file in decompile_dir.glob("*.dex"):
                new_zip.write(dex_file, f"dex/{dex_file.name}")
        
        shutil.rmtree(extract_dir)

    def link_resources(self, decompile_dir, res_zip, output_zip, min_sdk=21, target_sdk=33):
        """Link resources using aapt2"""
        manifest = decompile_dir / "AndroidManifest.xml"
        self._fix_manifest(manifest)
        
        temp_zip = output_zip.parent / "temp_base.zip"
        
        cmd = [
            str(self.aapt2), "link",
            "--proto-format", "-o", str(temp_zip),
            "-I", str(self.android_jar),
            "--manifest", str(manifest),
            f"--min-sdk-version", str(min_sdk),
            f"--target-sdk-version", str(target_sdk),
            "--version-code", "1",
            "--version-name", "1.0",
            "-R", str(res_zip),
            "--auto-add-overlay"
        ]
        
        self._run_command(cmd)
        self._restructure_zip(temp_zip, output_zip, decompile_dir)
        temp_zip.unlink()

    def build_aab(self, base_zip, output_aab):
        """Build AAB using bundletool"""
        cmd = [
            self.java, "-jar", str(self.bundletool),
            "build-bundle",
            "--modules=" + str(base_zip),
            "--output=" + str(output_aab)
        ]
        self._run_command(cmd)

    def build_apks_from_aab(self, aab_path, output_apks=None):
        """✅ Generate APKS from AAB with auto keystore signing"""
        if output_apks is None:
            output_apks = aab_path.parent / f"{aab_path.stem}.apks"
        
        cmd = [
            self.java, "-jar", str(self.bundletool),
            "build-apks",
            "--bundle=" + str(aab_path),
            "--output=" + str(output_apks),
            "--mode=universal"
        ]
        
        # ✅ Sign with keystore if exists
        if self.keystore.exists():
            cmd.extend([
                "--ks=" + str(self.keystore),
                "--ks-pass=pass:" + self.keystore_pass,
                "--ks-key-alias=" + self.key_alias
            ])
            print(f"  Using keystore: {self.keystore}")
        else:
            print("  Using debug keystore")
        
        self._run_command(cmd)
        
        # ✅ Extract universal APK
        extract_dir = output_apks.parent / "universal"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(output_apks, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        universal_apk = extract_dir / "universal.apk"
        if universal_apk.exists():
            print(f"✅ Universal APK: {universal_apk}")
            return universal_apk
        return None

    def _run_command(self, cmd):
        """Run a command with proper environment"""
        cmd_str = " ".join(str(c) for c in cmd)
        print(f"  Running: {cmd_str}")
        
        env = os.environ.copy()
        java_dir = Path(self.java).parent
        env["PATH"] = f"{java_dir}:{env.get('PATH', '')}"
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                env=env
            )
            if result.returncode != 0:
                raise Exception(result.stderr)
            if result.stdout:
                print(f"  Output: {result.stdout[:200]}...")
            return result
        except Exception as e:
            raise Exception(f"Command failed: {e}")

    def convert(self, apk_path, min_sdk=21, target_sdk=33):
        """✅ Main conversion: APK → AAB + APKS (auto)"""
        apk_path = Path(apk_path)
        if not apk_path.exists():
            print(f"❌ APK not found: {apk_path}")
            return None
        
        print(f"\n🚀 Starting conversion for: {apk_path.name}")
        print(f"  Min SDK: {min_sdk}, Target SDK: {target_sdk}")
        
        job_id = str(int(time.time()))
        job_dir = self.temp_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        try:
            # 1. Decompile APK
            decompile_dir = job_dir / "decompiled"
            self.decompile_apk(apk_path, decompile_dir)
            
            # 2. Extract DEX files
            dex_dir = job_dir / "dex"
            dex_dir.mkdir(exist_ok=True)
            self._extract_dex_from_apk(apk_path, dex_dir)
            for dex_file in dex_dir.glob("*.dex"):
                shutil.copy(dex_file, decompile_dir / dex_file.name)
            
            # 3. Compile resources
            res_zip = job_dir / "res.zip"
            self.compile_resources(decompile_dir, res_zip)
            
            # 4. Link resources
            base_zip = job_dir / "base.zip"
            self.link_resources(decompile_dir, res_zip, base_zip, min_sdk, target_sdk)
            
            # 5. Build AAB
            output_filename = apk_path.stem + ".aab"
            output_aab = self.output_dir / output_filename
            self.build_aab(base_zip, output_aab)
            print(f"\n✅ AAB created: {output_aab}")
            
            # 6. ✅ AUTO: Generate APKS from AAB
            print("\n🔧 Generating APKS from AAB...")
            self.build_apks_from_aab(output_aab)
            
            # 7. Clean up
            shutil.rmtree(job_dir)
            
            print(f"\n✅ Conversion complete!")
            print(f"📁 AAB: {output_aab}")
            print(f"📱 APKS: {self.output_dir / f'{output_aab.stem}.apks'}")
            
            return output_aab
            
        except Exception as e:
            print(f"\n❌ Conversion failed: {e}")
            if job_dir.exists():
                shutil.rmtree(job_dir)
            return None