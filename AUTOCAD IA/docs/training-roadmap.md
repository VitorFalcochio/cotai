# Cotai Arquiteto - Roadmap de Treinamento

## Objetivo

Elevar a `AUTOCAD IA` de um gerador beta de layout para um sistema de arquitetura assistida por IA capaz de:

- interpretar briefs reais de clientes
- estruturar programa arquitetonico
- gerar setorizacao coerente
- desenhar plantas mais proximas de um projeto real
- explicar as decisoes da planta
- preparar exportacao tecnica para CAD

## Principio central

Nao vamos depender de um unico modelo "magico". O sistema deve funcionar em camadas:

1. Interpretacao do pedido
2. Estruturacao em schema arquitetonico
3. Planejamento espacial
4. Avaliacao tecnica
5. Geracao geometrica
6. Exportacao tecnica

## Arquitetura de treino recomendada

### Camada 1 - IA de Interpretacao

Entrada:

- texto livre do cliente
- preferencias
- estilo
- dimensoes do lote
- numero de pavimentos
- necessidades especiais

Saida:

- JSON arquitetonico estruturado

Objetivo:

- transformar linguagem natural em dados consistentes
- extrair prioridades e restricoes
- entender tipologia do projeto

### Camada 2 - IA/Classificador de Programa

Entrada:

- schema arquitetonico da Camada 1

Saida:

- setorizacao sugerida
- relacoes de adjacencia
- prioridades espaciais

Objetivo:

- definir o que deve ficar junto
- definir o que deve ficar separado
- organizar o programa por zonas

### Camada 3 - Motor Parametrico

Entrada:

- projeto estruturado
- regras de adjacencia
- restricoes geometricas

Saida:

- planta renderizavel
- ambiente por ambiente com coordenadas
- massa externa
- circulacao

Objetivo:

- traduzir o programa em geometria
- respeitar largura do lote, pavimentos, eixos e nucleo molhado

### Camada 4 - IA Avaliadora

Entrada:

- schema do projeto
- layout gerado

Saida:

- score de qualidade
- conflitos espaciais
- sugestoes de refinamento

Objetivo:

- agir como arquiteto revisor
- rejeitar plantas fracas
- propor melhorias

## Dataset ideal

Cada item do dataset deve ter:

1. `brief`
2. `project_schema`
3. `layout_solution`
4. `technical_review`
5. `quality_score`

### Exemplo de fontes de dados

- projetos autorais do escritorio
- plantas aprovadas reais
- estudos preliminares
- memoriais descritivos
- tabelas de programa
- revisoes feitas por arquiteto/engenheiro

## Formato recomendado do dataset

### 1. Brief

Contem:

- tipo de projeto
- lote
- area alvo
- pavimentos
- estilo
- requisitos
- preferencias
- restricoes

### 2. Schema arquitetonico

Contem:

- lista de ambientes
- categoria
- role
- cluster
- zona
- adjacencias
- pavimento
- prioridade

### 3. Solucao de layout

Contem:

- massa do projeto
- rooms posicionados
- halls
- escada
- wet core
- lazer
- acessos

### 4. Revisao tecnica

Contem:

- pontos fortes
- falhas
- conflitos
- recomendacoes

## Fases de treinamento

### Fase 1 - Normalizacao dos dados

Meta:

- transformar plantas e memoriais em JSON padrao

Entregas:

- schema oficial
- scripts de conversao
- primeiros 20 a 50 casos etiquetados

### Fase 2 - Treino de interpretacao

Meta:

- sair do texto do cliente para JSON arquitetonico confiavel

Medida de sucesso:

- campos corretos
- ambientes corretos
- prioridades coerentes

### Fase 3 - Treino de adjacencia e setorizacao

Meta:

- ensinar o sistema a organizar programas como arquiteto experiente

Medida de sucesso:

- cozinha perto de jantar/servico
- suites agrupadas corretamente
- wet stack racional
- lazer conectado ao social

### Fase 4 - Treino de avaliacao

Meta:

- fazer a IA dizer se a planta esta boa ou ruim

Medida de sucesso:

- identificar circulacao ruim
- identificar corredor excessivo
- identificar banheiro mal posicionado
- sugerir correcoes uteis

### Fase 5 - Refino geometricamente orientado

Meta:

- usar o feedback da IA avaliadora para ajustar o motor parametrico

Medida de sucesso:

- plantas mais proximas de casos reais
- menos geometria "em grade"
- melhor relacao entre massa, acessos e nucleo

## Como coletar treinamento com qualidade

### Regras

- so usar projetos com documentacao minimamente consistente
- manter unidade unica em metros
- padronizar nomes de ambientes
- separar claramente terreo, superior, lazer e servico
- registrar comentarios do profissional que revisou

### Campos minimos para cada exemplo

- `source_id`
- `source_type`
- `author_role`
- `lot`
- `floors`
- `style`
- `brief`
- `rooms`
- `adjacency`
- `review_notes`
- `approved`

## Avaliacao de qualidade

Sugestao de score:

- `layout_score` de 0 a 10
- `circulation_score` de 0 a 10
- `privacy_score` de 0 a 10
- `constructability_score` de 0 a 10
- `wet_stack_score` de 0 a 10
- `overall_score` de 0 a 10

## Proximo passo pratico dentro do repositorio

1. criar o schema oficial de treino
2. criar pasta `datasets/cases`
3. montar 5 exemplos completos muito bem etiquetados
4. adaptar a pipeline atual para ler esse schema
5. depois treinar a camada de interpretacao

## Visao final

Quando esse roadmap estiver maduro, o `Cotai Arquiteto` vai operar assim:

1. cliente descreve a casa
2. IA interpreta e monta o schema
3. planner espacial organiza zonas e adjacencias
4. motor parametrico desenha
5. IA avaliadora revisa
6. sistema corrige
7. preview mostra opcoes melhores
8. DXF sai muito mais proximo de um estudo arquitetonico real
