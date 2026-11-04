"""Install free CPU-only Pix2Text in a separate environment; no CUDA or API keys."""
from remote import connection
from deploy import command
with connection() as ssh:
    command(ssh,'python3 -m venv /opt/dawnbreaker/ocr-venv && /opt/dawnbreaker/ocr-venv/bin/pip install -q --upgrade pip',timeout=300)
    command(ssh,'/opt/dawnbreaker/ocr-venv/bin/pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu',timeout=1200)
    command(ssh,'/opt/dawnbreaker/ocr-venv/bin/pip install --no-cache-dir pix2text==1.1.7 rapidocr==3.9.2 PyMuPDF==1.26.7',timeout=1200)
    command(ssh,'mkdir -p /var/lib/dawnbreaker/model-cache && chown dawnbreaker:dawnbreaker /var/lib/dawnbreaker/model-cache && chmod 700 /var/lib/dawnbreaker/model-cache')
print('CPU OCR environment installed',flush=True)
