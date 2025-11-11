🧠 FFmpeg & Tesseract OCR Setup Guide
🎥 FFmpeg Integration

Purpose:
FFmpeg is used for handling video/audio processing — like extracting frames, converting formats, or generating thumbnails.

🔧 Installation:

Windows:

Download the latest FFmpeg build from https://www.gyan.dev/ffmpeg/builds/

Extract the ZIP (e.g., ffmpeg-master-latest-win64-gpl-shared.zip).

Move the extracted folder to a safe location (e.g., C:\ffmpeg).

Add FFmpeg to your PATH:

Open System Properties → Environment Variables.

Under System Variables, edit Path → click New → add:

C:\ffmpeg\bin


Verify installation:

ffmpeg -version

Linux/macOS:
sudo apt update
sudo apt install ffmpeg -y
# or for macOS
brew install ffmpeg

📝 Tesseract OCR Integration

Purpose:
Tesseract OCR converts images or frames into readable text — often used for document scanning or text recognition.

🔧 Installation:

Windows:

Download the Windows installer from:
https://github.com/UB-Mannheim/tesseract/wiki

Run the installer and note the installation path (e.g.,
C:\Program Files\Tesseract-OCR).

Add it to your PATH environment variable.

Verify:

tesseract -v

Linux/macOS:
sudo apt update
sudo apt install tesseract-ocr -y
# or for macOS
brew install tesseract

🧩 Python Integration

If your project uses Python, install the wrappers:

pip install pytesseract
pip install opencv-python


Set path in your code (Windows example):

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
