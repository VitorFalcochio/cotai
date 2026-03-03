import os
import re
import time
import sys
import requests
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from typing import Any

try:
    from groq import Groq
except ImportError:
    Groq = None

# ===== CARREGAR VARIÁVEIS DE AMBIENTE =====
load_dotenv(override=True)

# Evita erro de encoding em consoles Windows (cp1252) quando o bot imprime emojis.
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# ===== CONFIGURAÇÕES GERAIS =====
SHEET_ID = "113R1o5gsgGO7k2nqLeVwVGsJb4VkzbNNTXUUiN3p8Hw"
ABA_PEDIDOS = "PEDIDOS"

WAHA_BASE_URL = os.getenv("WAHA_BASE_URL", "http://localhost:3000").strip().rstrip("/")
WAHA_SESSION = os.getenv("WAHA_SESSION", "default").strip() or "default"
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "").strip()
try:
    WAHA_CHATS_LIMIT = max(1, int(os.getenv("WAHA_CHATS_LIMIT", "10")))
except ValueError:
    WAHA_CHATS_LIMIT = 10

POLL_SECONDS = 5
DEBUG = True

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, "service_account.json")

STATUS_NOVO = "NOVO"

# Configurações do Bot de WhatsApp (WAHA)
FORCE_PHONE = "5517996657737"
FORCE_CHAT_ID = f"{FORCE_PHONE}@c.us"

# Configurações da NOVA (Groq + ML)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
MERCADO_LIVRE_SITE = os.getenv("MERCADO_LIVRE_SITE", "MLB")

client_groq = Groq(api_key=GROQ_API_KEY) if (Groq and GROQ_API_KEY) else None

# Frases-gatilho para salvar na planilha (Opcional, mantido do seu código original)
GATILHOS = [
    "quero uma cotação", "quero uma cotacao", "cotação", "cotacao",
    "orçamento", "orcamento", "orçar", "orcar", "#cotar_nova"
]

# ===== FUNÇÕES HELPERS (Gerais e WAHA) =====
def log(*args):
    if DEBUG:
        print(*args, flush=True)

def waha_headers() -> dict[str, str]:
    headers = {}
    if WAHA_API_KEY:
        headers["X-Api-Key"] = WAHA_API_KEY
    return headers

def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", str(s or ""))

def normalize_chat_to_phone_digits(chat_id: str) -> str:
    chat_id = str(chat_id or "")
    if "@" in chat_id:
        chat_id = chat_id.split("@", 1)[0]
    digits = only_digits(chat_id)
    if len(digits) in (10, 11):
        digits = "55" + digits
    return digits

def clean_text(s: str) -> str:
    return re.sub(r"[\u200e\u200f\u202a-\u202e]", "", s or "")

def waha_send_text(chat_id: str, text: str):
    payload = {"session": WAHA_SESSION, "chatId": chat_id, "text": text}
    try:
        r = requests.post(
            f"{WAHA_BASE_URL}/api/sendText",
            json=payload,
            headers=waha_headers(),
            timeout=30,
        )
        if r.status_code >= 400:
            log(f"Erro ao enviar msg WAHA: {r.status_code} {r.text}")
        return r.json() if r.text else {"ok": True}
    except Exception as e:
        log(f"Falha na conexão com WAHA: {e}")
        return {"ok": False}

