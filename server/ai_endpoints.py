"""Normalize inference bases without changing user-selected providers or regions."""
from urllib.parse import urlsplit

XAI_HOSTS=frozenset({'api.x.ai','us.api.x.ai'})

def is_xai(base):
    value=urlsplit(base)
    return value.scheme=='https' and value.hostname in XAI_HOSTS and value.port in (None,443) and not value.username and not value.password

def is_xai_service(base):
    value=urlsplit(base)
    return is_xai(base) or (value.scheme=='https' and value.hostname=='management-api.x.ai' and value.port in (None,443) and not value.username and not value.password)

def api_base(value):
    base=value.strip().rstrip('/')
    for suffix in ('/chat/completions','/responses','/messages','/language-models','/models'):
        if base.endswith(suffix):
            base=base[:-len(suffix)]
            break
    if is_xai(base) and not urlsplit(base).path:base+='/v1'
    return base

def models_url(base,language_only=False):
    base=api_base(base)
    return base+('/language-models' if language_only and is_xai(base) else '/models')
