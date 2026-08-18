# TROCA DA CHAVE DO SUPABASE — passo a passo

**Por quê:** a `SUPABASE_SERVICE_ROLE_KEY` está em texto puro em
`outputs/site_operacional/pasted_content_2.txt` — o briefing que foi colado num chat externo
(Manus) em julho. Essa chave **ignora todas as permissões**: lê, escreve e apaga o banco
inteiro. Conferido: o arquivo **nunca foi commitado**, então não vazou para o GitHub.

**⚠️ NÃO clique em "rotacionar".** A `service_role` e a `anon` são as duas assinadas pelo
mesmo JWT secret. A documentação da Supabase:

> *"anon and service_role must be rotated simultaneously"*
> *"Currently active users get immediately signed out"*
> *"it is no longer possible to rotate the legacy anon, service and JWT secrets"*

Rotacionar derrubaria o site junto. O caminho é **criar uma chave nova e aposentar a velha** —
as duas funcionam ao mesmo tempo, então não há interrupção.

---

## ⚠️ ANTES DE COMEÇAR: os nomes das suas variáveis não batem com o conteúdo

Decodifiquei o campo `role` de cada uma (isso não é segredo — é o que a chave *pode fazer*):

| variável no `.env` | o que o NOME sugere | o que ela REALMENTE é |
|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | serviço | ✅ `service_role` |
| `SUPABASE_SERVICE_KEY` | serviço | 🔴 **`anon`** — o nome engana |
| `SUPABASE_KEY` | genérica | ⚠️ `service_role` |

**Isto importa muito na troca.** Se você puser a `sb_secret_` nova em `SUPABASE_SERVICE_KEY`
achando que está trocando "a chave de serviço", vai estar dando poder de escrita a componentes
que hoje só leem — o oposto do que se quer numa faxina de segurança.

O `distribuidor.py` e os 4 workflows do GitHub usam `SUPABASE_SERVICE_KEY` — ou seja, hoje
rodam com privilégio **anon**. Funcionam porque a tabela `artigos` não tem Row Level Security
ligada. Não mexa nisso agora; só saiba que é assim, e faça a troca **variável por variável**,
não "todas de uma vez".

---

## PASSO 1 · Criar as chaves novas (2 min, não quebra nada)

1. Abra o painel: **https://supabase.com/dashboard/project/hzqtogcpwdzhjfroxtfz/settings/api-keys**
2. Aba **"Publishable and secret API keys"**
3. Se aparecer o botão **"Create new API keys"**, clique.

> *"Creating the new keys is safe. It adds a publishable key and a secret key alongside your
> existing anon and service_role keys. **Your legacy keys keep working.**"*

Você vai receber duas chaves:

| chave | onde entra |
|---|---|
| `sb_publishable_…` | site, navegador, qualquer coisa pública (você já tem uma) |
| `sb_secret_…` | **só backend** — Python, GitHub Actions, servidor |

**Copie a `sb_secret_…` num lugar seguro agora.** Ela aparece uma vez.

---

## PASSO 2 · Trocar no seu Mac (o `.env`)

Abra a **Chave 13** (`13_Abrir_o_env.command`) e troque:

```
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...(a nova)
SUPABASE_KEY=sb_secret_...(a mesma nova)
```

**Deixe `SUPABASE_SERVICE_KEY` como está por enquanto** — ela contém a `anon`, e trocá-la por
uma secret daria privilégio de escrita ao distribuidor. Se quiser arrumar o nome depois,
fazemos isso com calma, num passo separado.

**Confira antes de seguir:** clique a **Chave 23** (`23_Conferir_Chave_Supabase.command`).
Ela lê o `.env`, diz o tipo de cada chave e faz uma leitura real no banco. Você quer ver:

```
SUPABASE_SERVICE_ROLE_KEY   secret NOVA · sb_secret_…
✅ HTTP 200  SUPABASE_SERVICE_ROLE_KEY
✅ A chave de serviço JÁ É A NOVA
```

Se der 🔴, **pare** e me chame — não siga para o passo 3.

---

## PASSO 3 · Trocar no GitHub (os 4 robôs da nuvem)

Estes rodam sozinhos e usam os *secrets* do repositório, não o seu `.env`:

| workflow | o que faz |
|---|---|
| `radar.yml` | o Radar diário, 07:30 |
| `artigos-diarios.yml` | **o envio das 07:00** |
| `auditoria-semanal.yml` | auditoria |
| `lista-semanal.yml` | a lista |

