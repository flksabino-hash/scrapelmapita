"""
b2b_radar_pro.py — Agente de Sangria B2B
Arquiteto: Encânis | Alvo: Curitiba/Batel | Engine: Gemini 1.5 Flash
Execução: EndeavourOS KDE Zen | Python 3.11+ venv
"""

import os
import re
import time
import random
import json
import logging
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from googlemaps import Client as GoogleMapsClient

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "SUA_CHAVE_AQUI")
GOOGLE_MAPS_KEY    = os.environ.get("GOOGLE_MAPS_KEY", "SUA_CHAVE_MAPS_AQUI")
GSHEET_ID          = os.environ.get("GSHEET_ID",       "ID_DA_PLANILHA_AQUI")
CREDENTIALS_FILE   = os.environ.get("CREDENTIALS_FILE","credentials.json")

NICHO              = "restaurantes"          # altere conforme alvo
CIDADE             = "Curitiba"
BAIRRO             = "Batel"
BUSCA              = f"{NICHO} {BAIRRO} {CIDADE}"
MAX_ALVOS          = 30
DELAY_MIN          = 4.0                     # segundos entre requests
DELAY_MAX          = 9.0
LOG_FILE           = "sangria.log"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("sangria")

# ─── MACHINE LEARNING: HISTÓRICO DE ABORDAGENS ────────────────────────────────

HISTORICO_FILE = "historico_abordagens.json"

def carregar_historico() -> dict:
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, "r") as f:
            return json.load(f)
    return {"abordagens": [], "melhores_angulos": [], "taxa_resposta": {}}

def salvar_historico(hist: dict):
    with open(HISTORICO_FILE, "w") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

def registrar_resultado(hist: dict, cnpj_ou_nome: str, angulo: str, resultado: str):
    """Registra qual ângulo foi usado e qual foi o resultado. 
    resultado: 'respondeu', 'ignorou', 'negou', 'converteu'"""
    entrada = {
        "ts": datetime.now().isoformat(),
        "alvo": cnpj_ou_nome,
        "angulo": angulo,
        "resultado": resultado,
    }
    hist["abordagens"].append(entrada)
    if resultado in ("respondeu", "converteu"):
        hist["taxa_resposta"][angulo] = hist["taxa_resposta"].get(angulo, 0) + 1
    salvar_historico(hist)
    log.info(f"ML | resultado registrado: {angulo} → {resultado}")

def melhor_angulo(hist: dict) -> str:
    """Retorna o ângulo com maior taxa histórica de resposta."""
    taxa = hist.get("taxa_resposta", {})
    if not taxa:
        return "dor_agenda_vazia"     # default inicial
    return max(taxa, key=taxa.get)

# ─── DELAY HUMANO ─────────────────────────────────────────────────────────────

def esperar():
    t = random.uniform(DELAY_MIN, DELAY_MAX)
    log.info(f"Aguardando {t:.1f}s (delay humano)...")
    time.sleep(t)

# ─── GOOGLE MAPS SCRAPER ──────────────────────────────────────────────────────

def buscar_alvos_maps(query: str, max_resultados: int) -> list[dict]:
    """Busca estabelecimentos via Google Maps Places API."""
    client = GoogleMapsClient(key=GOOGLE_MAPS_KEY)
    alvos = []
    log.info(f"Maps: buscando '{query}'...")

    places_result = client.places(query=query)
    alvos.extend(places_result.get("results", []))

    next_token = places_result.get("next_page_token")
    while next_token and len(alvos) < max_resultados:
        esperar()
        places_result = client.places(query=query, page_token=next_token)
        alvos.extend(places_result.get("results", []))
        next_token = places_result.get("next_page_token")

    alvos = alvos[:max_resultados]
    log.info(f"Maps: {len(alvos)} alvos encontrados.")
    return alvos

def detalhar_alvo(place_id: str) -> dict:
    """Busca detalhes completos de um place_id."""
    client = GoogleMapsClient(key=GOOGLE_MAPS_KEY)
    fields = [
        "name", "formatted_address", "formatted_phone_number",
        "website", "rating", "user_ratings_total",
        "opening_hours", "business_status",
    ]
    result = client.place(place_id=place_id, fields=fields)
    return result.get("result", {})

# ─── BUSCA DE INSTAGRAM ───────────────────────────────────────────────────────

