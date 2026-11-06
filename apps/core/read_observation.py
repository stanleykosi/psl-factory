"""Bounded memo for one read-only observation, never a command/authority cache."""
import json
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
from django.core.exceptions import ValidationError

_frame=ContextVar('psl_read_observation',default=None)
MAX_FACTS=128  # Memory bound only; overflow computes normally and never blocks business work.


@contextmanager
def observation_scope():
    if _frame.get() is not None:
        yield;return
    token=_frame.set({})
    try:yield
    finally:_frame.reset(token)


def read_observation(fn):
    @wraps(fn)
    def observe(*args,**kwargs):
        with observation_scope():return fn(*args,**kwargs)
    return observe


def assert_command_allowed():
    if _frame.get() is not None:raise ValidationError('Read-only observation cannot execute a domain command; start a fresh authorised command')


def observed_fact(fn):
    """Reuse a pure dossier fact only inside this observation; exceptions are never retained."""
    @wraps(fn)
    def read(d,*args,**kwargs):
        frame=_frame.get()
        if frame is None:return fn(d,*args,**kwargs)
        try:parameters=json.dumps([args,kwargs],sort_keys=True,separators=(',',':'),allow_nan=False)
        except (ValueError,TypeError):return fn(d,*args,**kwargs)
        key=(fn.__module__,fn.__qualname__,d._meta.label_lower,d._state.db,d.case_id,d.pk,parameters)
        if key in frame:
            value=frame[key];return deepcopy(value) if isinstance(value,(dict,list,tuple)) else value
        value=fn(d,*args,**kwargs)
        if len(frame)<MAX_FACTS:frame[key]=deepcopy(value) if isinstance(value,(dict,list,tuple)) else value
        return value
    return read
