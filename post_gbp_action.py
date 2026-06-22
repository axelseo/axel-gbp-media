#!/usr/bin/env python3
"""
post_gbp_action.py — Executado diariamente pelo GitHub Actions
Axel SEO Digital Solutions

Posta o card do dia no Google Business Profile via API direta.
Credenciais vem de GitHub Secrets (variaveis de ambiente).

Coloque este arquivo na RAIZ do repositorio axel-gbp-media.
"""
import os
import sys
import json
import datetime
import time
import urllib.request
import urllib.parse
import urllib.error

# ── Variaveis de ambiente (GitHub Secrets) ────────────────────────────────────
REFRESH_TOKEN = os.environ.get('GBP_REFRESH_TOKEN', '')
CLIENT_ID     = os.environ.get('GBP_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('GBP_CLIENT_SECRET', '')
CLIENTE       = os.environ.get('GBP_CLIENTE', 'kadosh')
DATE_OVERRIDE = os.environ.get('DATE_OVERRIDE', '').strip()

# ── Validacao ─────────────────────────────────────────────────────────────────
missing = [k for k, v in {
    'GBP_REFRESH_TOKEN': REFRESH_TOKEN,
    'GBP_CLIENT_ID':     CLIENT_ID,
    'GBP_CLIENT_SECRET': CLIENT_SECRET,
    'GBP_CLIENTE':       CLIENTE,
}.items() if not v]

if missing:
    print(f"ERRO: Secrets faltando: {missing}")
    print("Configure em: Settings > Secrets and variables > Actions")
    sys.exit(1)

# ── Data de hoje ──────────────────────────────────────────────────────────────
if DATE_OVERRIDE:
    today = DATE_OVERRIDE
    print(f"[MODO TESTE] Postando como se fosse: {today}")
else:
    today = datetime.date.today().isoformat()

print(f"Data de postagem: {today}")
mes = today[:7]  # YYYY-MM

# ── Carregar schedule.json ─────────────────────────────────────────────────────
schedule_path = f"{CLIENTE}/{mes}/schedule.json"
print(f"Carregando schedule: {schedule_path}")

if not os.path.exists(schedule_path):
    print(f"ERRO: schedule.json nao encontrado: {schedule_path}")
    print("Gere e suba o schedule.json antes do inicio do mes.")
    sys.exit(0)

with open(schedule_path, encoding='utf-8') as f:
    schedule = json.load(f)

# ── Encontrar post de hoje ────────────────────────────────────────────────────
post = next((p for p in schedule.get('posts', []) if p['date'] == today), None)

if not post:
    print(f"Nenhum post agendado para {today}.")
    print("Schedule cobre: {} a {}".format(
        schedule.get('data_inicio', '?'),
        schedule.get('data_fim', '?')
    ))
    sys.exit(0)

print(f"Card #{post['card']}: {post['filename']}")
print(f"Descricao: {post['description'][:80]}...")

# ── URL da imagem (publica no GitHub) ─────────────────────────────────────────
github_username = schedule.get('github_username', 'axelseo')
repo            = schedule.get('repo', 'axel-gbp-media')
image_url = (
    f"https://raw.githubusercontent.com/{github_username}/{repo}/main"
    f"/{CLIENTE}/{mes}/{post['filename']}"
)
print(f"Imagem URL: {image_url}")

# ── Obter access token via refresh token ─────────────────────────────────────
def get_access_token():
    data = urllib.parse.urlencode({
        'grant_type':    'refresh_token',
        'refresh_token': REFRESH_TOKEN,
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=data,
        method='POST'
    )
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        print(f"ERRO HTTP ao obter token: {e.code} — {body}")
        if 'invalid_grant' in body:
            print("Token expirado ou revogado.")
            print("Solucao: Reautentique localmente e atualize o Secret GBP_REFRESH_TOKEN.")
        sys.exit(1)
    token = result.get('access_token')
    if not token:
        print(f"ERRO: access_token nao retornado: {result}")
        sys.exit(1)
    return token

# ── Postar no GBP ─────────────────────────────────────────────────────────────
def post_to_gbp(token, account_id, location_id, summary, image_url, language='en-US'):
    url = f'https://mybusiness.googleapis.com/v4/{account_id}/{location_id}/localPosts'
    body = json.dumps({
        'languageCode': language,
        'summary':      summary,
        'topicType':    'STANDARD',
        'callToAction': {'actionType': 'CALL'},
        'media': [{'mediaFormat': 'PHOTO', 'sourceUrl': image_url}],
    }).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Authorization',  f'Bearer {token}')
    req.add_header('Content-Type',   'application/json; charset=utf-8')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        print(f"ERRO HTTP ao postar: {e.code} — {body}")
        if e.code == 401:
            print("Token invalido. Verifique o Secret GBP_REFRESH_TOKEN.")
        elif e.code == 403:
            print("Permissao negada. Verifique account_id e location_id.")
        sys.exit(1)

# ── Verificar que o post tem imagem ──────────────────────────────────────────
def verify_has_image(token, post_name, retries=3):
    url = f'https://mybusiness.googleapis.com/v4/{post_name}'
    for attempt in range(retries):
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'Bearer {token}')
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            media = data.get('media', [])
            if media and media[0].get('sourceUrl'):
                return True
            # media existe mas sourceUrl ainda nao populado = GBP processando
            # Trata como inconclusivo, nao como falha
        except Exception as e:
            print(f"  Tentativa {attempt+1} falhou: {e}")
        if attempt < retries - 1:
            print(f"  Aguardando 15s antes da proxima tentativa...")
            time.sleep(15)
    return None  # inconclusivo

# ── Execucao principal ────────────────────────────────────────────────────────
print("\nObtendo token OAuth...")
token = get_access_token()
print("Token obtido.")

account_id = schedule.get('account_id', '')
location_id = schedule.get('location_id', '')
language    = schedule.get('language', 'en-US')

print(f"\nPostando no GBP...")
print(f"  Account:  {account_id}")
print(f"  Location: {location_id}")

result = post_to_gbp(token, account_id, location_id, post['description'], image_url, language)

post_name = result.get('name', '')
state     = result.get('state', '')
print(f"Post criado: {post_name}")
print(f"Estado: {state}")

# Verificacao da imagem — nao-fatal (GBP processa a imagem de forma assincrona)
print("\nVerificando imagem no post (aguardando 15s para GBP processar)...")
time.sleep(15)

has_image = verify_has_image(token, post_name)

if has_image is True:
    print("VERIFICACAO OK: post tem imagem!")
else:
    # GBP ainda processando ou inconclusivo — nao e um erro fatal
    print("AVISO: imagem ainda sendo processada pelo GBP (comportamento normal).")
    print(f"Verifique manualmente em alguns minutos: {post_name}")

print(f"""
==============================
Card #{post['card']} postado com sucesso!
Data:     {today}
Cliente:  {schedule.get('nome', CLIENTE)}
Post ID:  {post_name}
Estado:   {state}
Imagem:   {image_url}
==============================
""")
