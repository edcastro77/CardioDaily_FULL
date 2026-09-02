# ESPECIFICAÇÃO DA BANCADA DE CURADORIA — decisões do dono
## v1.0 · 02/Set/2026 · consolidada das sessões de protótipo (artifact "Bancada de Curadoria")

> Protótipo navegável: https://claude.ai/code/artifact/95895f76-9d50-4840-9a08-55231fffe2ca
> (513 artigos reais embutidos; estático — não escreve no banco). Este documento é a lista
> de decisões JÁ BATIDAS para a construção da bancada real. LEI 6: o QUE é dele; o COMO é
> da implementação.

## Decisões aprovadas (com a data da conversa)

1. **Cada artigo é um prontuário** (01/Set): título original DESTACADO; embaixo, os tópicos
   — NAC (pílula colorida), Rigor, tipo, tema(s), muda_conduta; depois a linha de peças.
2. **O TÍTULO clica para a PERÍCIA CardioDaily** (02/Set) — a nossa análise é a peça
   central. Peças na linha: 📄 Perícia CardioDaily · 🎧 Áudio · 🖼️ Visual (link real quando
   existe; MOTIVO do selo quando não — LEI 11).
3. **Link "artigo na revista ↗" (DOI) fica, discreto, ao lado da revista** (02/Set).
   Razão de produto: *"será útil no programa onde não posso compartilhar o artigo
   original"* — o PDF da revista tem direito autoral; o DOI é o acesso legal.
4. **Farol de envio** no canto: 🟢 enviado (com data) · 🟡 na agenda · 🔴 não enviado.
5. **Filtro "Entrou na fila"** (Hoje / semana do congresso / 30d / Tudo) combinado com
   publicação recente — porque `data_publicacao` só tem precisão de MÊS (as revistas
   indexam assim; medido: 314 artigos "01/07"). Clássicos reanalisados ganham etiqueta
   **CLÁSSICO·ano** e saem das vistas de novidade SEM sumir em silêncio (placar diz).
6. **Placar "X de Y na tela · N escondidos por quê"** — nada some em silêncio (29/Ago).
7. **⭐ Hot topics**: marcar fixa o artigo no topo (congresso).
8. **💬 Contestar/discutir** por artigo: no produto real, conversa com os FATOS do pacote
   e registra a contestação para reanálise.
9. **Busca por palavras (E-lógico) em título+tema+keywords+MeSH** — "escore trombo cancer"
   tem que achar o Bleeding Risk Score sem adivinhar frase (02/Set).
10. **✅ Aprovar e agendar em cada card** (data + botão), gravando na `agenda_envio` como a
    Chave 3 faz (upsert idempotente; sucesso só com confirmação do banco).
11. **Acesso pelo celular** é requisito (01/Set: "fico dependente de abrir o computador").

## Ainda aberto (decidir na construção)

- Onde a bancada real roda: Streamlit local melhorado × app web hospedado (acesso remoto
  de verdade) — envolve autenticação e custo; decisão do dono.
- ACRI na tela (vive no disco; a bancada real precisa alcançá-lo).
- Áudio tocando embutido.
- O modo-conversa com o acervo ("o que tenho de amiloidose nota ≥8?").

## O que o protótipo NÃO faz (limite da tecnologia, não do desenho)

Página estática hospedada: não escreve no banco (agendar é demonstração), não toca áudio
embutido, dados congelados no momento da geração. Para agendar DE VERDADE: Chave 3.
