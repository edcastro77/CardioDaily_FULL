# -*- coding: utf-8 -*-
"""
Portão de validação único para escritas na tabela artigos do Supabase.

Uso:
    from src.article_validator import validate_artigo_payload, registrar_rejeicao_supabase

    payload_limpo, warnings, is_valid = validate_artigo_payload(payload, analysis_json, article_type)
    for w in warnings:
        logger.warning(w)
    if not is_valid:
        erros = [w for w in warnings if w.startswith("[ERRO]")]
        registrar_rejeicao_supabase(payload_limpo, erros)
        return  # NÃO grava em artigos

Garante:
  - LEI 0 aplicada em nota_aplicabilidade (quando analysis_json fornecido)
  - tipo_estudo normalizado para enum canônico
  - doenca_principal validada contra taxonomia oficial
  - keywords sempre lista
  - título sinalizado se parece nome de arquivo
  - tipos numéricos corretos para notas

Campos críticos (ausente OU inválido → is_valid=False, artigo barrado):
  titulo, nota_aplicabilidade, nota_trabalho_estatistico,
  mcid_avaliacao (>= 10 chars), resumo_markdown (>= 1000 chars)
"""
from __future__ import annotations

import os
import re
from typing import Any

try:
    from src.taxonomy import validate_category
except ImportError:
    from taxonomy import validate_category  # type: ignore  # quando sys.path aponta para src/

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TIPO_ESTUDO_VALIDOS = frozenset({"original", "metanalise", "revisao", "guideline"})

# Mapeamento de variantes brutas (LLM) → enum canônico
_TIPO_NORMALIZACAO: dict[str, str] = {
    "original":                            "original",
    "artigo_original":                     "original",
    "caso_clinico":                        "original",   # relato de caso = original
    "revisao":                             "revisao",
    "revisao_geral":                       "revisao",
    "ponto_de_vista":                      "revisao",
    "editorial":                           "revisao",
    "revisao_sistematica":                 "metanalise",
    "revisao_sistematica_meta_analise":    "metanalise",
    "metanalise":                          "metanalise",
    "meta-analise":                        "metanalise",
    "meta_analise":                        "metanalise",
    "guideline":                           "guideline",
    "diretriz":                            "guideline",
    "guidelines":                          "guideline",
}

# Padrões de título que indicam nome de arquivo
_RE_FILENAME_DATE   = re.compile(r'^\d{4}[-_]\d{2}')          # YYYY-MM ou YYYY_MM
_RE_DOC_ID          = re.compile(r'^(doi|pdf)_[a-f0-9]+', re.IGNORECASE)
_RE_UNDERSCORE      = re.compile(r'_')                         # qualquer _ em título
_MCID_MIN_PIPES     = 3                                        # formato "A | B | C | D"
_RESUMO_MIN_CHARS   = 1000                                     # bloqueante
_TITULO_MIN_WORDS   = 5
_MCID_KEYWORD       = re.compile(r'\bMCID\b', re.IGNORECASE)
_MCID_BLOCK_CHARS   = 10                                       # abaixo disso → ERRO grave


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _titulo_parece_filename(titulo: str) -> bool:
    if not titulo:
        return False
    if _RE_FILENAME_DATE.match(titulo):
        return True
    if _RE_DOC_ID.match(titulo):
        return True
    if _RE_UNDERSCORE.search(titulo):
        return True
    # Padrão classificador YYYY-MM-Journal-Words (3+ segmentos separados por -)
    partes = titulo.split("-")
    if len(partes) >= 3 and partes[0].strip().isdigit() and len(partes[0].strip()) == 4:
        return True
    return False


def _aplicar_lei_0(nota: float, analysis_json: dict, article_type: str) -> float:
    """Importação lazy — evita depender do módulo pesado article_analyzer no topo."""
    try:
        try:
            from src.article_analyzer import aplicar_teto_nac  # type: ignore
        except ImportError:
            from article_analyzer import aplicar_teto_nac  # type: ignore
        return aplicar_teto_nac(nota, analysis_json, article_type)
    except Exception:
        return nota


# ---------------------------------------------------------------------------
# Gravação de rejeição
# ---------------------------------------------------------------------------