def waha_list_chats(limit=WAHA_CHATS_LIMIT):
    r = requests.get(
        f"{WAHA_BASE_URL}/api/{WAHA_SESSION}/chats",
        params={"limit": limit},
        headers=waha_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def waha_get_messages_try(chat_id: str, limit=15):
    tries = [
        (f"{WAHA_BASE_URL}/api/{WAHA_SESSION}/chats/{chat_id}/messages", {"limit": limit}),
        (f"{WAHA_BASE_URL}/api/{WAHA_SESSION}/messages", {"chatId": chat_id, "limit": limit}),
        (f"{WAHA_BASE_URL}/api/messages", {"session": WAHA_SESSION, "chatId": chat_id, "limit": limit}),
    ]
    last = None
    for url, params in tries:
        try:
            r = requests.get(url, params=params, headers=waha_headers(), timeout=30)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "messages" in data: return data["messages"]
            if isinstance(data, dict) and "data" in data: return data["data"]
            if isinstance(data, list): return data
            return []
        except Exception as e:
            last = e
    raise last

def extract_text(msg: dict) -> str:
    for k in ("body", "text", "message", "caption"):
        v = msg.get(k)
        if isinstance(v, str) and v.strip(): return v.strip()
    return ""

def is_incoming(msg: dict) -> bool:
    if "fromMe" in msg: return not bool(msg.get("fromMe"))
    if "isFromMe" in msg: return not bool(msg.get("isFromMe"))
    return True

def get_timestamp(msg: dict) -> int:
    for k in ("timestamp", "t", "time", "messageTimestamp"):
        v = msg.get(k)
        if isinstance(v, (int, float)): return int(v)
        if isinstance(v, str) and v.isdigit(): return int(v)
    return 0

# ===== FUNÇÕES GOOGLE SHEETS =====
def conectar_worksheet():
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        return sh.worksheet(ABA_PEDIDOS)
    except requests.exceptions.ConnectionError as e:
        print(f"[Google Sheets] Falha de conexao: {e}. Vou tentar novamente.")
        return None
    except Exception as e:
        print(f"[Google Sheets] Nao foi possivel conectar: {e}. Vou tentar novamente.")
        return None

def get_next_id(ws) -> int:
    try:
        records = ws.get_all_records()
        max_id = 0
        for r in records:
            try: max_id = max(max_id, int(str(r.get("id", "")).strip() or 0))
            except: pass
        return max_id + 1
    except:
        return 1

def pedido_ja_existe(ws, phone_digits: str, itens_texto: str) -> bool:
    try:
        records = ws.get_all_records()
        for r in records:
            w = only_digits(r.get("whatsapp", ""))
            if w and len(w) in (10, 11): w = "55" + w
            if w != phone_digits: continue

            status = str(r.get("status", "")).strip().upper()
            if status in {"NOVO", "RECEBIDO", "EM_ATENDIMENTO", "ABERTO", "COTANDO"}:
                existing = str(r.get("itens_json", "") or r.get("itens", "")).strip()
                if existing == itens_texto.strip(): return True
        return False
    except:
        return False

def append_pedido(ws, phone_digits: str, pedido: dict) -> int:
    if not ws: return 0
    try:
        new_id = get_next_id(ws)
        row = [
            new_id, pedido.get("cliente", ""), phone_digits,
            pedido.get("local", ""), pedido.get("prazo", ""),
            pedido.get("itens_texto", ""), STATUS_NOVO,
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
        return new_id
    except Exception as e:
        log("Erro ao salvar no Sheets:", e)
        return 0

# ===== FUNÇÕES DA NOVA (Busca e Inteligência) =====
def buscar_mercado_livre(item: str) -> list[dict[str, Any]]:
    url = f"https://api.mercadolibre.com/sites/{MERCADO_LIVRE_SITE}/search"
    try:
        # Aumentei o limite para 10 para ter mais chances de achar produtos relevantes
        response = requests.get(url, params={"q": item, "limit": 10}, timeout=15)
        response.raise_for_status()
        results = response.json().get("results", [])
    except Exception as e:
        log(f"Erro na busca do ML para {item}: {e}")
        return []

    saida: list[dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict): continue
        saida.append({
            "titulo": r.get("title", ""),
            "preco": r.get("price", 0),
            "link": r.get("permalink", "")
        })
    return saida[:5] # Retorna as 5 melhores opções

def extrair_produto_fallback(mensagem: str) -> str:
    texto = re.sub(r"#COTAR_NOVA", "", mensagem, flags=re.IGNORECASE).strip()
    linhas = [l.strip(" -\t") for l in texto.splitlines() if l.strip()]
    for linha in linhas:
        if linha.lower().startswith(("nome:", "empresa:", "prazo:", "local:", "obs:")): continue
        if linha.lower().startswith("itens:"): linha = linha.split(":", 1)[-1].strip()
        linha = re.sub(r"^\d+[\).]\s*", "", linha).strip()
        if linha: return linha
    return "material de construcao"

def disparar_busca_nova(mensagem_cliente: str) -> str:
    """Função principal da IA que lê o pedido e busca os preços."""
    if client_groq is None:
        return "⚠️ A IA da NOVA não está configurada (Chave Groq ausente)."

    try:
        # 1) Extrai o produto principal
        prompt_extrair = (
            "Extraia apenas o nome do produto principal desta mensagem para busca de preco. "
            "Retorne apenas o nome do produto, sem explicacoes.\n\n"
            f"Mensagem:\n{mensagem_cliente}"
        )
        res_extrair = client_groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt_extrair}],
            temperature=0,
        )
        produto = (res_extrair.choices[0].message.content or "").strip()
        if not produto:
            produto = extrair_produto_fallback(mensagem_cliente)

        log(f"🧠 NOVA identificou o produto: {produto}")

        # 2) Busca real no ML
        precos_encontrados = buscar_mercado_livre(produto)

        # 3) Formata a resposta
        if not precos_encontrados:
            return (f"😔 Não encontrei ofertas confiáveis para '{produto}' no momento. "
                    "Poderia me enviar mais detalhes como marca ou especificação?")

        prompt_final = (
            "Você é a NOVA, a assistente inteligente da Cotai. Responda no WhatsApp para um cliente. "
            "Seja profissional, objetiva e use emojis.\n"
            f"Produto Buscado: {produto}\n"
            f"Ofertas Encontradas (JSON): {precos_encontrados}\n\n"
            "Sua tarefa: Apresente as 3 melhores ofertas de forma clara (Nome, Preço e o Link). "
            "No final, pergunte se o cliente quer cotar mais alguma coisa."
        )
        
        res_final = client_groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt_final}],
            temperature=0.2,
        )

        return res_final.choices[0].message.content

    except Exception as exc:
        log("Erro na Inteligência da NOVA:", exc)
        return "⚠️ Tive um pequeno problema ao processar sua cotação agora. Nossa equipe já foi notificada."


