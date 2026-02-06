import webbrowser
import urllib.parse
import time
import gspread
from google.oauth2.service_account import Credentials
import os

# ====== CONFIG ======
SHEET_ID = "113R1o5gsgGO7k2nqLeVwVGsJb4VkzbNNTXUUiN3p8Hw"
ABA_PEDIDOS = "PEDIDOS"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, "service_account.json")

STATUS_ALVO = "NOVO"

# ====== Google Sheets ======
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def conectar_planilha():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    planilha = client.open_by_key(SHEET_ID)
    return planilha.worksheet(ABA_PEDIDOS)

# ====== WhatsApp (wa.me) ======
def abrir_whatsapp(numero, mensagem):
    numero = str(numero)  # 🔥 CORREÇÃO AQUI

    numero = (
        numero.replace("+", "")
              .replace(" ", "")
              .replace("-", "")
              .replace("(", "")
              .replace(")", "")
    )


    texto = urllib.parse.quote(mensagem)
    url = f"https://wa.me/{numero}?text={texto}"
    webbrowser.open(url)

# ====== Mensagem padrão ======
def montar_mensagem_recebido(pedido):
    cliente = pedido.get("cliente", "tudo bem")
    local = pedido.get("local", "—")
    prazo = pedido.get("prazo", "—")
    itens = pedido.get("itens", "—")

    msg = f"""Olá {cliente}! 👷‍♂️

Recebi seu pedido com sucesso ✅  
Já estou cotando com fornecedores da sua região.

📍 Local da obra: {local}
⏱️ Prazo desejado: {prazo}
🧱 Itens:
{itens}

Em breve te retorno com as melhores opções de preço e prazo.
"""
    return msg

# ====== MAIN ======
def main():
    ws = conectar_planilha()
    registros = ws.get_all_records()

    pedidos_novos = [
        (idx + 2, row)  # +2 por causa do header
        for idx, row in enumerate(registros)
        if str(row.get("status", "")).strip().upper() == STATUS_ALVO
    ]

    if not pedidos_novos:
        print("Nenhum pedido com status NOVO encontrado.")
        return

    # 👉 Processa APENAS o primeiro pedido (MVP consciente)
    linha, pedido = pedidos_novos[0]

    numero = pedido.get("whatsapp")
    if not numero:
        print("Pedido sem número de WhatsApp.")
        return

    mensagem = montar_mensagem_recebido(pedido)

    print(f"Abrindo WhatsApp para o pedido ID {pedido.get('id')}")
    abrir_whatsapp(numero, mensagem)

    print("WhatsApp aberto. Envie a mensagem manualmente.")
    print("Depois disso, você pode atualizar o status na planilha.")

if __name__ == "__main__":
    main()
