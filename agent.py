import os
import re
import time
import requests
import gspread
from google.oauth2.service_account import Credentials

# ===== CONFIG =====
SHEET_ID = "113R1o5gsgGO7k2nqLeVwVGsJb4VkzbNNTXUUiN3p8Hw"
ABA_PEDIDOS = "PEDIDOS"

WAHA_BASE_URL = "http://localhost:3000"
WAHA_SESSION = "default"

POLL_SECONDS = 5
DEBUG = True

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, "service_account.json")

STATUS_NOVO = "NOVO"

# ✅ seu número pra forçar leitura do chat (modo teste garantido)
FORCE_PHONE = "5517996657737"
FORCE_CHAT_ID = f"{FORCE_PHONE}@c.us"

# Frases-gatilho (o site pode incluir no texto)
GATILHOS = [
    "quero uma cotação",
    "quero uma cotacao",
    "cotação",
    "cotacao",
    "orçamento",
    "orcamento",
    "orçar",
    "orcar",
]

# ===== Helpers =====
def log(*args):
    if DEBUG:
        print(*args)

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
    # remove caracteres invisíveis comuns
    return re.sub(r"[\u200e\u200f\u202a-\u202e]", "", s or "")

def waha_send_text(chat_id: str, text: str):
    payload = {"session": WAHA_SESSION, "chatId": chat_id, "text": text}
    r = requests.post(f"{WAHA_BASE_URL}/api/sendText", json=payload, timeout=30)
    if r.status_code >= 400:
        raise requests.HTTPError(f"{r.status_code} {r.text}")
    return r.json() if r.text else {"ok": True}

