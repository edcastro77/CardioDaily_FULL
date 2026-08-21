"""
gerar_freq_mesh.py — a tabela de frequência dos descritores MeSH no acervo.

É o peso IDF do desempate do `tema_mesh.decidir`: descritor RARO vale mais que descritor
comum. "Humans" aparece em quase tudo e não separa nada; "Amyloidosis" separa.

Até 20/Ago essa contagem era feita dentro do `marcar_temas.py`, que via o acervo inteiro de
uma vez. O portão vê UM artigo por vez e não tem como contar — por isso a tabela vira arquivo.

Rode de novo de tempos em tempos (a cada revisão, por exemplo aos 800 artigos).
Uso:  python3 scripts/gerar_freq_mesh.py
"""
import collections, json, os, sys, urllib.parse, urllib.request
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, ".env"))

url = os.getenv("SUPABASE_URL"); key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
h = {"apikey": key, "Authorization": f"Bearer {key}"}
q = urllib.parse.urlencode({"select": "mesh_terms", "limit": "5000"})
dados = json.load(urllib.request.urlopen(
    urllib.request.Request(f"{url}/rest/v1/artigos?{q}", headers=h), timeout=60))
freq = collections.Counter(t for d in dados for t in (d.get("mesh_terms") or []))
destino = os.path.join(RAIZ, "src", "dados", "mesh_freq.json")
json.dump(dict(freq), open(destino, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"✔ {destino}")
print(f"  {len(dados)} artigos · {len(freq)} descritores distintos")
for t, n in freq.most_common(6):
    print(f"    {n:>4}  {t}")
