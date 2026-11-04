"""Create the first local administrator without storing a password in source."""
import getpass,uuid
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import db
from server.main import PASSWORD
def main():
    db.init();name=input('Administrator username: ').strip();password=getpass.getpass('Password (hidden): ')
    if not 3<=len(name)<=32 or len(password)<12:raise SystemExit('Use a 3–32 character username and a password of at least 12 characters.')
    with db.connect(True) as d:
        if d.execute('SELECT 1 FROM users WHERE username=?',(name,)).fetchone():raise SystemExit('Username already exists; no changes made.')
        d.execute('INSERT INTO users(id,username,password,nickname,bio,created_at,role) VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,name,PASSWORD.hash(password),name,'',db.now(),'admin'))
    print('Administrator created.')
if __name__=='__main__':main()
