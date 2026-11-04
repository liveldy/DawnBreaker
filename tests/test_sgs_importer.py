from scripts.prepare_sgs import fields,plain,classic_group,is_test,digest

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
