"""
voz_utils.py — lint anti-inglês pro roteiro FALADO (o TTS pronuncia termo em inglês → "mudança de idioma"
que o Patrick pegou no beta). Caça palavras inglesas e siglas não-PT antes de mandar pro TTS.
"""
import re

# palavras inglesas comuns que escapam em roteiro médico (o TTS lê em inglês)
_ING = {
    "contraindication", "trial", "trials", "endpoint", "endpoints", "outcome", "outcomes",
    "baseline", "follow-up", "followup", "borderline", "guideline", "guidelines", "statement",
    "feature", "bug", "cohort", "hazard", "mismatch", "run-in", "runin", "screening", "score",
    "scores", "landmark", "workshop", "overview", "target", "double-blind", "open-label",
    "placebo-controlled", "intention-to-treat", "primary", "secondary", "hard", "soft",
}
# siglas em inglês que trocam de idioma no áudio (dizer por extenso em PT)
_SIGLAS_ING = {"HFREF", "HFPEF", "MACE", "LVEF", "NYHA", "ACE", "ARB", "RCT", "ITT", "DSMB",
               "OMT", "GDMT", "BARC", "NT-PROBNP", "PROBNP", "SGLT2", "GLP-1", "GLP1"}
# siglas PORTUGUESAS aceitas (não flagrar)
_OK_PT = {"IC", "IAM", "PA", "FC", "FE", "FEVE", "SUS", "AVC", "TVP", "EP", "DPOC", "HAS", "DAC",
          "VE", "VD", "AE", "AD", "IECA", "BRA", "SCA", "ECG", "UTI", "CDI", "IM", "TV", "FA"}


_OK_PT |= {"SIM", "NAO", "NÃO", "STEMI", "NSTEMI", "SCA"}  # aceitos na fala do cardio BR


def cacar_ingles(texto):
    achados = []
    for m in re.finditer(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\-]*", texto):
        w = m.group(0)
        if re.search(r"[À-ÿ]", w):
            continue                       # tem acento → é português, ignora
        wl = w.lower()
        if wl in _ING or w.upper() in _SIGLAS_ING:
            achados.append(w)
        elif w.isupper() and 2 <= len(w) <= 6 and w not in _OK_PT:
            achados.append(w)  # sigla em caixa alta não-PT → provável inglês
    return sorted(set(achados), key=str.lower)


def falar(texto, caminho_mp3):
    """Gera o MP3 do roteiro com a config de TTS do .env (OpenAI). ElevenLabs é EXCLUSIVO do Radar.
    Lê: OPENAI_TTS_MODEL, OPENAI_TTS_VOICE, OPENAI_TTS_SPEED, OPENAI_TTS_INSTRUCTIONS."""
    import os
    from openai import OpenAI
    model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.getenv("OPENAI_TTS_VOICE", "onyx")
    instr = (os.getenv("OPENAI_TTS_INSTRUCTIONS", "") or "").strip()
    try:
        speed = float(os.getenv("OPENAI_TTS_SPEED", "1.0"))
    except ValueError:
        speed = 1.0
    cli = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    base = dict(model=model, voice=voice, input=texto[:4000])
    if instr:
        base["instructions"] = instr                     # steering de voz (só gpt-4o-*-tts)
    # tenta com speed; se o modelo não aceitar, refaz sem speed
    for kwargs in ({**base, "speed": speed}, base):
        try:
            with cli.audio.speech.with_streaming_response.create(**kwargs) as resp:
                resp.stream_to_file(caminho_mp3)
            return caminho_mp3
        except TypeError:
            continue
        except Exception as e:
            if "speed" in str(e).lower() and "speed" in kwargs:
                continue
            raise
    return caminho_mp3


if __name__ == "__main__":
    import sys
    t = open(sys.argv[1]).read()
    flags = cacar_ingles(t)
    print(f"⚠️  {len(flags)} termo(s) pra revisar (falar em português): {', '.join(flags)}" if flags
          else "✅ roteiro limpo — sem termo em inglês")
