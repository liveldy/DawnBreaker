"""Import BWIKI's structured general/skin templates into the shared collection schema.

Run with requirements-dev.txt. Raw wiki revisions and source artwork stay under
mods/SGSpackage (ignored by Git); only the importer and provenance rules are public.
"""
import argparse,hashlib,io,json,re,time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import quote
import httpx,mwparserfromhell
from bs4 import BeautifulSoup
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[1]
API='https://wiki.biligame.com/sgs/api.php'
INDEX='https://wiki.biligame.com/sgs/武将图鉴'

def digest(text):return hashlib.sha256(text.encode()).hexdigest()[:24]
def plain(value):
    text=re.sub(r'<br\s*/?>','\n',str(value),flags=re.I)
    text=mwparserfromhell.parse(text).strip_code(normalize=True,collapse=True)
    return BeautifulSoup(text,'html.parser').get_text('\n',strip=True).strip()
def fields(text,name):
    templates=[t for t in mwparserfromhell.parse(text).filter_templates() if str(t.name).strip()==name]
    return {str(p.name).strip():str(p.value).strip() for p in templates[0].params} if templates else {}
def is_test(data,version='经典'):
    flag=plain(data.get(version+'测试',''))
    return (bool(flag) and flag not in ('0','否','false')) or any('测' in plain(data.get(version+k,'')) for k in ('获取方式','上线时间'))
def classic_group(data):
    pack=plain(data.get('武将包',''));prefix,_,sub=pack.partition('-')
    if is_test(data):return None
    if prefix=='一将成名' and plain(data.get('经典上线时间',''))!='开服':return ('一将成名',sub,'R')
    if prefix=='限定' and sub in ('神·武','祈福','隐山之玉','高山仰止','武庙'):return ('限定专属','神武' if sub=='神·武' else sub,'SR')
    if prefix=='威震':return ('威系列',sub,'SR')
    if prefix=='谋定':return ('谋定天下',sub,'SR')
    if prefix=='星河璀璨':return ('星河璀璨',sub,'SR')
    if prefix=='荟萃' and plain(data.get('经典上线时间',''))!='开服':return ('群英荟萃',sub,'SR')
    return None

