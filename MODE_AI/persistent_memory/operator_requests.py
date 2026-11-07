"""Explicit content-bound Operator requests, never inferred or fabricated consent."""
import re


def create_content(text):
    if type(text) is not str:return None
    # Session scope and refusal cannot be overridden by a positive prefix.
    if re.search(r"\b(?:don't|do not|never|session.only|thread.only|conversation.only)\b|\bfor this (?:conversation|session|thread)\b",text,re.I):return None
    match=re.fullmatch(r'(?:Also\s+)?(?:remember this for later:\s*|remember that\s+)(\S[\s\S]*)',text.strip(),re.I)
    return match[1] if match else None


def removal_target(text):
    if type(text) is not str:return None
    match=re.fullmatch(r"(?:I'm correcting something from earlier:\s*)?(?:don't|do not) remember (.+?) (?:long term|permanently)\.(?:\s*That's just for this conversation\.)?",text.strip(),re.I)
    if not match:return None
    value=re.sub(r'^(?:the\s+)?name\s+','',match[1],flags=re.I).strip()
    return value if len(value)>=3 else None


def removal_matches(text,content):
    target=removal_target(text)
    return bool(target and re.search(r'(?<!\w)'+re.escape(target)+r'(?!\w)',content,re.I))


def bound_create_authorization(confirmation,original,content):
    return confirmation==original and create_content(confirmation)==content and bool(content)