# ===== PARSER DE PEDIDO (Extrai dados estruturados para a planilha) =====
def parse_pedido(texto: str) -> dict | None:
    t = clean_text((texto or "").strip())
    low = t.lower()

    if not any(g in low for g in GATILHOS): return None
    if "itens" not in low: return None

    normalized = t.replace("•", "\n•").replace("*", "\n*")
    raw_lines = [l.strip() for l in normalized.splitlines() if l.strip()]
    lines = [re.sub(r"^[•\*\-\–]\s*", "", l).strip() for l in raw_lines]

    data = {"cliente": "", "empresa": "", "prazo": "", "local": "", "itens": []}
    modo_itens = False

    for line in lines:
        l_low = line.lower().strip()
        if l_low.startswith("itens"):
            modo_itens = True
            if ":" in line:
                after = line.split(":", 1)[1].strip()
                if after: data["itens"].append(after)
            continue

        if modo_itens:
            if ":" in line:
                k = line.split(":", 1)[0].lower()
                if any(x in k for x in ["prazo", "local", "nome", "empresa"]):
                    modo_itens = False

            if modo_itens:
                item = re.sub(r"^[\s\d]+[\)\.\-]\s*", "", line).strip()
                item = re.sub(r"^[\-\*]\s*", "", item).strip()
                if item: data["itens"].append(item)
                continue

        if ":" in line and not modo_itens:
            chave, valor = line.split(":", 1)
            chave = chave.strip().lower()
            valor = valor.strip()
            if "nome" in chave: data["cliente"] = valor
            elif "empresa" in chave: data["empresa"] = valor
            elif "prazo" in chave: data["prazo"] = valor
            elif "local" in chave: data["local"] = valor

    if not data["itens"]: return None
    data["itens_texto"] = "\n".join([i.strip() for i in data["itens"] if i.strip()]).strip()
    return data

