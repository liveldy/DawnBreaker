"""Install distribution-maintained, open-source Word readers; no OCR/API account required."""
from remote import connection
from deploy import command
with connection() as ssh:
    command(ssh,'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends pandoc libreoffice-writer-nogui libreoffice-math-nogui',timeout=900)
    command(ssh,'pandoc --version | head -n 1; libreoffice --headless --version')
print('Pandoc and LibreOffice Word conversion ready',flush=True)
