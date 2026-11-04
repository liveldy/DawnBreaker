"""Synchronous plugin hooks, executed in the caller's database transaction."""
from collections import defaultdict
from typing import Callable

_hooks:dict[str,list[Callable]]=defaultdict(list)

def subscribe(event:str,handler:Callable):
    if handler not in _hooks[event]: _hooks[event].append(handler)

def dispatch(event:str,db,uid:str,payload:dict):
    for handler in _hooks[event]: handler(db,uid,payload)