def registrar_rejeicao_supabase(payload: dict[str, Any], motivos: list[str]) -> bool:
    """Grava artigo barrado em artigos_rejeitados. Silent failure — nunca derruba o pipeline."""
    try:
        import requests as _req
        sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        sb_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
        if not sb_url or not sb_key:
            return False

        _EXCLUIR = {"embedding", "id"}
        data = {k: v for k, v in payload.items() if k not in _EXCLUIR}
        data["motivo_rejeicao"] = "; ".join(motivos)

        h = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        r = _req.post(
            f"{sb_url}/rest/v1/artigos_rejeitados",
            headers=h, json=data, timeout=15,
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def validate_artigo_payload(
    payload: dict[str, Any],
    analysis_json: dict | None = None,
    article_type: str = "",
) -> tuple[dict[str, Any], list[str], bool]:
    """
    Valida e limpa o payload antes de escrever na tabela artigos.

    Args:
        payload:       Dict a enviar ao Supabase (copiado internamente — original não modificado).
        analysis_json: JSON completo da análise LLM (necessário para aplicar LEI 0).
        article_type:  Tipo do artigo. Usado pela LEI 0 quando analysis_json fornecido.

    Returns:
        (payload_limpo, warnings, is_valid)
        - payload_limpo: cópia com correções automáticas aplicadas.
        - warnings:  todos os avisos; prefixo "[ERRO]" = campo crítico inválido/ausente.
        - is_valid:  False se qualquer campo crítico estiver ausente ou inválido.
                     Quando False, o caller NÃO deve gravar em artigos e deve
                     chamar registrar_rejeicao_supabase() com os [ERRO]s.
    """
    p = dict(payload)
    warnings: list[str] = []
    erros_graves: list[str] = []
    doc_id = p.get("doc_id", "<sem-doc_id>")

    def _erro(msg: str) -> None:
        erros_graves.append(msg)
        warnings.append(msg)

    # ------------------------------------------------------------------ titulo
    titulo = p.get("titulo") or ""
    titulo = titulo.strip()
    if not titulo:
        _erro(f"[ERRO][{doc_id}] titulo está vazio ou ausente")
    else:
        if _titulo_parece_filename(titulo):
            _erro(f"[ERRO][{doc_id}] titulo parece nome de arquivo: '{titulo[:70]}'")
        word_count = len(titulo.split())
        if word_count < _TITULO_MIN_WORDS:
            warnings.append(
                f"[AVISO][{doc_id}] titulo tem só {word_count} palavra(s): '{titulo[:70]}'"
            )
        p["titulo"] = titulo

    # --------------------------------------------------------------- tipo_estudo
    tipo_raw = p.get("tipo_estudo")
    if tipo_raw is not None:
        tipo_lower = str(tipo_raw).lower().strip()
        tipo_canonical = _TIPO_NORMALIZACAO.get(tipo_lower)
        if tipo_canonical:
            if tipo_canonical != tipo_raw:
                warnings.append(
                    f"[INFO][{doc_id}] tipo_estudo normalizado: '{tipo_raw}' → '{tipo_canonical}'"
                )
            p["tipo_estudo"] = tipo_canonical
        elif tipo_lower not in TIPO_ESTUDO_VALIDOS:
            warnings.append(
                f"[AVISO][{doc_id}] tipo_estudo desconhecido: '{tipo_raw}' — mantido sem normalização"
            )

    # -------------------------------------------- nota_aplicabilidade + LEI 0
    nota_raw = p.get("nota_aplicabilidade")
    if "nota_aplicabilidade" not in p or nota_raw is None:
        _erro(f"[ERRO][{doc_id}] nota_aplicabilidade ausente ou None — campo obrigatório")
    else:
        nota_float: float | None = None
        try:
            nota_float = float(nota_raw)
        except (TypeError, ValueError):
            _erro(f"[ERRO][{doc_id}] nota_aplicabilidade não numérico: '{nota_raw}'")
            p["nota_aplicabilidade"] = None

        if nota_float is not None:
            if not (0.0 <= nota_float <= 10.0):
                _erro(f"[ERRO][{doc_id}] nota_aplicabilidade fora de [0-10]: {nota_float}")

            if analysis_json is not None:
                _tipo_lei0 = article_type or str(p.get("tipo_estudo", ""))
                nota_apos = _aplicar_lei_0(nota_float, analysis_json, _tipo_lei0)
                if nota_apos != nota_float:
                    warnings.append(
                        f"[LEI0][{doc_id}] nota_aplicabilidade {nota_float:.0f} → {nota_apos:.0f}"
                        f" (teto LEI 0 aplicado)"
                    )
                nota_float = nota_apos

            p["nota_aplicabilidade"] = int(nota_float)

    # ------------------------------------------------------- nota_trabalho_estatistico
    nota_est_raw = p.get("nota_trabalho_estatistico")
    if "nota_trabalho_estatistico" not in p or nota_est_raw is None:
        _erro(f"[ERRO][{doc_id}] nota_trabalho_estatistico ausente ou None — campo obrigatório")
    else:
        nota_est: int | None = None
        try:
            nota_est = int(float(nota_est_raw))
        except (TypeError, ValueError):
            _erro(f"[ERRO][{doc_id}] nota_trabalho_estatistico não numérico: '{nota_est_raw}'")
            p["nota_trabalho_estatistico"] = None

        if nota_est is not None:
            if not (0 <= nota_est <= 10):
                _erro(f"[ERRO][{doc_id}] nota_trabalho_estatistico fora de [0-10]: {nota_est}")
            p["nota_trabalho_estatistico"] = nota_est

    # ---------------------------------------------------------- doenca_principal
    doenca = p.get("doenca_principal")
    if doenca is not None:
        doenca_valid = validate_category(str(doenca))
        if doenca_valid != doenca:
            warnings.append(
                f"[INFO][{doc_id}] doenca_principal normalizada: '{doenca}' → '{doenca_valid}'"
            )
        p["doenca_principal"] = doenca_valid

    # ----------------------------------------------------------------- keywords
    kw = p.get("keywords")
    if kw is not None:
        if isinstance(kw, str):
            kw_list = [k.strip() for k in kw.split(",") if k.strip()]
            warnings.append(
                f"[INFO][{doc_id}] keywords era string, convertida para lista ({len(kw_list)} itens)"
            )
            p["keywords"] = kw_list
        elif isinstance(kw, list):
            kw_clean = [str(k).strip() for k in kw if k and str(k).strip()]
            if not kw_clean:
                warnings.append(f"[AVISO][{doc_id}] keywords lista vazia após limpeza")
            p["keywords"] = kw_clean
        else:
            warnings.append(
                f"[ERRO][{doc_id}] keywords tipo inesperado ({type(kw).__name__}) → []"
            )
            p["keywords"] = []

    # -------------------------------------------------------------- resumo_markdown
    resumo = p.get("resumo_markdown")
    if "resumo_markdown" not in p or resumo is None:
        _erro(f"[ERRO][{doc_id}] resumo_markdown ausente — campo obrigatório")
    else:
        resumo = str(resumo).strip()
        if len(resumo) < _RESUMO_MIN_CHARS:
            _erro(
                f"[ERRO][{doc_id}] resumo_markdown muito curto: {len(resumo)} chars"
                f" (mínimo {_RESUMO_MIN_CHARS})"
            )
        p["resumo_markdown"] = resumo

    # -------------------------------------------------------------- mcid_avaliacao
    mcid = p.get("mcid_avaliacao")
    if "mcid_avaliacao" not in p or mcid is None:
        _erro(f"[ERRO][{doc_id}] mcid_avaliacao ausente — campo obrigatório")
    else:
        mcid = str(mcid).strip()
        if len(mcid) < _MCID_BLOCK_CHARS:
            _erro(
                f"[ERRO][{doc_id}] mcid_avaliacao muito curto ({len(mcid)} chars)"
                f" — mínimo {_MCID_BLOCK_CHARS}"
            )
        else:
            pipe_count = mcid.count("|")
            if pipe_count < _MCID_MIN_PIPES:
                warnings.append(
                    f"[AVISO][{doc_id}] mcid_avaliacao não segue formato padrão"
                    f" (esperado 4 seções com '|', encontrado {pipe_count + 1}): '{mcid[:60]}'"
                )
            if not _MCID_KEYWORD.search(mcid):
                warnings.append(
                    f"[AVISO][{doc_id}] mcid_avaliacao não contém 'MCID': '{mcid[:60]}'"
                )
        p["mcid_avaliacao"] = mcid

    is_valid = len(erros_graves) == 0
    return p, warnings, is_valid
