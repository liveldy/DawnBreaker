"""Print bounded extractor diagnostics without media URLs, cookies or tokens."""
import json
import yt_dlp
class Logger:
    def debug(self,message):pass
    def warning(self,message):pass
    def error(self,message):pass
url='https://www.bilibili.com/video/BV1xx411c7mD'
with yt_dlp.YoutubeDL({'quiet':True,'logger':Logger(),'socket_timeout':15,'retries':0,'noplaylist':True,'skip_download':True,'allowed_extractors':['bilibili.*'],'format':'all','http_headers':{'Referer':'https://www.bilibili.com/','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}}) as ydl:
    try:
        info=ydl.extract_info(url,download=False)
        formats=info.get('formats',[])
        print(json.dumps({'extractor':info.get('extractor_key'),'formats':len(formats),'combined':sum(f.get('vcodec')!='none' and f.get('acodec')!='none' for f in formats),'video_only':sum(f.get('vcodec')!='none' and f.get('acodec')=='none' for f in formats),'audio_only':sum(f.get('vcodec')=='none' and f.get('acodec')!='none' for f in formats)},ensure_ascii=True))
    except Exception as e:
        message=str(e)
        print(json.dumps({'error_type':type(e).__name__,'risk_control':any(x in message for x in ['412','403','-352']),'format_error':'format' in message.lower(),'login':'login' in message.lower(),'message':message.split('(caused by')[0][:240]},ensure_ascii=True))
