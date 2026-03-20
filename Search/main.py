from playwright.sync_api import sync_playwright
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 1. CONEXÃO COM O GOOGLE SHEETS
# ==========================================
print("🔄 Conectando ao Google Sheets...")

# Define o que o robô tem permissão para acessar no Google
escopo = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    # O arquivo JSON que você baixou e renomeou precisa estar na mesma pasta!
    credenciais = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", escopo)
    cliente_google = gspread.authorize(credenciais)
    
    # Nome exato da planilha que você criou no seu Google Drive
    planilha = cliente_google.open("Cotacao_Obras").sheet1 
    print("✅ Conexão bem-sucedida com a nuvem!\n")
except Exception as e:
    print(f"❌ Erro ao conectar no Google: {e}")
    print("Verifique se o arquivo 'credenciais.json' está na pasta e se você compartilhou a planilha com o e-mail do robô.")
    exit()

# ==========================================
# 2. O MOTOR DE BUSCA (ROBÔ)
# ==========================================
def orcamento_direto_nuvem(lista_produtos, lojas):
    data_hoje = datetime.now().strftime("%d/%m/%Y")

    with sync_playwright() as p:
        # headless=True faz ele rodar invisível e mais rápido
        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()

        for loja in lojas:
            print(f"🏢 Iniciando buscas na loja: {loja['nome']}...")
            
            for item in lista_produtos:
                print(f"  🔍 Buscando: {item}")
                url = loja['url_busca'].format(item)
                
                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_selector(loja['seletor_card'], timeout=15000)
                except Exception as e:
                    print(f"  ⚠️ Não encontrou '{item}' na {loja['nome']}.")
                    continue 

                # Dá uma rolada na página para carregar as imagens e preços
                page.mouse.wheel(0, 2000)
                time.sleep(2)
                
                cards = page.locator(loja['seletor_card']).all()

                # Pega os 3 primeiros resultados de cada pesquisa
                for card in cards[:3]: 
                    try:
                        nome = card.locator(loja['seletor_nome']).inner_text().replace('\n', ' ').strip()
                        preco_bruto = card.locator(loja['seletor_preco']).inner_text()
                        
                        # Limpa o preço para ficar só o número (ex: 34,90)
                        preco_limpo = preco_bruto.replace('R$', '').replace('\n', ' ').replace('cada', '').replace('à vista', '').strip()
                        
                        # --- ESCREVENDO DIRETO NO GOOGLE SHEETS ---
                        linha_para_adicionar = [data_hoje, item, nome, preco_limpo, loja['nome']]
                        planilha.append_row(linha_para_adicionar)
                        
                        print(f"    ✔️ Salvo na nuvem: {nome[:30]}... | R$ {preco_limpo}")
                    except Exception as e:
                        continue
                        
        browser.close()
        print("\n🎉 MEGA SUCESSO! Todas as buscas foram salvas no seu Google Sheets.")