def waha_list_chats(limit=500):
    r = requests.get(
        f"{WAHA_BASE_URL}/api/{WAHA_SESSION}/chats",
        params={"limit": limit},
        timeout=30
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
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "messages" in data:
                return data["messages"]
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            last = e
    raise last

def extract_text(msg: dict) -> str:
    for k in ("body", "text", "message", "caption"):
        v = msg.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def is_incoming(msg: dict) -> bool:
    if "fromMe" in msg:
        return not bool(msg.get("fromMe"))
    if "isFromMe" in msg:
        return not bool(msg.get("isFromMe"))
    return True

def get_timestamp(msg: dict) -> int:
    for k in ("timestamp", "t", "time", "messageTimestamp"):
        v = msg.get(k)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return 0

# ===== Sheets =====
def conectar_worksheet():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    return sh.worksheet(ABA_PEDIDOS)

def get_next_id(ws) -> int:
    records = ws.get_all_records()
    max_id = 0
    for r in records:
        try:
            max_id = max(max_id, int(str(r.get("id", "")).strip() or 0))
        except Exception:
            pass
    return max_id + 1

def pedido_ja_existe(ws, phone_digits: str, itens_texto: str) -> bool:
    records = ws.get_all_records()
    for r in records:
        w = only_digits(r.get("whatsapp", ""))
        if w and len(w) in (10, 11):
            w = "55" + w
        if w != phone_digits:
            continue

        status = str(r.get("status", "")).strip().upper()
        if status in {"NOVO", "RECEBIDO", "EM_ATENDIMENTO", "ABERTO", "COTANDO"}:
            existing = str(r.get("itens_json", "") or r.get("itens", "")).strip()
            if existing == itens_texto.strip():
                return True
    return False

def append_pedido(ws, phone_digits: str, pedido: dict) -> int:
    """
    Assumindo header:
    id | cliente | whatsapp | local | prazo | itens_json | status | ...
    """
    new_id = get_next_id(ws)
    row = [
        new_id,
        pedido.get("cliente", ""),
        phone_digits,
        pedido.get("local", ""),
        pedido.get("prazo", ""),
        pedido.get("itens_texto", ""),
        STATUS_NOVO,
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    return new_id

# ===== Parser (aceita • * - e 1 linha ou várias) =====
def parse_pedido(texto: str) -> dict | None:
    t = clean_text((texto or "").strip())
    low = t.lower()

    if not any(g in low for g in GATILHOS):
        return None
    if "itens" not in low:
        return None

    # quebra por bullets mesmo se vier tudo em uma linha
    normalized = t.replace("•", "\n•").replace("*", "\n*")
    raw_lines = [l.strip() for l in normalized.splitlines() if l.strip()]

    # remove bullets no começo
    lines = [re.sub(r"^[•\*\-\–]\s*", "", l).strip() for l in raw_lines]

    data = {"cliente": "", "empresa": "", "prazo": "", "local": "", "itens": []}
    modo_itens = False

    for line in lines:
        l_low = line.lower().strip()

        if l_low.startswith("itens"):
            modo_itens = True
            if ":" in line:
                after = line.split(":", 1)[1].strip()
                if after:
                    data["itens"].append(after)
            continue

        if modo_itens:
            # se apareceu outro campo, sai do modo itens
            if ":" in line:
                k = line.split(":", 1)[0].lower()
                if any(x in k for x in ["prazo", "local", "nome", "empresa"]):
                    modo_itens = False

            if modo_itens:
                item = re.sub(r"^[\s\d]+[\)\.\-]\s*", "", line).strip()
                item = re.sub(r"^[\-\*]\s*", "", item).strip()
                if item:
                    data["itens"].append(item)
                continue

        if ":" in line and not modo_itens:
            chave, valor = line.split(":", 1)
            chave = chave.strip().lower()
            valor = valor.strip()

            if "nome" in chave:
                data["cliente"] = valor
            elif "empresa" in chave:
                data["empresa"] = valor
            elif "prazo" in chave:
                data["prazo"] = valor
            elif "local" in chave:
                data["local"] = valor

    if not data["itens"]:
        return None

    data["itens_texto"] = "\n".join([i.strip() for i in data["itens"] if i.strip()]).strip()
    return data

# ===== Loop =====
def main():
    ws = conectar_worksheet()
    last_msg_ts_by_chat = {}

    log("🤖 Criador de pedido por mensagem iniciado. Ctrl+C para parar.")
    log("🧪 Modo teste: FORCE_CHAT_ID =", FORCE_CHAT_ID)

    while True:
        try:
            chats = waha_list_chats(limit=500)

            # monta lista de chatIds + adiciona o chat forçado
            chat_ids = []
            for c in chats:
                cid = c.get("id") or c.get("chatId")
                if cid:
                    chat_ids.append(str(cid))

            if FORCE_CHAT_ID and FORCE_CHAT_ID not in chat_ids:
                chat_ids.append(FORCE_CHAT_ID)

            # debug rápido pra ver se está vindo chat
            log("TOTAL CHATS:", len(chats), "| checando:", len(chat_ids))

            for chat_id in chat_ids:
                # só chats de pessoa
                if not str(chat_id).endswith("@c.us"):
                    continue

                try:
                    msgs = waha_get_messages_try(chat_id, limit=15)
                except Exception as e:
                    log("⚠️ Não consegui ler mensagens de", chat_id, "->", e)
                    continue

                incoming = [m for m in msgs if isinstance(m, dict) and is_incoming(m)]
                if not incoming:
                    continue

                incoming.sort(key=get_timestamp)
                last_msg = incoming[-1]
                ts = get_timestamp(last_msg)

                if ts <= last_msg_ts_by_chat.get(chat_id, 0):
                    continue

                text = extract_text(last_msg)
                if not text:
                    last_msg_ts_by_chat[chat_id] = ts
                    continue

                log("DEBUG última msg:", chat_id, "ts=", ts, "|", (text[:120] + "..." if len(text) > 120 else text))

                pedido = parse_pedido(text)
                if not pedido:
                    last_msg_ts_by_chat[chat_id] = ts
                    continue

                phone_digits = normalize_chat_to_phone_digits(chat_id)
                log("📩 Pedido detectado de", phone_digits)

                if pedido_ja_existe(ws, phone_digits, pedido["itens_texto"]):
                    log("↩️ Já existia pedido parecido, ignorando para não duplicar.")
                    last_msg_ts_by_chat[chat_id] = ts
                    continue

                new_id = append_pedido(ws, phone_digits, pedido)

                reply = (
                    f"✅ Pedido criado com sucesso!\n"
                    f"ID: {new_id}\n"
                    f"👤 Cliente: {pedido.get('cliente','—')}\n"
                    f"🏢 Empresa: {pedido.get('empresa','—')}\n"
                    f"📍 Local: {pedido.get('local','—')}\n"
                    f"⏱️ Prazo: {pedido.get('prazo','—')}\n"
                    f"🧱 Itens:\n{pedido.get('itens_texto','—')}\n\n"
                    f"Agora é só aguardar que vamos cotar e te retornar."
                )

                waha_send_text(chat_id, reply)
                log("✅ Pedido criado e confirmado. ID:", new_id)

                last_msg_ts_by_chat[chat_id] = ts

        except KeyboardInterrupt:
            print("\n🛑 Parando.")
            return
        except Exception as e:
            log("⚠️ Erro no loop:", repr(e))

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