# ===== LOOP PRINCIPAL DO BOT =====
def main():
    ws = None
    last_msg_ts_by_chat = {}

    log("🤖 Bot da NOVA (WhatsApp + Inteligência) iniciado. Ctrl+C para parar.")
    log(f"🧪 Modo teste ativo: Lendo mensagens de {FORCE_PHONE}")

    while True:
        try:
            if ws is None:
                try:
                    ws = conectar_worksheet()
                except requests.exceptions.ConnectionError as e:
                    print(f"[Google Sheets] Sem conexao: {e}.")
                    ws = None
                except Exception as e:
                    print(f"[Google Sheets] Erro de conexao: {e}.")
                    ws = None

            try:
                chats = waha_list_chats(limit=WAHA_CHATS_LIMIT)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                body = (e.response.text or "").strip() if e.response is not None else ""
                if status == 401:
                    print("[WAHA] Nao autorizado. Verifique WAHA_API_KEY no .env.")
                elif status == 422:
                    print(
                        "[WAHA] Sessao ainda nao esta WORKING (ex.: SCAN_QR_CODE). "
                        "Abra http://localhost:3000/dashboard e conecte a sessao."
                    )
                else:
                    print(f"[WAHA] Erro HTTP ao listar chats ({status}): {body[:200]}")
                time.sleep(POLL_SECONDS)
                continue
            except requests.exceptions.ConnectionError as e:
                print(f"[WAHA] Sem conexao em {WAHA_BASE_URL}: {e}. Vou tentar novamente.")
                time.sleep(POLL_SECONDS)
                continue
            except Exception as e:
                print(f"[WAHA] Erro ao listar chats: {e}. Vou tentar novamente.")
                time.sleep(POLL_SECONDS)
                continue

            chat_ids = [str(c.get("id") or c.get("chatId")) for c in chats if (c.get("id") or c.get("chatId"))]
            if FORCE_CHAT_ID and FORCE_CHAT_ID not in chat_ids:
                chat_ids.append(FORCE_CHAT_ID)

            for chat_id in chat_ids:
                if not str(chat_id).endswith("@c.us"): continue # Só processa DMs

                try:
                    msgs = waha_get_messages_try(chat_id, limit=15)
                except:
                    continue

                incoming = [m for m in msgs if isinstance(m, dict) and is_incoming(m)]
                if not incoming: continue

                incoming.sort(key=get_timestamp)
                last_msg = incoming[-1]
                ts = get_timestamp(last_msg)

                if ts <= last_msg_ts_by_chat.get(chat_id, 0): continue

                text = extract_text(last_msg)
                if not text:
                    last_msg_ts_by_chat[chat_id] = ts
                    continue

                log(f"📩 Nova mensagem de {chat_id}: {text[:50]}...")

                # --- FLUXO DA NOVA: Verifica se tem o trigger ---
                if "#COTAR_NOVA" in text.upper():
                    log("🎯 Trigger #COTAR_NOVA detectado!")
                    
                    # 1. Avisa o cliente imediatamente
                    waha_send_text(chat_id, "🤖 Pedido Recebido! A NOVA está analisando os itens e buscando os melhores preços para você agora...")

                    # 2. Registra na Planilha (Opcional, mas útil)
                    pedido = parse_pedido(text)
                    phone_digits = normalize_chat_to_phone_digits(chat_id)
                    
                    if pedido and ws:
                        if not pedido_ja_existe(ws, phone_digits, pedido["itens_texto"]):
                            append_pedido(ws, phone_digits, pedido)
                            log("✅ Pedido salvo na planilha.")

                    # 3. Dispara a inteligência de busca e responde com os preços
                    resultado_busca = disparar_busca_nova(text)
                    waha_send_text(chat_id, resultado_busca)
                    log("✅ Cotação enviada ao cliente com sucesso.")

                last_msg_ts_by_chat[chat_id] = ts

        except KeyboardInterrupt:
            print("\n🛑 Parando bot.")
            return
        except Exception as e:
            log("⚠️ Erro no loop principal:", repr(e))

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