# ==========================================
# 3. CONFIGURAÇÕES DA BUSCA
# ==========================================
# ==========================================
# A SUPER LISTA DE 100 MATERIAIS PARA OBRA
# ==========================================
materiais_para_obra = [
    # --- Fundação e Estrutura ---
    "cimento 50kg",
    "areia média saco 20kg",
    "areia fina saco 20kg",
    "pedra brita 1 saco",
    "cal hidratada 20kg",
    "tábua de pinus 30cm",
    "sarrafo de pinus 10cm",
    "pontalete de eucalipto",
    "prego 18x27 com cabeça",
    "arame recozido fio 18",
    "vergalhão 10mm 3/8",
    "vergalhão 8mm 5/16",
    "estribo 10x20",
    "malha pop 20x20",
    "impermeabilizante asfáltico 18L",
    "aditivo impermeabilizante 18L",
    "lona preta rolo",
    
    # --- Alvenaria ---
    "tijolo baiano 8 furos",
    "bloco de concreto 14x19x39",
    "bloco cerâmico estrutural",
    "verga de concreto",
    "contraverga de concreto",
    "argamassa para assentamento de blocos",
    "espuma expansiva poliuretano",
    
    # --- Cobertura ---
    "telha fibrocimento 2,44x1,10m",
    "telha cerâmica portuguesa",
    "cumeeira fibrocimento",
    "manta térmica para telhado",
    "prego para telha galvanizado",
    "calha de alumínio",
    "rufo metálico",
    "caixa d'água 1000 litros",
    "boia para caixa d'água",
    
    # --- Hidráulica (Água Fria e Esgoto) ---
    "tubo pvc soldável 25mm",
    "tubo pvc soldável 50mm",
    "tubo pvc esgoto 100mm",
    "tubo pvc esgoto 50mm",
    "joelho pvc soldável 25mm",
    "te pvc soldável 25mm",
    "curva pvc esgoto 100mm",
    "luva pvc soldável 25mm",
    "registro de gaveta 3/4",
    "registro de pressão 3/4",
    "caixa sifonada 100x150x50",
    "caixa de gordura pvc",
    "caixa de inspeção pvc",
    "ralo linear 50cm",
    "ralo seco pvc",
    "adesivo plástico pvc frasco",
    "fita veda rosca 18mm",
    "torneira para pia de cozinha",
    "torneira para lavatório",
    "sifão sanfonado universal",
    "engate flexível pvc",
    "vaso sanitário com caixa acoplada",
    "assento sanitário",
    
    # --- Elétrica ---
    "eletroduto corrugado 3/4 rolo",
    "eletroduto corrugado 1 polegada rolo",
    "caixa de luz 4x2",
    "caixa de luz 4x4",
    "quadro de distribuição 12 a 16 disjuntores",
    "fio cabo flexível 1,5mm rolo 100m",
    "fio cabo flexível 2,5mm rolo 100m",
    "fio cabo flexível 4,0mm rolo 100m",
    "fio cabo flexível 6,0mm rolo 100m",
    "disjuntor din 10A",
    "disjuntor din 16A",
    "disjuntor din 20A",
    "disjuntor din 32A",
    "interruptor simples 1 tecla",
    "interruptor duplo 2 teclas",
    "tomada 10A placa montada",
    "tomada 20A placa montada",
    "fita isolante 20m",
    "lâmpada led 9w",
    "lâmpada led 15w",
    "plafon led sobrepor",
    "chuveiro elétrico 220v",
    
    # --- Revestimentos e Acabamentos ---
    "argamassa ac1",
    "argamassa ac2",
    "argamassa ac3",
    "rejunte acrílico",
    "rejunte epóxi",
    "piso cerâmico 60x60",
    "porcelanato polido",
    "rodape poliestireno",
    "porta de madeira lisa 80x210",
    "batente para porta de madeira",
    "fechadura para porta interna",
    "dobradiça para porta",
    "janela de alumínio 120x150",
    "porta de alumínio balcão",
    
    # --- Pintura ---
    "massa corrida 20kg",
    "massa acrílica 20kg",
    "fundo preparador de paredes 18L",
    "selador acrílico 18L",
    "tinta acrílica fosca branca 18L",
    "tinta acrílica semibrilho branca 18L",
    "esmalte sintético base água 3,6L",
    "solvente aguarrás 900ml",
    "rolo de pintura lã de carneiro",
    "trincha cerda gris",
    "bandeja para pintura",
    "lixa massa grão 120",
    "lixa ferro grão 100",
    "fita crepe larga"
]

config_lojas = [
    {
        "nome": "Leroy Merlin",
        "url_busca": "https://www.leroymerlin.com.br/search?term={}",
        "seletor_card": ".new-product-thumb",
        "seletor_nome": ".css-1eaoahv-ellipsis",
        "seletor_preco": ".css-gt77zv-price-tag"
    },
    {
        "nome": "Telhanorte",
        "url_busca": "https://www.telhanorte.com.br/busca?q={}", 
        "seletor_card": "div.vtex-product-summary-2-x-container",
        "seletor_nome": ".vtex-product-summary-2-x-brandName",
        "seletor_preco": ".vtex-product-summary-2-x-sellingPrice" 
    }
]

# ==========================================
# 4. DISPARAR O ROBÔ
# ==========================================
orcamento_direto_nuvem(materiais_para_obra, config_lojas)