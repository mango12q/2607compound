from PIL import Image
import os

base = r"E:\2607compound\pdf_extract"
files = sorted([f for f in os.listdir(base) if f.endswith('.png')])
for f in files:
    path = os.path.join(base, f)
    im = Image.open(path)
    print(f"{f}: {im.size}, mode={im.mode}, {os.path.getsize(path)} bytes")
