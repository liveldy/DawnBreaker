"""Cross-plugin counters, independent of the journal installation."""
from .core import emit, today
from difflib import SequenceMatcher

def changed_characters(before,after):
    if before==after:return 0
    # First diff lines. Bound character-level matching to avoid quadratic work on books.
    total=0;a=before.splitlines(keepends=True);b=after.splitlines(keepends=True)
    for tag,i,j,k,l in SequenceMatcher(None,a,b,autojunk=True).get_opcodes():
        if tag=='equal':continue
        left=''.join(''.join(a[i:j]).split());right=''.join(''.join(b[k:l]).split())
        if len(left)+len(right)<=12000:
            total+=sum(max(y-x,v-u) for op,x,y,u,v in SequenceMatcher(None,left,right,autojunk=True).get_opcodes() if op!='equal')
        else:
            prefix=0
            while prefix<min(len(left),len(right)) and left[prefix]==right[prefix]:prefix+=1
            end=0
            while end<min(len(left),len(right))-prefix and left[-end-1]==right[-end-1]:end+=1
            total+=max(len(left),len(right))-prefix-end
    return total

def record_edit(db,uid,document,before,after):
    count=changed_characters(before,after)
    if count:emit(db,uid,'document-saved',{'date':today(),'document':document,'characters':count})
    return count

def record_word(db,uid,word):
    # Count distinct completed words, across study/test/review, once per Shanghai day.
    if not db.execute("SELECT 1 FROM events WHERE user_id=? AND kind='word-practiced' AND json_extract(payload,'$.date')=? AND json_extract(payload,'$.word')=?",(uid,today(),word)).fetchone():
        emit(db,uid,'word-practiced',{'date':today(),'word':word})

def listening_seconds(db,uid,day=None):
    return db.execute("SELECT COALESCE(SUM(json_extract(payload,'$.seconds')),0) FROM events WHERE user_id=? AND kind='music-listened'"+(" AND json_extract(payload,'$.date')=?" if day else ''),(uid,day) if day else (uid,)).fetchone()[0]
