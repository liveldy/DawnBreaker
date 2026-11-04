from scripts.prepare_sgs import fields,plain,classic_group,is_test,digest
from scripts.prepare_sgs import shared_skin_cards,card_portrait
from PIL import Image

def test_structured_wiki_classification_and_markup():
    text='{{武将|武将名=甲|武将包=一将成名-2025|经典上线时间=[https://example.com 2025-01-01]|经典形象故事=甲<br>乙{{颜色字|丙|red}}}}'
    data=fields(text,'武将')
    assert classic_group(data)==('一将成名','2025','R')
    assert plain('甲<br>乙')=='甲\n乙'
    assert classic_group(data|{'经典上线时间':'开服'}) is None
    assert is_test(data|{'经典获取方式':'体验卡测试'})
    assert classic_group({'武将包':'限定-神·武'})==('限定专属','神武','SR')
    assert classic_group({'武将包':'限定-冥'}) is None
    assert classic_group({'武将包':'威震-君威盖世'})==('威系列','君威盖世','SR')
    assert classic_group({'武将包':'荟萃-百战虎贲','经典上线时间':'开服'}) is None
    assert classic_group({'武将包':'荟萃-百战虎贲','经典上线时间':'2024-01-01'})==('群英荟萃','百战虎贲','SR')
    assert classic_group({'武将包':'喵喵杀'}) is None
    assert classic_group({'武将包':'限时地主'}) is None
    assert '/' not in digest('含有*与/的页面名') and digest('甲')!=digest('乙')

def test_shared_skin_name_requires_multiple_distinct_cards():
    cards=[{'id':'classic','world':'限定专属','series':'独立包'}, {'id':'single','world':'皮肤珍藏','series':'孤品'}, {'id':'a','world':'皮肤珍藏','series':'同名'}, {'id':'b','world':'皮肤珍藏','series':'同名'}]
    retained,removed=shared_skin_cards(cards)
    assert removed=={'孤品'} and {c['id'] for c in retained}=={'classic','a','b'}
    assert shared_skin_cards([cards[1],cards[1]])[0]==[],'duplicate rows must not create a shared series'

def test_three_art_families_fill_frame_without_matte_or_stretch():
    for size,family in [((876,632),'landscape'),((574,761),'portrait-classic'),((2480,3508),'portrait-poster')]:
        source=Image.new('RGB',size,'#e04020');portrait,info=card_portrait(source)
        assert portrait.size==(360,540) and info['family']==family
        x0,y0,x1,y1=info['crop']
        assert abs((x1-x0)/(y1-y0)-2/3)<1e-6
        assert 0<=x0<x1<=size[0] and 0<=y0<y1<=size[1]
        assert portrait.getextrema()==((224,224),(64,64),(32,32)),'no artificial letterbox color'
    portrait,info=card_portrait(Image.new('RGB',(876,632),'white'),.8)
    assert info['crop'][0]>(876-632*2/3)/2,'focal override should retain the right-side subject'
    portrait,info=card_portrait(Image.new('RGB',(500,1000),'white'))
    assert info['crop'][1]<50 and portrait.getpixel((0,0))==(255,255,255)
