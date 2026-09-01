---
name: prova
description: Roda a PROVA da casa — as 90+ travas do teste_motor.py + py_compile de todo src/ — e reporta APROVADO/REPROVADO com as falhas na íntegra. É o portão da Chave 8 sem o merge. Use antes de qualquer commit, depois de mexer em motor/prompt/portão/classificador, ou quando o Dr. Eduardo pedir "roda a prova".
---

# /prova — o portão da Chave 8, sem o merge

Execute na raiz do projeto (`CardioDaily_FULL`), nesta ordem, com o venv do projeto:

```bash
.venv/bin/python -m py_compile src/*.py
.venv/bin/python -u src/teste_motor.py
```

A bateria roda em ~7 s. O runner do `teste_motor.py` VARRE o módulo e recolhe toda
função `teste_*` (hoje ~90) — a lista fixa só ordena o relatório. Não existe
"rodar um subconjunto": prova parcial é aprovado por ausência, o pior defeito da casa.

## Como reportar o resultado

- **APROVADO** só existe com exit 0 **e** a palavra `APROVADO` na última linha.
  Qualquer outra combinação é REPROVADO.
- **REPROVADO**: mostre as travas que falharam (linhas `❌`) e o traceback na
  íntegra. É proibido resumir para "quase passou" ou "falhou só uma" — falha é falha
  (LEI 7). Não conserte nada por conta própria a partir do resultado: reporte primeiro.
- Use o vocabulário da LEI 7: a prova rodada nesta sessão, nesta máquina, com a
  saída visível, pode ser reportada como "rodou na sua máquina".

## Avisos que evitam diagnóstico errado

- A bateria é **100% offline desde 01/Set** (provado: ambiente vazio, sem `.env`,
  91 travas APROVADO): o `administrador` ganhou `main()` e importá-lo não abre a
  UI nem toca a rede. Se a bateria voltar a exigir rede/credencial, isso é
  REGRESSÃO — investigue qual import voltou a executar coisa no nível do módulo.
- Os avisos `missing ScriptRunContext` do Streamlit são ruído esperado do modo
  bare — podem ser ignorados.
- A mesma prova roda na nuvem a cada push (`.github/workflows/prova.yml`).
  Vermelho lá e verde aqui (ou vice-versa) é sinal de duas verdades — investigue,
  não escolha o resultado que agrada (LEI 9).
- A TELA do administrador tem suíte própria (AppTest, sem navegador):
  `.venv/bin/python -u src/teste_administrador.py` — Chave 26, e também no CI.
  Se a mudança tocou o `administrador.py`, rode as DUAS provas.