class Importer:
    def __init__(self,source,output,workers=4,browser=False):
        self.source=source;self.output=output;self.workers=workers
        for name in ('raw','media','indexes'):(source/name).mkdir(parents=True,exist_ok=True)
        self.client=httpx.Client(timeout=60,follow_redirects=True,headers={'User-Agent':'DawnBreaker-SGS-Importer/1.0 (public wiki catalog; bounded concurrency)','Accept-Encoding':'identity'})
        self.browser_pool=ThreadPoolExecutor(max_workers=1) if browser else None
        self.browser_page=None
    def browser_request(self,params):
        if self.browser_page is None:
            from playwright.sync_api import sync_playwright
            self.playwright=sync_playwright().start()
            self.browser=self.playwright.chromium.launch(channel='chrome',headless=True)
            self.browser_page=self.browser.new_page()
            self.browser_page.goto(API,wait_until='domcontentloaded')
        time.sleep(1)
        value=self.browser_page.evaluate('''async params=>{const r=await fetch('/sgs/api.php?'+new URLSearchParams(params));return {status:r.status,body:await r.text()};}''',params)
        if value['status']!=200:raise RuntimeError('Public wiki API unavailable: HTTP '+str(value['status']))
        result=json.loads(value['body'])
        if 'error' in result:raise RuntimeError(str(result['error']))
        return result
    def close(self):
        self.client.close()
        if self.browser_pool:
            if self.browser_page:self.browser_pool.submit(self.close_browser).result()
            self.browser_pool.shutdown()
    def close_browser(self):self.browser.close();self.playwright.stop()
    def request(self,**params):
        if self.browser_pool:return self.browser_pool.submit(self.browser_request,{'format':'json','maxlag':'5',**{k:str(v) for k,v in params.items()}}).result()
        for attempt in range(4):
            try:
                response=self.client.get(API,params={'format':'json','maxlag':5,**params});response.raise_for_status();value=response.json()
                if 'error' in value:raise RuntimeError(str(value['error']))
                return value
            except Exception:
                if attempt==3:raise
                time.sleep(2**attempt)
    def index(self,category,properties):
        path=self.source/'indexes'/(category+'.json')
        if path.exists():return json.loads(path.read_text('utf8'))
        result={};offset=0
        while True:
            query='[[分类:'+category+']]|'+''.join('?'+p+'|' for p in properties)+'limit=500|offset='+str(offset)
            value=self.request(action='ask',query=query)['query'];batch=value['results']
            if not isinstance(batch,dict) or not batch:break
            result.update(batch);offset+=len(batch)
            if len(batch)<500:break
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');return result
    def revisions(self,titles):
        pending=[t for t in titles if not (self.source/'raw'/(digest(t)+'.json')).exists()]
        chunks=[pending[i:i+40] for i in range(0,len(pending),40)]
        def batch(titles):
            value=self.request(action='query',prop='revisions',titles='|'.join(titles),rvprop='ids|timestamp|content',rvslots='main')
            for page in value['query']['pages'].values():
                (self.source/'raw'/(digest(page['title'])+'.json')).write_text(json.dumps(page,ensure_ascii=False),'utf8')
            return len(titles)
        done=0
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for future in as_completed([pool.submit(batch,c) for c in chunks]):
                done+=future.result();print('Wiki revisions',done,'/',len(pending),flush=True)
        return {t:json.loads((self.source/'raw'/(digest(t)+'.json')).read_text('utf8')) for t in titles}
    def category_titles(self,category):
        path=self.source/'indexes'/('category-'+category+'.json')
        if path.exists():return json.loads(path.read_text('utf8'))
        titles=[];continuation={}
        while True:
            value=self.request(action='query',list='categorymembers',cmtitle='分类:'+category,cmlimit=500,cmnamespace=0,**continuation)
            titles.extend(p['title'] for p in value['query']['categorymembers'])
            continuation=value.get('continue',{})
            if not continuation:break
        path.write_text(json.dumps(titles,ensure_ascii=False),'utf8');return titles
    def metadata(self):
        heroes=self.index('武将图鉴测试',['武将包','武将版本']);skins=self.index('皮肤',['皮肤名','所属武将'])
        # SMW's known category-index issue omits real generals. Cross-check the
        # MediaWiki category and skin-owner references instead of trusting counts.
        skin_titles=sorted(set(skins)|set(self.category_titles('皮肤')))
        skin_raw=self.revisions(skin_titles)
        owners={plain(fields(p.get('revisions',[{}])[0].get('slots',{}).get('main',{}).get('*',''),'皮肤').get('所属武将','')) for p in skin_raw.values()}
        hero_titles=sorted(set(heroes)|set(self.category_titles('武将图鉴测试'))|{o for o in owners if o})
        raw=self.revisions(hero_titles)|skin_raw;general={};cards=[];excluded=[]
        def candidate(title,data,version,world,series,rarity):
            name=plain(data.get('武将名',title)) if version else plain(data.get('所属武将',''))
            skin=plain(data.get('皮肤名','')) if not version else ('界限突破' if version=='界限' else '经典形象')
            suffix=''
            if not version and name in title:suffix=title.split(name,1)[1]
            stem=plain(data.get('地址','')) if not version else ''
            stems=([stem] if stem else [skin+'-'+name+'-静态'+suffix,skin+'-'+name+'-大图'+suffix]) if not version else [name+('-界限突破' if version=='界限' else '')+'-经典形象']
            # A breakthrough card must have its own art, never the unbroken portrait.
            files=[s+'.'+ext for s in stems for ext in ('png','jpg','jpeg','webp')]
            source=raw[title];revision=source.get('revisions',[{}])[0]
            own_story=plain(data.get(version+'形象故事','') if version else data.get('皮肤故事',''))
            fallback=plain(data.get('经典形象故事','')) if version else plain(general.get(name,{}).get('经典形象故事',''))
            series_id='sgs-series-'+digest(world+'|'+series)
            return {'id':'sgs-'+digest(title+'|'+(version or 'skin')),'name':name+' · '+skin,'character_name':name,'skin_name':skin,'title':world+' · '+series,'rarity':rarity,'original_rarity':plain(data.get('品质','')) if not version else version,'album_id':'sgs','series_ids':[series_id],'world':world,'series':series,'description':own_story or fallback,'story_source':'skin' if own_story and not version else version if own_story else 'classic-fallback' if fallback else 'missing','artist':plain(data.get(version+'形象画师',data.get('经典形象画师','')) if version else data.get('画师','')),'source_url':'https://wiki.biligame.com/sgs/'+quote(title,safe=''),'source_page_id':source.get('pageid'),'source_revision':revision.get('revid'),'wiki_title':title,'version':version or 'skin','file_candidates':files}
        for title in hero_titles:
            page=raw[title];text=page.get('revisions',[{}])[0].get('slots',{}).get('main',{}).get('*','');data=fields(text,'武将')
            if not data:excluded.append({'page':title,'reason':'no-general-template'});continue
            general[title]=data
            if is_test(data):excluded.append({'page':title,'reason':'test-general'});continue
            group=classic_group(data)
            if group:cards.append(candidate(title,data,'经典',*group))
            else:excluded.append({'page':title,'reason':'classic-outside-requested-groups-or-launch'})
            pack=plain(data.get('武将包',''));base=pack.split('-',1)[0]
            versions=heroes.get(title,{}).get('printouts',{}).get('武将版本',[])
            # The requested source has no separate Myth Returns breakthrough art;
            # the user explicitly chose to ignore that absent sub-album.
            if base in ('标准','一将成名','星火燎原') and plain(data.get('经典上线时间',''))=='开服' and not is_test(data,'界限'):
                cards.append(candidate(title,data,'界限','界限突破',base,'R'))
        for title in skin_titles:
            text=raw[title].get('revisions',[{}])[0].get('slots',{}).get('main',{}).get('*','');data=fields(text,'皮肤')
            hero=plain(data.get('所属武将',''));skin=plain(data.get('皮肤名',''))
            if not data:
                excluded.append({'page':title,'reason':'initial-portrait-template-already-handled'});continue
            if hero not in general or is_test(general[hero]) or plain(general[hero].get('武将包','')) in ('限时地主','喵喵杀'):
                excluded.append({'page':title,'reason':'skin-of-excluded-or-unknown-general'});continue
            if skin in ('经典','经典形象','界限突破','原画'):
                excluded.append({'page':title,'reason':'classic-already-handled'});continue
            cards.append(candidate(title,data,'','皮肤珍藏',skin,'R'))
        result={'source':INDEX,'heroes':len(hero_titles),'semantic_heroes':len(heroes),'skins':len(skin_titles),'cards':cards,'excluded':excluded}
        (self.source/'metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
        print('Metadata',len(cards),'cards',Counter(c['world'] for c in cards),flush=True);return result
    def image_info(self,cards):
        path=self.source/'image-info.json';known=json.loads(path.read_text('utf8')) if path.exists() else {}
        titles=sorted({f for c in cards for f in c['file_candidates'] if f not in known})
        def batch(names):
            value=self.request(action='query',prop='imageinfo',titles='|'.join('File:'+n for n in names),iiprop='url|size|mime|sha1',redirects=1)
            aliases={n['from']:n['to'] for n in value['query'].get('normalized',[])}|{n['from']:n['to'] for n in value['query'].get('redirects',[])}
            pages={p['title']:p for p in value['query']['pages'].values()}
            def info(name):
                key='File:'+name
                for _ in range(5):
                    if key not in aliases:break
                    key=aliases[key]
                return pages.get(key,{}).get('imageinfo',[None])[0]
            return {n:info(n) for n in names}
        chunks=[titles[i:i+50] for i in range(0,len(titles),50)]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for future in as_completed([pool.submit(batch,c) for c in chunks]):
                known.update(future.result());path.write_text(json.dumps(known,ensure_ascii=False),'utf8')
        return known
    def compile(self,metadata):
        infos=self.image_info(metadata['cards']);complete=[];missing=[]
        for name in ('cards','splashes','posters'):(self.output/name).mkdir(parents=True,exist_ok=True)
        def render(card):
            match=next(((name,infos[name]) for name in card['file_candidates'] if infos.get(name)),None)
            if not match:return card,None,'no-static-image'
            filename,info=match;url=info['url']
            if not url.startswith('https://patchwiki.biligame.com/'):raise RuntimeError('Unexpected artwork host')
            path=self.source/'media'/(digest(url)+Path(filename).suffix)
            if not path.exists():
                response=self.client.get(url,headers={'Referer':quote(INDEX,safe=':/')});response.raise_for_status()
                if len(response.content)>30*1024*1024:raise RuntimeError('Artwork too large')
                temp=path.with_suffix('.partial');temp.write_bytes(response.content);temp.replace(path)
            portrait_path=self.output/'cards'/(card['id']+'.webp');splash_path=self.output/'splashes'/(card['id']+'.webp')
            ready=portrait_path.exists() and splash_path.exists() and min(portrait_path.stat().st_mtime,splash_path.stat().st_mtime)>=path.stat().st_mtime
            if ready:
                with Image.open(portrait_path) as previous:ready=previous.size==(360,540)
            if not ready:
                with Image.open(path) as original:
                    image=ImageOps.exif_transpose(original).convert('RGB')
                    if image.width<100 or image.height<100:return card,None,'too-small-artwork'
                    portrait=ImageOps.pad(image,(360,540),method=Image.Resampling.LANCZOS,color='#151b1d',centering=(.5,.5))
                    portrait.save(portrait_path,'WEBP',quality=86)
                    image.thumbnail((1920,1920));image.save(splash_path,'WEBP',quality=90)
            result={k:v for k,v in card.items() if k not in ('file_candidates','world','series','version')}
            result.update(image='/api/plugins/collection/image/'+card['id'],splash='/api/plugins/collection/splash/'+card['id'],source_image=url,source_file=filename)
            return card,result,None
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures=[pool.submit(render,c) for c in metadata['cards']]
            for i,future in enumerate(as_completed(futures),1):
                card,result,reason=future.result()
                if reason:missing.append({'page':card['wiki_title'],'version':card['version'],'reason':reason})
                else:complete.append((card,result))
                if i%100==0 or i==len(futures):print('Artwork',i,'/',len(futures),'missing',len(missing),flush=True)
        complete.sort(key=lambda pair:pair[1]['id']);worlds={}
        order=['界限突破','一将成名','限定专属','威系列','谋定天下','星河璀璨','群英荟萃','皮肤珍藏']
        for card,value in complete:
            world=worlds.setdefault(card['world'],{})
            series=world.setdefault(card['series'],{'id':card['series_ids'][0],'name':card['series'],'kind':'series','children':[],'cover_card_id':card['id']})
        if not complete:raise RuntimeError('No valid cards; do not replace the active catalog')
        children=[{'id':'sgs-world-'+digest(w),'name':w,'kind':'universe','children':list(worlds[w].values())} for w in order if w in worlds]
        album={'id':'sgs','name':'三国杀','kind':'album','description':'以武将包和同名皮肤归档。来源：哔哩哔哩游戏三国杀 BWIKI。','content_plugin':'sgs','poster':'posters/sgs.webp','children':children,'pack':{'title':'群英入卷','subtitle':'三国杀','caption':'一页风云，一面故人。','art_caption':'三国杀 · 经典武将与皮肤','probabilities':{'R':80,'SR':20}}}
        # A real portrait at the right leaves a plain field for the existing poster's text.
        cover=next((v for _,v in complete if v['character_name']=='乐蔡文姬' and v['skin_name']=='姝丽风华'),None)
        if not cover:raise RuntimeError('Requested cover artwork missing: 乐蔡文姬 · 姝丽风华')
        album['cover_card_id']=cover['id'];album['pack']['art_caption']='姝丽风华 · 乐蔡文姬';album['pack']['subtitle']='乐蔡文姬'
        poster=Image.new('RGB',(1600,900),'#151b1d')
        with Image.open(self.output/'splashes'/(cover['id']+'.webp')) as im:
            im=ImageOps.contain(im,(960,900),Image.Resampling.LANCZOS);poster.paste(im,(1600-im.width,(900-im.height)//2))
        poster.save(self.output/'posters/sgs.webp','WEBP',quality=90)
        existing=json.loads((self.output/'cards.json').read_text('utf8'));existing['cards']=[c for c in existing['cards'] if c.get('album_id')!='sgs']+[v for _,v in complete]
        registry=json.loads((self.output/'card-albums.json').read_text('utf8'));registry['albums']=[a for a in registry['albums'] if a['id']!='sgs']+[album]
        for name,value in [('cards.json',existing),('card-albums.json',registry)]:
            tmp=self.output/(name+'.partial');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8');tmp.replace(self.output/name)
        report={k:v for k,v in metadata.items() if k!='cards'}|{'cards':len(complete),'worlds':{w:len(worlds[w]) for w in order if w in worlds},'rarities':dict(Counter(v['rarity'] for _,v in complete)),'missing_artwork':missing,'missing_stories':[v['wiki_title'] for _,v in complete if not v['description']],'image_size':[360,540],'normalization':'contain full original on a neutral matte; full artwork retained in splash'}
        (self.source/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('excluded','missing_artwork','missing_stories')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--metadata-only',action='store_true');parser.add_argument('--workers',type=int,default=4);parser.add_argument('--browser',action='store_true',help='Read the public API with installed Chrome; requests are serialized at 1/s');args=parser.parse_args()
    importer=Importer(ROOT/'mods/SGSpackage',ROOT/'server/content',max(1,min(args.workers,6)),args.browser)
    try:
        file=importer.source/'metadata.json';metadata=json.loads(file.read_text('utf8')) if file.exists() else importer.metadata()
        if not args.metadata_only:importer.compile(metadata)
    finally:importer.close()