def buscar_instagram(nome_negocio: str) -> Optional[str]:
    """Tenta encontrar o Instagram do negócio via busca simples."""
    query = f"{nome_negocio} {CIDADE} site:instagram.com"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=5"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = re.search(r"instagram\.com/([A-Za-z0-9._]+)", href)
            if match:
                handle = match.group(1)
                if handle not in ("p", "reel", "stories", "explore", "accounts"):
                    return f"instagram.com/{handle}"
    except Exception as e:
        log.warning(f"Instagram search falhou para '{nome_negocio}': {e}")
    return None

# ─── AUDITORIA TÉCNICA DO SITE ────────────────────────────────────────────────

def auditar_site(url: Optional[str]) -> dict:
    """Audita o site do alvo: presença, velocidade, mobile, pixel, etc."""
    resultado = {
        "site_existe": False,
        "carrega": False,
        "tempo_resposta_s": None,
        "tem_pixel_fb": False,
        "tem_gtag": False,
        "tem_whatsapp_link": False,
        "mobile_friendly_hint": False,
        "erros": [],
    }
    if not url:
        return resultado
    resultado["site_existe"] = True
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"}
    try:
        inicio = time.time()
        r = requests.get(url, headers=headers, timeout=12)
        resultado["tempo_resposta_s"] = round(time.time() - inicio, 2)
        resultado["carrega"] = r.status_code == 200
        html = r.text
        resultado["tem_pixel_fb"]       = "fbq(" in html or "facebook.net/tr" in html
        resultado["tem_gtag"]           = "gtag(" in html or "google-analytics.com" in html
        resultado["tem_whatsapp_link"]  = "wa.me" in html or "whatsapp.com" in html
        resultado["mobile_friendly_hint"] = "viewport" in html
    except Exception as e:
        resultado["erros"].append(str(e))
    return resultado

# ─── GEMINI: RAIO-X DE SANGRIA ────────────────────────────────────────────────

def gerar_raio_x(dados: dict, historico: dict) -> dict:
    """Usa Gemini 1.5 Flash para gerar diagnóstico e mensagem personalizada."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    angulo = melhor_angulo(historico)

    prompt = f"""
Você é um auditor clínico de infraestrutura digital B2B. Analise estes dados brutos e retorne um JSON com os campos abaixo. SEM texto fora do JSON.

DADOS DO ALVO:
Nome: {dados.get('nome', 'N/A')}
Endereço: {dados.get('endereco', 'N/A')}
Telefone: {dados.get('telefone', 'N/A')}
Site: {dados.get('site', 'Nenhum')}
Instagram: {dados.get('instagram', 'Nenhum')}
Avaliação Google: {dados.get('rating', 'N/A')} ({dados.get('total_avaliacoes', 0)} avaliações)
Site carrega: {dados.get('auditoria', {}).get('carrega', False)}
Tempo resposta site: {dados.get('auditoria', {}).get('tempo_resposta_s', 'N/A')}s
Tem Pixel Facebook: {dados.get('auditoria', {}).get('tem_pixel_fb', False)}
Tem Google Analytics: {dados.get('auditoria', {}).get('tem_gtag', False)}
Link WhatsApp no site: {dados.get('auditoria', {}).get('tem_whatsapp_link', False)}
Mobile friendly: {dados.get('auditoria', {}).get('mobile_friendly_hint', False)}

ÂNGULO DE MAIOR CONVERSÃO HISTÓRICA: {angulo}

Retorne EXATAMENTE este JSON (sem markdown, sem explicação):
{{
  "score_sangria": <inteiro 0-100, quanto maior = mais fácil de converter>,
  "dores_identificadas": ["<dor 1>", "<dor 2>"],
  "oportunidades": ["<oportunidade 1>", "<oportunidade 2>"],
  "nivel_urgencia": "<baixa|media|alta>",
  "mensagem_whatsapp": "<mensagem fria de abertura, máximo 3 linhas, sem emoji, direta ao ponto, focada na dor: {angulo}>",
  "angulo_usado": "{angulo}",
  "proposta_resumida": "<uma linha sobre o que oferecer como upsell>",
  "prioridade_contato": "<1=hoje|2=amanha|3=semana>"
}}
"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        log.error(f"Gemini falhou: {e}")
        return {
            "score_sangria": 0,
            "dores_identificadas": ["erro na análise"],
            "oportunidades": [],
            "nivel_urgencia": "baixa",
            "mensagem_whatsapp": "",
            "angulo_usado": angulo,
            "proposta_resumida": "",
            "prioridade_contato": "3",
        }

