#!/usr/bin/env python3
"""
verificar_posts.py — le o estado dos ultimos posts de uma ficha.
Rodado so a mao (workflow_dispatch). Existe porque o Google nao avisa quando
rejeita um post: ele fica com state REJECTED e some da ficha em silencio.
"""
import os, sys, json, urllib.request, urllib.parse, urllib.error

CLIENTE = os.environ.get('GBP_CLIENTE', '')
QTD     = int(os.environ.get('QTD', '10') or 10)
data = urllib.parse.urlencode({
    'grant_type': 'refresh_token',
    'refresh_token': os.environ['GBP_REFRESH_TOKEN'],
    'client_id': os.environ['GBP_CLIENT_ID'],
    'client_secret': os.environ['GBP_CLIENT_SECRET'],
}).encode()
req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
with urllib.request.urlopen(req, timeout=30) as r:
    token = json.loads(r.read())['access_token']

sch = None
for mes in sorted(os.listdir(CLIENTE), reverse=True):
    p = f"{CLIENTE}/{mes}/schedule.json"
    if os.path.exists(p):
        sch = json.load(open(p)); break
if not sch:
    print("sem schedule.json em", CLIENTE); sys.exit(1)

url = (f"https://mybusiness.googleapis.com/v4/{sch['account_id']}/"
       f"{sch['location_id']}/localPosts?pageSize=100")
req = urllib.request.Request(url); req.add_header('Authorization', f'Bearer {token}')
with urllib.request.urlopen(req, timeout=60) as r:
    posts = json.loads(r.read()).get('localPosts', [])

print(f"{CLIENTE}: {len(posts)} posts na ficha\n")
rejeitados = [p for p in posts if p.get('state') == 'REJECTED']
for p in posts[:QTD]:
    print(f"{p.get('createTime','?')[:16]}  {p.get('state','?'):11} "
          f"{'com imagem' if p.get('media') else 'SEM IMAGEM':10}  "
          f"{p.get('summary','')[:60]!r}")
    print(f"     {p.get('name','').split('/')[-1]}  ->  {p.get('searchUrl','(sem link)')}")
if rejeitados:
    print(f"\n::warning::{len(rejeitados)} post(s) REJEITADO(S) nesta ficha:")
    for p in rejeitados:
        print("  ", p.get('createTime','')[:16], repr(p.get('summary','')[:80]))
else:
    print("\nNenhum post rejeitado nesta ficha.")