1. Abra: **https://github.com/edcastro77/CardioDaily_FULL/settings/secrets/actions**
2. Clique em `SUPABASE_SERVICE_KEY` → **Update** → cole a `sb_secret_…`
3. Se existir `SUPABASE_SERVICE_ROLE_KEY` lá, atualize também

**Confira:** na aba **Actions**, dispare o `Artigos Diários` na mão ("Run workflow"). Se a
agenda de hoje estiver vazia ele vai dizer isso — e **isso já é sucesso**: significa que ele
conseguiu ler o banco com a chave nova.

---

## PASSO 4 · Trocar nos outros dois projetos

A mesma chave está sendo usada fora do CardioDaily:

- `~/projetos/PESQUISADOR/pesquisador_cardiodaily/pesquisador/.env`
- `~/projetos/POCUS_ASSISTENT/.env`

Abra cada um e troque pela `sb_secret_…`.

> A documentação recomenda o contrário disto, e vale anotar para depois:
> *"Prefer using a separate secret key for each separate backend component, so that if one
> leaks you will only need to change it and not all."*
> Ou seja: o ideal é **uma chave por projeto**. Hoje é uma para os três. Não precisa resolver
> agora, mas quando for mexer no PESQUISADOR, crie uma chave só dele.

---

## PASSO 5 · O site (Vercel)

Se o site usa a `service_role` em alguma rota de admin, troque também em
**Vercel → Project → Settings → Environment Variables**, e faça um **redeploy** (variável nova
só vale no próximo build).

Se o site só lê dados públicos, ele usa a `anon` — e a `anon` **não muda nada neste processo**.

---

## PASSO 6 · Desativar a chave velha

Só depois que os passos 2 a 5 estiverem conferidos.

1. Supabase → **Settings > API Keys**
2. Desative a **`service_role`** legada
3. **Deixe a `anon` legada LIGADA** — o site ainda depende dela

> *"You can re-activate them if you find a client you missed, so this step is reversible."*

⚠️ A documentação avisa que **não há indicador automático confiável** de uso — a conferência é
manual. Por isso os passos 2 a 5 vêm antes, e a Chave 23 existe.

**Depois de desativar, clique a Chave 23 de novo.** Tudo tem que continuar 200.

---

## PASSO 7 · Limpar as cópias antigas

Existem **6 arquivos `.env.*`** no projeto com a chave velha dentro (dois criados por mim
hoje). Depois da troca eles são inúteis e continuam sendo segredo espalhado pelo disco:

```bash
cd ~/projetos/CardioDaily_FULL
ls .env.*                      # confira a lista antes
rm .env.backup-* .env.antes-do-telefone-*
```

E o arquivo que originou tudo:

```bash
# tire a chave de dentro dele, ou apague o arquivo:
~/projetos/outputs/site_operacional/pasted_content_2.txt
```

---

## Resumo em uma tela

| # | onde | o que fazer |
|---|---|---|
| 1 | Supabase → Settings > API Keys | criar as chaves novas |
| 2 | `.env` (Chave 13) | `SUPABASE_SERVICE_ROLE_KEY` e `SUPABASE_KEY` → `sb_secret_…` |
| 3 | GitHub → Secrets | os 4 workflows |
| 4 | PESQUISADOR e POCUS | `.env` de cada um |
| 5 | Vercel | se o site usar service_role · **redeploy** |
| 6 | Supabase | desativar a `service_role` legada · **manter a `anon`** |
| 7 | disco | apagar os 6 `.env.*` e limpar o `pasted_content_2.txt` |

**Confira com a Chave 23 depois de cada passo.** Ela não muda nada — só olha e testa.

---

## O que eu já deixei pronto no código

- **`src/supabase_chaves.py`** — monta o cabeçalho certo conforme o TIPO da chave. Legada
  (JWT) manda `apikey` + `Authorization: Bearer`; nova (`sb_…`) manda **só o `apikey`**, como
  a documentação pede. Ligado no `administrador.py`, `lista_whatsapp.py` e no gerador do
  Visual Abstract.
- **Chave 23** — o conferidor.

⚠️ **Uma correção honesta:** eu avisei que o código quebraria com a chave nova, porque a
documentação diz *"You cannot send a publishable or secret key in the Authorization: Bearer
header"*. **Fui testar contra o seu projeto e os dois formatos devolveram HTTP 200.** O
gateway tolera hoje. Então o `supabase_chaves.py` não conserta uma quebra — ele tira a
dependência de um comportamento tolerado mas não documentado. Se a Supabase apertar a regra,
o CardioDaily não descobre no dia em que o painel parar de abrir.