# ─── GOOGLE SHEETS ────────────────────────────────────────────────────────────

def conectar_sheets():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GSHEET_ID)
    try:
        ws = sh.worksheet("Sangria_Radar")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Sangria_Radar", rows="500", cols="25")
        cabecalho = [
            "Timestamp", "Nome", "Endereço", "Telefone", "Site", "Instagram",
            "Rating", "Total Avaliações", "Site Carrega", "Tempo Resposta (s)",
            "Pixel FB", "GTag", "WhatsApp no Site", "Mobile Friendly",
            "Score Sangria", "Dores", "Oportunidades", "Urgência",
            "Mensagem WA", "Ângulo", "Proposta", "Prioridade", "Status Follow-up",
        ]
        ws.append_row(cabecalho)
    return ws

def salvar_alvo_sheets(ws, dados: dict, raio_x: dict):
    auditoria = dados.get("auditoria", {})
    linha = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        dados.get("nome", ""),
        dados.get("endereco", ""),
        dados.get("telefone", ""),
        dados.get("site", ""),
        dados.get("instagram", ""),
        dados.get("rating", ""),
        dados.get("total_avaliacoes", ""),
        str(auditoria.get("carrega", "")),
        str(auditoria.get("tempo_resposta_s", "")),
        str(auditoria.get("tem_pixel_fb", "")),
        str(auditoria.get("tem_gtag", "")),
        str(auditoria.get("tem_whatsapp_link", "")),
        str(auditoria.get("mobile_friendly_hint", "")),
        raio_x.get("score_sangria", ""),
        " | ".join(raio_x.get("dores_identificadas", [])),
        " | ".join(raio_x.get("oportunidades", [])),
        raio_x.get("nivel_urgencia", ""),
        raio_x.get("mensagem_whatsapp", ""),
        raio_x.get("angulo_usado", ""),
        raio_x.get("proposta_resumida", ""),
        raio_x.get("prioridade_contato", ""),
        "pendente",
    ]
    ws.append_row(linha)
    log.info(f"Sheets: linha salva para '{dados.get('nome', '?')}'")

# ─── PIPELINE PRINCIPAL ───────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("AGENTE DE SANGRIA B2B — INICIANDO")
    log.info(f"Alvo: {BUSCA} | Máx: {MAX_ALVOS}")
    log.info("=" * 60)

    historico = carregar_historico()
    ws = conectar_sheets()

    alvos_raw = buscar_alvos_maps(BUSCA, MAX_ALVOS)
    esperar()

    processados = 0
    for alvo in alvos_raw:
        place_id = alvo.get("place_id")
        if not place_id:
            continue

        log.info(f"[{processados+1}/{len(alvos_raw)}] Processando: {alvo.get('name', '?')}")

        try:
            detalhe = detalhar_alvo(place_id)
            esperar()

            site = detalhe.get("website")
            instagram = buscar_instagram(detalhe.get("name", ""))
            esperar()

            auditoria = auditar_site(site)
            esperar()

            dados = {
                "nome":           detalhe.get("name", ""),
                "endereco":       detalhe.get("formatted_address", ""),
                "telefone":       detalhe.get("formatted_phone_number", ""),
                "site":           site,
                "instagram":      instagram,
                "rating":         detalhe.get("rating", ""),
                "total_avaliacoes": detalhe.get("user_ratings_total", 0),
                "auditoria":      auditoria,
            }

            raio_x = gerar_raio_x(dados, historico)
            esperar()

            salvar_alvo_sheets(ws, dados, raio_x)
            processados += 1

            log.info(
                f"Score Sangria: {raio_x.get('score_sangria')} | "
                f"Urgência: {raio_x.get('nivel_urgencia')} | "
                f"Prioridade: {raio_x.get('prioridade_contato')}"
            )

        except Exception as e:
            log.error(f"Erro ao processar {alvo.get('name', '?')}: {e}")
            continue

    log.info(f"MISSÃO CONCLUÍDA: {processados} alvos processados e salvos no Sheets.")
    log.info(f"Melhor ângulo atual: {melhor_angulo(historico)}")

if __name__ == "__main__":
    main()
