#!/usr/bin/env bash
# ============================================================
# setup_sangria_local.sh — Setup local no EndeavourOS
# Cria venv, baixa dependências, testa credenciais
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'
BLU='\033[0;34m'; NC='\033[0m'; BOLD='\033[1m'

log()  { echo -e "${BLU}[SETUP]${NC} $*"; }
ok()   { echo -e "${GRN}[OK]${NC} $*"; }
warn() { echo -e "${YLW}[WARN]${NC} $*"; }
die()  { echo -e "${RED}[ERRO]${NC} $*"; exit 1; }

# ─── PREPARAÇÃO ─────────────────────────────────────────────
WORK_DIR="$PWD"
if [[ ! -f "b2b_radar_pro.py" ]] || [[ ! -f "credentials.json" ]]; then
  die "Execute do diretório contendo b2b_radar_pro.py e credentials.json"
fi

log "Setup local no EndeavourOS"
echo ""

# 1. Criar venv
log "Criando venv..."
python3 -m venv venv
source venv/bin/activate
ok "venv ativo"

# 2. Instalar dependências
log "Instalando dependências Python..."
pip install -q google-generativeai googlemaps gspread google-auth requests beautifulsoup4
ok "Dependências instaladas"

# 3. Pedir chaves
echo ""
log "Configure as variáveis de ambiente:"
echo ""
read -p "  GEMINI_API_KEY (https://aistudio.google.com): " GEMINI_API_KEY
read -p "  GOOGLE_MAPS_KEY (seu API Key 4): " GOOGLE_MAPS_KEY
read -p "  GSHEET_ID (já preenchido = 1MrFTpc1F_8bADeLcTXc9O4NhiegNuC-Mqd2J1SgERm0): " GSHEET_ID_INPUT
GSHEET_ID="${GSHEET_ID_INPUT:-1MrFTpc1F_8bADeLcTXc9O4NhiegNuC-Mqd2J1SgERm0}"

# 4. Smoke test
log "Executando smoke test..."
python3 -c "
import os, gspread, googlemaps
from google.oauth2.service_account import Credentials

os.environ['GEMINI_API_KEY'] = '$GEMINI_API_KEY'
os.environ['GOOGLE_MAPS_KEY'] = '$GOOGLE_MAPS_KEY'
os.environ['GSHEET_ID'] = '$GSHEET_ID'
os.environ['CREDENTIALS_FILE'] = 'credentials.json'

try:
  creds = Credentials.from_service_account_file('credentials.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
  gc = gspread.authorize(creds)
  sh = gc.open_by_key('$GSHEET_ID')
  print('Sheets OK: ' + sh.title)
except Exception as e:
  print('Sheets FALHOU: ' + str(e))
  exit(1)

try:
  gm = googlemaps.Client(key='$GOOGLE_MAPS_KEY')
  r = gm.places('restaurante Batel Curitiba')
  print('Maps OK: ' + r['results'][0]['name'])
except Exception as e:
  print('Maps FALHOU: ' + str(e))
  exit(1)

print('PRONTO PARA DEPLOY.')
" || die "Smoke test falhou"

ok "Tudo validado"

# 5. Criar .env para o deploy
log "Criando arquivo .env para deploy..."
cat > .env <<EOF
export GEMINI_API_KEY="$GEMINI_API_KEY"
export GOOGLE_MAPS_KEY="$GOOGLE_MAPS_KEY"
export GSHEET_ID="$GSHEET_ID"
export CREDENTIALS_FILE="credentials.json"
EOF
ok "Arquivo .env criado"

echo ""
echo -e "${BOLD}════════════════════════════════════════════${NC}"
echo -e "${GRN}  SETUP LOCAL CONCLUÍDO${NC}"
echo -e "${BOLD}════════════════════════════════════════════${NC}"
echo ""
echo "Próximos passos:"
echo "  1. source venv/bin/activate"
echo "  2. chmod +x deploy_sangria_READY.sh"
echo "  3. ./deploy_sangria_READY.sh"
echo ""
