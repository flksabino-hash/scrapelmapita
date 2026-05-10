# AGENTE DE SANGRIA — GUIA DE EXECUÇÃO IMEDIATA

**Status:** Tudo pronto para rodar. Seus dados reais já estão nos scripts.

---

## ⚠️ PRÉ-REQUISITO CRÍTICO

Você precisa completar **UM** passo antes de tudo:

### Compartilhar a planilha com a service account

Abra sua planilha do Google Sheets:
```
https://docs.google.com/spreadsheets/d/1MrFTpc1F_8bADeLcTXc9O4NhiegNuC-Mqd2J1SgERm0/edit
```

Clique em **Compartilhar** (botão verde, canto superior direito) → Cole este email como **Editor**:
```
sangria-sheets@lofty-root-494507-c2.iam.gserviceaccount.com
```

Sem esse passo, o script retorna: `gspread.exceptions.SpreadsheetNotFound`

---

## PASSO 1 — Setup Local (EndeavourOS)

Na pasta onde você tem o `b2b_radar_pro.py` e `credentials.json`:

```bash
# Baixe os scripts de setup e deploy
cd ~/sangria  # ou a pasta onde estão seus arquivos

# Dar permissão e executar setup
chmod +x setup_sangria_local.sh
./setup_sangria_local.sh
```

**O script vai:**
1. Criar venv isolado
2. Instalar dependências Python
3. Pedir as 3 chaves (Gemini, Maps, Sheets ID)
4. Rodar smoke test para validar tudo
5. Criar arquivo `.env` com suas variáveis

**Esperado no final:**
```
[OK] Sheets OK: Sangria_Radar
[OK] Maps OK: Restaurante XYZ
[OK] PRONTO PARA DEPLOY.
```

Se aparecer erro, verifique:
- `credentials.json` está no diretório?
- A planilha foi compartilhada com o email da service account?

---

## PASSO 2 — Teste Local Rápido (Opcional)

Se você quer rodar uma rodada completa do agente **no EndeavourOS antes de deployar**:

```bash
# Ativar venv e variáveis
source venv/bin/activate
source .env

# Rodar uma busca rápida (5-10 minutos, gera ~5 alvos)
export NICHO="restaurantes"  # altere se quiser testar outro nicho
python3 b2b_radar_pro.py
```

Ele vai:
- Buscar 5 restaurantes em Batel
- Auditar sites
- Gerar raio-x com Gemini
- Salvar na planilha

**Log ao vivo:**
```bash
# em outro terminal
tail -f sangria.log
```

Verifique na planilha se as linhas chegaram com dados corretos (Score Sangria, Dores, Mensagem WA, etc).

---

## PASSO 3 — Deploy para Google Cloud VM

Quando o teste local validar que tudo funciona:

```bash
# Ainda no mesmo diretório
chmod +x deploy_sangria_READY.sh
./deploy_sangria_READY.sh
```

**O que acontece:**

1. **Fase 0** — Verifica se gcloud está instalado (você já instalou via yay)
2. **Fase 1** — Abre browser para login GCP (uma única vez)
3. **Fase 2** — Cria a VM `sangria-vm` em São Paulo (e2-standard-2)
4. **Fase 3** — Transfere `b2b_radar_pro.py` e `credentials.json` para a VM
5. **Fase 4** — Configura Python venv, n8n, cron na VM (15-20 minutos)
5. **Fase 5** — Exibe o IP da VM e URL do n8n

**Esperado ao final:**
```
════════════════════════════════════════════
  DEPLOY CONCLUÍDO — SANGRIA AGENTE
════════════════════════════════════════════
  IP:   35.198.xxx.xxx
  n8n:  http://35.198.xxx.xxx:5678
  Login: admin / sangria2025
  Cron:  seg, qua, sex — 09:00 BRT
════════════════════════════════════════════
```

---

## PASSO 4 — Acessar n8n e montar os Nós

Quando o deploy terminar, abra no browser:
```
http://[IP_DA_VM]:5678
```

Login: `admin` / `sangria2025`

Crie um novo workflow e adicione os 10 nodes descritos no documento `sangria_pacote_operacional.md`.

---

## PASSO 5 — Monitorar o Cron

A VM executará o agente automaticamente:
- **Segunda, quarta, sexta**
- **Às 09:00 (horário de Brasília)**

Para monitorar manualmente na VM:

```bash
# SSH direto (nenhuma chave para configurar)
gcloud compute ssh sangria-vm --zone=southamerica-east1-b

# Na VM:
tail -f ~/sangria/sangria.log         # Log em tempo real
cat ~/sangria/historico_abordagens.json   # Resultado do ML
```

---

## TROUBLESHOOTING RÁPIDO

### Erro: `SpreadsheetNotFound`
→ A planilha não foi compartilhada com `sangria-sheets@lofty-root-494507-c2.iam.gserviceaccount.com`
→ Abra a planilha e compartilhe agora

### Erro: `REQUEST_DENIED` no Maps
→ O API Key 4 não tem permissão para Places API
→ Verifique em: `console.cloud.google.com/apis/library/places.googleapis.com?project=lofty-root-494507-c2`
→ Deve estar **Habilitado** (botão azul)

### Erro: `gcloud not found`
→ Execute: `source /etc/profile.d/google-cloud-cli.sh`

### Erro: `credential file not found`
→ `credentials.json` precisa estar no diretório onde você roda o script

---

## CUSTO ESTIMADO

Com sua cota de **R$1.700**:

| Item | Custo/mês |
|------|-----------|
| VM e2-standard-2 (São Paulo) | ~R$ 60 |
| Disco SSD 20GB | ~R$ 8 |
| IP estático | ~R$ 15 |
| Egress | ~R$ 2 |
| **Total** | **~R$ 85** |

**Runway: R$1.700 ÷ R$85 = ~20 meses** sem custo adicional

---

## PRÓXIMOS PASSOS APÓS DEPLOY

1. ✓ SSH na VM e rodar manualmente: `source venv/bin/activate && source .env && python3 b2b_radar_pro.py`
2. ✓ Abrir n8n e montar os 10 nodes do funil veneno
3. ✓ Configurar webhooks para integrar com seu CRM/whatsapp
4. ✓ Monitorar `historico_abordagens.json` — o agente aprende qual ângulo converte melhor a cada rodada
5. ✓ Ajustar variáveis (NICHO, BAIRRO, MAX_ALVOS) para escalar

---

**Status final:** Tudo está pronto. O deploy é 100% não-interativo exceto a autenticação initial do gcloud.

Tempo total estimado: **5 minutos de setup local + 20 minutos de deploy**.

Mande print do console do GCP ou da planilha quando as primeiras linhas chegarem. ✓
