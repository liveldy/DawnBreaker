"""Global configuration overrides. Defaults remain in the owning plugins."""
import json

def setting(db,key,default):
    row=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else default
