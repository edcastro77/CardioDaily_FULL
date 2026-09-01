---
name: varredura
description: Executa o procedimento da LEI 9 antes de mudar uma REGRA DE NEGÓCIO - lista os blocos onde a regra pode morar, varre TODOS (grep/leitura), mostra o resultado bloco a bloco (inclusive os que estão certos), e só então autoriza editar. Use sempre que a mudança for regra (limiar, teto, rótulo, porta, vocabulário), não conserto local. Args - descreva a regra que vai mudar.
---

# /varredura — a LEI 9 como procedimento executável

**A regra da lei:** uma regra de negócio quase nunca vive num arquivo só. Consertar
onde se achou e seguir é o mesmo que não consertar — o bloco que sobrou roda em
silêncio. Foi assim que a D-01 (revisão sistemática É meta) foi "consertada" no
prompt em 31/Jul e continuou errada no mapa do PubMed até estragar 112 artigos.

## O procedimento (nesta ordem, sem pular)

**1. Enuncie a regra** em uma frase, com a decisão do dono que a originou (data).

**2. Escreva a lista dos blocos onde ela PODE morar** — começando pelos 10 da casa:

| # | bloco | onde |
|---|---|---|
| 1 | Classificador — cascata | `src/classificador_ouro.py` (cada camada decide sozinha; as de cima calam as de baixo) |
| 2 | Classificador — mapa PubMed | `src/classificador_pubmed.py` · `_PUBTYPE_PRIORITY` |
| 3 | Classificador — prompt | `src/classificador_prompt.py` |
| 4 | Extração | `src/analise_prompt.md` · `analise_diretriz_prompt.md` · `analise_revisao_prompt.md` + SCHEMAS em `src/analise.py` |
| 5 | Motor de notas | `src/notas_prototipo.py` (4 motores: ORIGINAL · META · DIRETRIZ · REVISAO) |
| 6 | Escolha do prompt/tipo | `src/analisador.py` (`tipo_do_documento`, `escolher_prompt`, cache de fatos) |
| 7 | Redator e derivados | `src/redator_*_prompt.md` (4) · `acri_prompt.md` · `script_audio_prompt.md` · `gancho_abertura_prompt.md` |
| 8 | Portão do Supabase | `src/contrato.py` · `publicador.py` · `ficha_site.py` |
| 9 | Prova | `src/teste_motor.py` · `prova_classificador.py` · `placar.py` · `teste_administrador.py` |
| 10 | Documentação | `CLAUDE.md` · `docs/CADERNO_EXECUCAO.md` |

E acrescente os que o caso pedir (ex.: tela da Chave 3 = `administrador.py`;
Visual Abstract = `infographics/`; hooks = `.claude/hooks/`; CI = `.github/workflows/`).

**3. Varra DE VERDADE** — grep + leitura do trecho, bloco a bloco. Grep sozinho
não basta quando a regra pode estar parafraseada (prompt em linguagem natural):
nesses blocos, LEIA a seção.

**4. Mostre a tabela da varredura ANTES de editar** — uma linha por bloco,
inclusive os limpos: `bloco 7: não tem essa regra, ok`. **O que não aparece na
tabela não foi olhado.** Regra achada em N blocos = consertar nos N.

**5. Trava**: onde a regra puder virar função pura, escreva a trava no
`teste_motor.py` — e prove que ela REPROVARIA o estado antigo (rode a lógica
contra `git show HEAD:` do arquivo, como a trava da paginação fez em 01/Set).

**6. `/prova` no fim.** E se a regra muda NOTA: medir o impacto no acervo
inteiro antes de valer (motor de ontem × de hoje, mesmo `fatos`), mostrar os
números, e quem decide se vale é o dono.

## Proibições que a lei registra

- Enunciar o risco NÃO é tratá-lo: se você sabe nomear o que não foi medido, PARA.
- "Pode soltar" com varredura pela metade foi exatamente o caso de 02/Ago.
- Medir só o LLM quando a cascata decide antes dele é medir a coisa errada.
