# AUTOCAD IA

Beta inicial para a nova frente do Cotai que transforma descricoes de projeto em uma planta 2D simples exportada em DXF.

## Objetivo desta fase

Nesta beta, a IA ainda nao tenta substituir um arquiteto nem gerar um projeto executivo completo. O foco aqui e:

- receber um pedido em linguagem natural ou JSON estruturado
- converter isso para um modelo geometrico simples
- distribuir os ambientes em uma planta 2D basica
- exportar um arquivo `.dxf` que pode ser aberto no AutoCAD

## Estrutura

- `main.py`: CLI do MVP
- `docs/training-roadmap.md`: plano de evolucao do cerebro arquitetonico
- `docs/dataset-schema.json`: schema base para treinamento
- `datasets/cases/`: exemplos estruturados para formar o dataset
- `autocad_ia/models.py`: modelos de dados do projeto
- `autocad_ia/design_brain.py`: camada semantica de estrategia, zonas e adjacencias
- `autocad_ia/text_parser.py`: parser simples de descricao em texto
- `autocad_ia/layout_engine.py`: motor parametricamente simples para organizar a planta
- `autocad_ia/dxf_writer.py`: exportador DXF sem dependencias externas
- `autocad_ia/service.py`: orquestracao do fluxo texto/json -> layout -> DXF
- `samples/simple_house.json`: exemplo de entrada estruturada
- `output/`: pasta sugerida para DXFs gerados

## Limites atuais

Esta beta ainda nao faz:

- calculo arquitetonico real
- regras completas de circulacao
- portas e janelas inteligentes
- multiplos pavimentos completos
- integracao direta com AutoCAD API
- leitura de normas locais

## Como testar

### Preview no navegador

Abra [`preview.html`](C:/Users/vitin/Desktop/cotai/cotaiedit/AUTOCAD%20IA/preview.html) no navegador.

Nele voce pode:

- colar um JSON estruturado
- escrever o projeto em texto livre
- visualizar a planta 2D em SVG sem precisar do AutoCAD
- alternar grade e labels
- usar zoom
- baixar o JSON renderizado da composicao atual

### 1. Gerar a partir de um JSON estruturado

```powershell
python "AUTOCAD IA/main.py" from-json "AUTOCAD IA/samples/simple_house.json" "AUTOCAD IA/output/simple_house.dxf"
```

### 2. Gerar a partir de texto

```powershell
python "AUTOCAD IA/main.py" from-text "casa terrea 12x8 com sala 4x5, cozinha 3x3, quarto 3x3, banheiro 2x2" "AUTOCAD IA/output/casa_texto.dxf"
```

### 3. Analisar o projeto estruturado

```powershell
python "AUTOCAD IA/main.py" analyze-text "Quero uma mansao de 2 andares em um terreno de 20x30 com garagem para 4 carros, sala de estar, sala de jantar, cozinha gourmet, area de servico, lavabo, escritorio, varanda gourmet, piscina. No pavimento superior quero 1 suite master, 2 suites, 2 quartos, 3 banheiros, closet e sala intima."
```

### 4. Exportar JSON para o Cotai Arquiteto

```powershell
python "AUTOCAD IA/main.py" export-plan-json "Quero uma mansao de 2 andares em um terreno de 20x30 com garagem para 4 carros, sala de estar, sala de jantar, cozinha gourmet, area de servico, lavabo, escritorio, varanda gourmet, piscina. No pavimento superior quero 1 suite master, 2 suites, 2 quartos, 3 banheiros, closet e sala intima." "AUTOCAD IA/output/mansao_importavel.json"
```

Depois:

1. abra [`preview.html`](C:/Users/vitin/Desktop/cotai/cotaiedit/AUTOCAD%20IA/preview.html)
2. clique em `Importar JSON IA`
3. selecione o arquivo exportado
4. o estudo entra como um projeto pronto dentro do `Cotai Arquiteto`

## Proxima evolucao natural

Depois desta beta, os proximos passos mais fortes sao:

1. usar o schema oficial do dataset para treinar interpretacao do briefing
2. enriquecer o layout com wet stack, corredores e massa mais realista
3. fazer o preview do Cotai Arquiteto consumir o pipeline real
4. gerar camadas DXF mais organizadas
5. integrar com uma API/plugin do AutoCAD
