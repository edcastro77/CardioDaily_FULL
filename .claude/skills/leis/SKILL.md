---
name: leis
description: Resumo operativo das LEIS do CardioDaily com o estado das revogações. Consulte ANTES de mexer em régua, nota, classificador, portão ou qualquer regra de negócio. A FONTE é o CLAUDE.md da raiz — se este resumo divergir dele, vale a raiz e este arquivo deve ser corrigido.
---

# /leis — o resumo operativo (a fonte é o CLAUDE.md da raiz)

⚠️ Este arquivo é RESUMO, não fonte. Divergiu do CLAUDE.md da raiz? Vale a raiz,
e corrija aqui na hora (LEI 9: duas fontes de verdade é a definição de buraco).

## As leis, em uma linha cada

| Lei | A regra |
|---|---|
| **0** | A nota é DETERMINÍSTICA (`notas_prototipo.py`): `min(teto_desenho, teto_externa, nota_estatística)`. Teto por desenho A=10 B=8 C=7 D=6 E=5; rigor <8 → NAC ≤7. O LLM extrai FATOS, não dá nota. |
| **1** | NUNCA propor abandonar parte do projeto. Sem alternativa não existe "desistir". |
| **2** | Diante de dificuldade: objetivo → causa real → 2-3 alternativas (CONFIABILIDADE > CUSTO > VELOCIDADE) → recomendar → registrar no CADERNO com data/hora. |
| **3** | O Dr. Eduardo define o produto. Discordou tecnicamente? Apresenta a ressalva E executa. |
| **4** | UMA pasta: `CardioDaily_FULL`. Isolamento é por branch ou pasta de saída, NUNCA por cópia do projeto. Aprovado = commitado no main. |
| **5** | SÓ `publicador.py` escreve na tabela `artigos` (via contrato+preflight). Qualquer outro escritor é buraco — recusar. Vale para o Claude também (hook `guarda_lei5`). |
| **6** | O QUE entra é decisão do dono; COMO implementar é do Claude. Escolha de produto embutida em código sem listar antes = decisão ROUBADA. Buraco zero = toda coluna editorial preenchida, e quem define quais são é ele. |
| **7** | Vocabulário de certeza: **Escrevi** (existe no arquivo) · **Compila** · **Testei aqui** (dado de mentira) · **Rodou na sua máquina** · **RESOLVIDO** (só com ele rodando, dado real, evidência visível). Nunca uma palavra acima da verdade. "Não sei" é resposta válida. |
| **8** | O classificador É a decisão: caixa errada → prompt, motor, notas, perícia — tudo errado e internamente coerente. Na dúvida, REVISAO_HUMANA. A cascata (revista → topo → descarte → título → PubMed → rótulo → LLM) decide de cima para baixo. |
| **9** | Uma regra mora em VÁRIOS blocos. Antes de mudar: listar os blocos, varrer TODOS, consertar em todos, MOSTRAR a varredura bloco a bloco (inclusive "não tem, ok"). Use a skill `/varredura`. |
| **10** | O CardioDaily PUBLICA MENOS E REPROVA MAIS — o produto é o filtro. Porta de publicação: nota ≥6 (perícia/ACRI ≥6 · visual ≥7 · áudio ≥8). Régua "severa demais"? Mostra os números; quem decide é o dono. |
| **11** | O vazio tem NOME (selos `nao_gerado:` · `nao_se_aplica:` · `ausente:`) e quem lê o campo tem que saber ler o nome — selo lido como valor é tão ruim quanto NULL. |
| **12** | Nada destrutivo sem conferir: origem 0 bytes não é dado; destino existente se olha antes; trabalho MANUAL dele (gabarito, curadoria) o Claude SÓ LÊ; `saidas/`, `outputs/`, `ARTIGOS/` não têm git. Hook `guarda_lei12` cobra. |

## Bicondicional e vocabulários do `muda_conduta` (04–06/Ago)

- **RCT e meta**: nota 9/10 ⟺ muda conduta. UM cálculo, nunca dois caminhos.
- **Revisão**: campo = `N/A (revisão organiza conhecimento…)`. Nota pode chegar a 10 = "organiza excepcionalmente bem".
- **Diretriz**: campo = RECOMENDACAO_DIRETRIZ (≥8 RECOMENDADA · 6–7 COM RESSALVAS · 4–5 REFERÊNCIA, NÃO AUTORIDADE · ≤3 NÃO RECOMENDADA). **A recomendação AVISA, não RETÉM.**

## Exceções e revogações VIGENTES (a parte que mais engana)

1. **Diretriz NÃO tem porta** (05/Ago): sobe em qualquer nota, com tudo (perícia, visual, áudio com roteiro próprio que DIZ a nota em voz alta). A exceção é SÓ da diretriz.
2. **REVOGADO em 22/Ago**: *"abaixo de 9 o desconto de indústria vale inteiro"*. Regra atual: o desconto de independência **não rebaixa quem tem rigor ≥9** — vira ressalva declarada em qualquer altura da escala. Rigor <9 leva o desconto inteiro. (Caso EXCEL; medido: 22 artigos 7→8, nenhum desce.)
3. **Teto 8 do open-label FICA** (22/Ago): gabarito dele de 11/Ago — EXCEL 8, NOBLE 7, ISAR-REACT 5 = 7. Não é castigo por não cegar; é quanta certeza o desenho entrega.
4. **Meta-análises — LEI 10**: misturar ECR+observacional no primário = FATAL teto 5 · perder significância no Trim-and-Fill = FATAL teto 5 · I²>50% sem exploração = teto 6 · desfecho substituto = teto 8. Crivos de aplicabilidade: 4/4→9-10 · 3/4→8 · 2/4→6 · 1/4→5 · 0/4→4 (não existe 7, de propósito).
5. **ARR**: dois campos — `arr_pct` (cumulativa, o motor divide por `seguimento_anos`) vs `arr_ano_pct` (pessoas-ano, NÃO divide).
6. **Palavras-chave em PORTUGUÊS** (8–12 termos, doença·droga·população·desfecho).

## Antes de mudar qualquer regra acima

1. `/varredura` (LEI 9) — lista e varre os blocos.
2. A decisão é do dono? Liste as escolhas ANTES de codar (LEI 6).
3. Trava nova no `teste_motor.py` + prove que ela REPROVARIA o estado antigo.
4. `/prova` antes e depois. Medir o impacto no acervo antes de valer (como em 22/Ago: 1011 artigos, motor de ontem × de hoje).
