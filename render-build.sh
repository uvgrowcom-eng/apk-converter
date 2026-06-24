#!/usr/bin/env bash
set -o errexit

echo "📦 Setting up Java + Python..."

# Java download
mkdir -p java
cd java
wget -q https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.12%2B7/OpenJDK17U-jdk_x64_linux_hotspot_17.0.12_7.tar.gz
tar -xzf OpenJDK17U-jdk_x64_linux_hotspot_17.0.12_7.tar.gz
export JAVA_HOME=$(pwd)/jdk-17.0.12+7
export PATH=$JAVA_HOME/bin:$PATH
cd ..

echo "✅ Java installed:"
java -version

# Tools download
echo "📥 Downloading Android tools..."
mkdir -p tools
cd tools

wget -q -O apktool.jar https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/windows/apktool.bat
wget -q -O bundletool.jar https://github.com/google/bundletool/releases/download/1.16.1/bundletool-all-1.16.1.jar
wget -q -O android.jar https://github.com/airwire/android-platforms/raw/main/android-33.jar

echo "  📥 aapt2 (Linux)..."
wget -q -O aapt2.zip https://dl.google.com/dl/android/maven2/com/android/tools/build/aapt2/7.1.0-7984345/aapt2-7.1.0-7984345-linux.zip
unzip -q aapt2.zip
chmod +x aapt2
rm aapt2.zip

cd ..

echo "✅ Tools ready:"
ls -la tools/

# Python dependencies
pip3 install --upgrade pip
pip3 install -r requirements.txt

echo "✅ Build completed!"