"""Shared album -> universe -> series catalog. Card IDs are stable and globally unique."""
from fastapi import HTTPException
from .content_store import items
from .core import installed

def album_specs(registry):
    return registry.get('albums',[])

def accessible_cards(db,uid,config,registry):
    allowed={a['id'] for a in album_specs(registry) if installed(db,uid,a['content_plugin'])}
    return [c for c in items(db,'cards',config['cards']) if c.get('album_id') in allowed]

def tree_for(spec,cards,owned):
    """Compute counters from unique card IDs, including multi-series memberships."""
    by_id={c['id']:c for c in cards}
    def visit(node):
        children=[];members=set()
        if node['kind']=='series':
            members={c['id'] for c in cards if node['id'] in c.get('series_ids',[]) or c['id'] in node.get('card_ids',[])}
        else:
            for child in node.get('children',[]):
                rendered,ids=visit(child)
                if ids:children.append(rendered);members.update(ids)
        cover=node.get('cover_card_id')
        if cover not in members:cover=next((c['id'] for c in cards if c['id'] in members),None)
        result={k:v for k,v in node.items() if k not in ('children','card_ids','cover_card_id','pack','poster','content_plugin')}
        result.update(total=len(members),owned=sum(owned.get(cid,0)>0 for cid in members),cover=by_id[cover]['image'] if cover else None,card_ids=sorted(members),children=children)
        return result,members
    return visit(spec)[0]

def pack_for(spec,config,db):
    from .config import setting
    pack=spec.get('pack')
    if not pack:return None
    return pack|{'id':spec['id'],'name':spec['name'],'cost':pack.get('cost',setting(db,'draw_cost',config['cost'])),'probabilities':pack.get('probabilities',setting(db,'draw_probabilities',config['probabilities']))}

def media_path(root,relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():raise HTTPException(404,'图像不存在')
    return path
