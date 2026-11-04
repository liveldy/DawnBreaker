"""Single-host durable SQLite storage; transactions serialize economy mutations."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone

DATA = Path(os.environ.get('DAWN_DATA_DIR', 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'dawn.db'

def now():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def connect(write=False):
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=30000')
    try:
        if write:
            db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, nickname TEXT NOT NULL, bio TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS installed(user_id TEXT NOT NULL REFERENCES users(id), plugin_id TEXT NOT NULL, installed_at TEXT NOT NULL, PRIMARY KEY(user_id,plugin_id));
        CREATE TABLE IF NOT EXISTS balances(user_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0 CHECK(amount>=0), PRIMARY KEY(user_id,kind));
        CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL, amount INTEGER NOT NULL, reason TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(user_id,kind,source));
        CREATE TABLE IF NOT EXISTS progress(user_id TEXT NOT NULL REFERENCES users(id), plugin_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(user_id,plugin_id,key));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS downloads(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), url TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL, percent REAL DEFAULT 0, filename TEXT, error TEXT, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_user ON events(user_id,kind);
        CREATE INDEX IF NOT EXISTS ledger_user ON ledger(user_id,id);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor_id TEXT NOT NULL,target_id TEXT,action TEXT NOT NULL,before_json TEXT,after_json TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS content_edits(kind TEXT NOT NULL,id TEXT NOT NULL,value TEXT,PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS library_nodes(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),parent_id TEXT,kind TEXT NOT NULL CHECK(kind IN ('folder','document')),title TEXT NOT NULL,markdown TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 1,source_job_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS library_owner ON library_nodes(user_id,parent_id);
        CREATE TABLE IF NOT EXISTS import_jobs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),parent_id TEXT,title TEXT NOT NULL,filename TEXT NOT NULL,mode TEXT NOT NULL,status TEXT NOT NULL,error TEXT,document_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vaults(user_id TEXT PRIMARY KEY REFERENCES users(id),version INTEGER NOT NULL,envelope TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assistants(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),config TEXT NOT NULL,secret TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ai_threads(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),assistant_id TEXT NOT NULL,title TEXT NOT NULL,messages TEXT NOT NULL DEFAULT '[]',summary TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ai_turns(user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,thread_id TEXT NOT NULL,status TEXT NOT NULL,result TEXT,created_at TEXT NOT NULL,PRIMARY KEY(user_id,request_id));
        CREATE TABLE IF NOT EXISTS ai_prompts(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),title TEXT NOT NULL,content TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS listening_segments(user_id TEXT NOT NULL REFERENCES users(id),id TEXT NOT NULL,device_id TEXT NOT NULL,start REAL NOT NULL,end REAL NOT NULL,seconds REAL NOT NULL,credited REAL NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(user_id,id));
        CREATE INDEX IF NOT EXISTS listening_range ON listening_segments(user_id,start,end);
        ''')
        if 'input_hash' not in {r[1] for r in db.execute('PRAGMA table_info(ai_turns)')}:
            db.execute("ALTER TABLE ai_turns ADD COLUMN input_hash TEXT NOT NULL DEFAULT ''")
        for column,default in [('trace','[]'),('reasoning',''),('error','')]:
            if column not in {r[1] for r in db.execute('PRAGMA table_info(ai_turns)')}:
                db.execute("ALTER TABLE ai_turns ADD COLUMN "+column+" TEXT NOT NULL DEFAULT '"+default+"'")
        for table,column in [('ai_threads','archived'),('import_jobs','deleted')]:
            if column not in {r[1] for r in db.execute('PRAGMA table_info('+table+')')}:
                db.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' INTEGER NOT NULL DEFAULT 0')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS quote_schedule(day TEXT PRIMARY KEY,quote_id TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS api_monitors(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),name TEXT NOT NULL,api_base TEXT NOT NULL,secret TEXT NOT NULL,protocol TEXT NOT NULL,report TEXT NOT NULL DEFAULT '{}',updated_at TEXT NOT NULL);
        ''')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS practice_sessions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),mode TEXT NOT NULL,source TEXT NOT NULL,batch_id TEXT,count INTEGER NOT NULL,completed INTEGER NOT NULL DEFAULT 0,correct INTEGER NOT NULL DEFAULT 0,seconds REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'running',started_at TEXT NOT NULL,finished_at TEXT);
        CREATE INDEX IF NOT EXISTS practice_sessions_owner ON practice_sessions(user_id,started_at);
        CREATE TABLE IF NOT EXISTS wallpapers(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),title TEXT NOT NULL,manifest TEXT NOT NULL,filename TEXT NOT NULL,size INTEGER NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL);
        ''')
        for column,sql in [('provider_id',"TEXT NOT NULL DEFAULT 'custom'"),('billing_secret',"TEXT NOT NULL DEFAULT ''")]:
            if column not in {r[1] for r in db.execute('PRAGMA table_info(api_monitors)')}:
                db.execute('ALTER TABLE api_monitors ADD COLUMN '+column+' '+sql)
        if 'role' not in {r[1] for r in db.execute('PRAGMA table_info(users)')}:
            db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin'))")
        if 'avatar' not in {r[1] for r in db.execute('PRAGMA table_info(users)')}:db.execute("ALTER TABLE users ADD COLUMN avatar TEXT NOT NULL DEFAULT ''")
        if 'library_quota_bytes' not in {r[1] for r in db.execute('PRAGMA table_info(users)')}:
            db.execute('ALTER TABLE users ADD COLUMN library_quota_bytes INTEGER NOT NULL DEFAULT 67108864')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS library_images(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),filename TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS library_images_owner ON library_images(user_id);
        CREATE TABLE IF NOT EXISTS checkin_notes(user_id TEXT NOT NULL REFERENCES users(id),day TEXT NOT NULL,content TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(user_id,day));
        CREATE TABLE IF NOT EXISTS quote_history(user_id TEXT NOT NULL REFERENCES users(id),day TEXT NOT NULL,quote_id TEXT NOT NULL,snapshot TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(user_id,day));
        ''')
        # Retired currencies are removed, with no conversion or archive.
        db.execute("DELETE FROM balances WHERE kind IN ('climb','collection')")
        db.execute("DELETE FROM ledger WHERE kind IN ('climb','collection')")
        db.execute('DROP TABLE IF EXISTS retired_balances')
        db.execute("DELETE FROM settings WHERE key='word_climb_reward'")

