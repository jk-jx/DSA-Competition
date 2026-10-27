"""Explainable candidate matching, not automatic customer merging."""
import re, unicodedata
from rapidfuzz import fuzz
from config import settings
from database import load_df

REPLACEMENTS = {'natl':'national','univ':'university','hosp':'hospital','acct':'account', 'pte':'','ltd':'','sdn':'','bhd':'','co':''}

def normalize(name):
    name=unicodedata.normalize('NFKD',name or '').lower()
    tokens = re.findall(r'[a-z0-9]+',name)
    return ' '.join(REPLACEMENTS.get(tok,tok) for tok in tokens if REPLACEMENTS.get(tok,tok))

def find_matches(name, domain='Customer', country=None, limit=5):
    if domain!='Customer': return []  # Item master matching requires its own SKU/catalogue index.
    df=load_df('SELECT customer_id,name,country,entity,registration_number FROM customers')
    if country: df=df[df.country==country]
    query=normalize(name); matches=[]
    high=settings()['matching']['review']; warn=settings()['matching']['warn']
    for r in df.itertuples(index=False):
        score=round(fuzz.token_sort_ratio(query,normalize(r.name)),1)
        tier='Review required' if score >= high else 'Warning' if score >= warn else 'Pass'
        if score >= warn:
            matches.append({'customer_id':r.customer_id,'existing_name':r.name,'country':r.country,'entity':r.entity,'score':score,'tier':tier,'registration_number':r.registration_number})
    return sorted(matches,key=lambda r:r['score'],reverse=True)[:limit]
