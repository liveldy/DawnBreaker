"""Extract the chat envelope without ever presenting internal state as message text."""
import json,re
from fastapi import HTTPException

class ReplyFormatError(HTTPException):
    def __init__(self,message='回复格式无法读取，请重试'):super().__init__(502,message)

MARKER=re.compile(r'\{\s*"(?:bubbles|emotion|memories|messages)"\s*:',re.I)

def envelope(text):
    decoder=json.JSONDecoder(strict=False);value=str(text).strip()
    # Decode complete objects even when the model puts prose or fences before them.
    for match in list(re.finditer(r'\{',value))[:256]:
        try:obj,end=decoder.raw_decode(value[match.start():])
        except ValueError:continue
        if not isinstance(obj,dict):continue
        bubbles=obj.get('bubbles',obj.get('messages',obj.get('text',obj.get('message'))))
        if isinstance(bubbles,(str,list)) and ('bubbles' in obj or match.start()==0 or MARKER.match(value[match.start():])):
            return obj,bubbles
    return None,None

def parse_reply(raw,allow_empty=False,max_bubbles=12):
    text=str(raw).strip();obj,bubbles=envelope(text)
    if obj is None:
        if MARKER.search(text) or text.startswith(('{','[')):raise ReplyFormatError()
        obj={};bubbles=[s.strip() for s in re.split(r'\n{2,}',text) if s.strip()]
    if isinstance(bubbles,str):bubbles=[bubbles]
    if not isinstance(bubbles,list):raise ReplyFormatError()
    clean=[]
    for item in bubbles:
        if not isinstance(item,str) or not item.strip():continue
        nested,nested_bubbles=envelope(item)
        if nested is not None:
            pieces=[nested_bubbles] if isinstance(nested_bubbles,str) else nested_bubbles
        elif MARKER.search(item):raise ReplyFormatError()
        else:pieces=[item]
        for piece in pieces:
            if isinstance(piece,str) and piece.strip():
                if MARKER.search(piece):raise ReplyFormatError()
                clean.append(piece.strip().rstrip('。'))
    clean=clean[:max_bubbles]
    if not clean and not allow_empty:raise ReplyFormatError('没有收到可读取的回复，请重试')
    return clean,obj

def display_text(text):
    """Also protect old persisted replies; do not rewrite their memories or source rows."""
    if not MARKER.search(text):return text
    try:return '\n'.join(parse_reply(text,True,40)[0])
    except ReplyFormatError:
        prefix=text[:MARKER.search(text).start()].strip().rstrip('`').strip()
        return prefix or '这条旧回复的格式异常，请重新发送上一条消息。'
