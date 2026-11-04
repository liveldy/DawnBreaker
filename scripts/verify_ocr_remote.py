from pathlib import Path
import shlex
from remote import connection
from deploy import command
R=Path(__file__).resolve().parents[1]
with connection() as ssh:
    command(ssh,'mkdir -p /var/lib/dawnbreaker/ocr-verification && chown dawnbreaker:dawnbreaker /var/lib/dawnbreaker/ocr-verification')
    with ssh.open_sftp() as sftp:sftp.put(str(R/'server/ocr_worker.py'),'/var/lib/dawnbreaker/ocr-verification/ocr_worker.py')
    make="import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as p;p.figure(figsize=(6,2));p.text(.2,.4,r'$E=mc^2$',fontsize=48);p.axis('off');p.savefig('/var/lib/dawnbreaker/ocr-verification/formula.png',bbox_inches='tight',facecolor='white')"
    command(ssh,'env MPLCONFIGDIR=/var/lib/dawnbreaker/model-cache/matplotlib /opt/dawnbreaker/ocr-venv/bin/python -c '+shlex.quote(make),timeout=120)
    command(ssh,'chown -R dawnbreaker:dawnbreaker /var/lib/dawnbreaker/ocr-verification /var/lib/dawnbreaker/model-cache && runuser -u dawnbreaker -- /opt/dawnbreaker/ocr-venv/bin/python /var/lib/dawnbreaker/ocr-verification/ocr_worker.py /var/lib/dawnbreaker/ocr-verification/formula.png /var/lib/dawnbreaker/ocr-verification/result.json formula',timeout=1800)
    code="import json;d=json.load(open('/var/lib/dawnbreaker/ocr-verification/result.json'));print(d['markdown']);assert '$$' in d['markdown'] and 'E' in d['markdown'] and 'c' in d['markdown']"
    command(ssh,'/opt/dawnbreaker/ocr-venv/bin/python -c '+shlex.quote(code))
print('PASS: actual CPU formula OCR produced LaTeX',flush=True)
