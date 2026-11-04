"""Editable content overlays; original supplied resources stay unchanged."""
import json

def items(db,kind,base,key='id'):
    data={str(row[key]):dict(row)|{'id':str(row[key])} for row in base}
    for row in db.execute('SELECT id,value FROM content_edits WHERE kind=?',(kind,)):
        value=json.loads(row['value']) if row['value'] else None
        if value is None: data.pop(row['id'],None)
        else: data[row['id']]=data.get(row['id'],{})|value|{'id':row['id']}
    return list(data.values())
