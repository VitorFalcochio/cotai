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
- `autocad_ia/models.py`: modelos de dados do projeto
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

## Proxima evolucao natural

Depois desta beta, os proximos passos mais fortes sao:

1. usar a Cota para preencher um schema arquitetonico melhor
2. enriquecer o layout com adjacencias, corredores e aberturas
3. gerar camadas DXF mais organizadas
4. integrar com uma API/plugin do AutoCAD
5. retornar preview visual dentro do Cotai antes da exportacao
