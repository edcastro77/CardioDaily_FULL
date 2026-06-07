#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Biblioteca Web
Dr. Eduardo Castro

Servidor HTTP local para busca visual de artigos.
Inicia em http://localhost:5100 e abre no browser automaticamente.

USO:
    ./cardiodaily biblioteca
    python3 src/web_biblioteca.py
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests as req_lib

try:
    import markdown as _markdown_lib
    def _md_to_html(text: str) -> str:
        return _markdown_lib.markdown(text, extensions=["extra", "nl2br"])
except ImportError:
    import html as _html_lib
    def _md_to_html(text: str) -> str:
        return "<pre>" + _html_lib.escape(text) + "</pre>"

# ── WhatsApp ───────────────────────────────────────────────────────────────────
try:
    from whatsapp.webhook_handler import handle_webhook
    from whatsapp.user_manager import get_all_users, get_user, create_user, update_user
    from whatsapp import zapi_client as _zapi
    WHATSAPP_AVAILABLE = True
except ImportError:
    WHATSAPP_AVAILABLE = False

# ── Radar ──────────────────────────────────────────────────────────────────────
try:
    from radar.radar_pubmed import RadarPubMed, CATEGORIAS, CATEGORIAS_PT, JOURNAL_MAP
    RADAR_AVAILABLE = True
except ImportError:
    RADAR_AVAILABLE = False

_radar = RadarPubMed() if RADAR_AVAILABLE else None
_jobs: dict = {}          # job_id → {status, result, error}
_jobs_lock = threading.Lock()

# ─── Setup ────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent

# Instagram publisher (importação lazy para não bloquear startup)
_instagram_publisher = None
def _get_instagram_publisher():
    global _instagram_publisher
    if _instagram_publisher is None:
        try:
            from dotenv import load_dotenv
            load_dotenv(_ROOT / ".env")
            # Garantir que o root do projeto está no path
            _root_str = str(_ROOT)
            if _root_str not in sys.path:
                sys.path.insert(0, _root_str)
            from src.social.instagram_publisher import InstagramPublisher
            _instagram_publisher = InstagramPublisher()
        except Exception as e:
            print(f"⚠️  Instagram publisher não disponível: {e}")
    return _instagram_publisher
sys.path.insert(0, str(_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
CORPUS_DIR = _ROOT / "outputs" / "corpus"
PORT = 5100

_SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

# ─── HTML ─────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CardioDaily — Biblioteca</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f0f4f8; min-height: 100vh; }

  /* ── Header ── */
  .header { background: linear-gradient(135deg, #1a5f7a 0%, #16213e 100%);
             color: white; padding: 22px 32px; display: flex;
             align-items: center; gap: 14px; box-shadow: 0 2px 12px rgba(0,0,0,.3); }
  .header h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -.3px; }
  .header p { font-size: .85rem; opacity: .75; margin-top: 2px; }

  /* ── Painel de filtros ── */
  .filtros { background: white; padding: 20px 32px; display: flex;
             flex-wrap: wrap; gap: 14px; align-items: flex-end;
             border-bottom: 1px solid #e2e8f0;
             box-shadow: 0 1px 4px rgba(0,0,0,.07); }
  .filtros .grupo { display: flex; flex-direction: column; gap: 5px; }
  .filtros label { font-size: .75rem; font-weight: 600; color: #64748b;
                   text-transform: uppercase; letter-spacing: .5px; }
  .filtros input, .filtros select {
    border: 1.5px solid #e2e8f0; border-radius: 8px; padding: 8px 12px;
    font-size: .9rem; color: #1e293b; background: #f8fafc;
    outline: none; transition: border-color .2s; min-width: 140px; }
  .filtros input:focus, .filtros select:focus { border-color: #1a5f7a; background: white; }
  .filtros input[type=text] { min-width: 220px; }
  .filtros input[type=date] { min-width: 148px; }

  .btn-buscar { background: linear-gradient(135deg, #1a5f7a, #0e3d52);
    color: white; border: none; border-radius: 8px; padding: 9px 24px;
    font-size: .95rem; font-weight: 600; cursor: pointer; white-space: nowrap;
    transition: opacity .15s; height: 38px; }
  .btn-buscar:hover { opacity: .88; }
  .btn-limpar { background: none; border: 1.5px solid #cbd5e1; border-radius: 8px;
    padding: 7px 16px; font-size: .85rem; color: #64748b; cursor: pointer;
    height: 38px; transition: border-color .2s; }
  .btn-limpar:hover { border-color: #94a3b8; color: #334155; }

  /* ── Atalhos de data ── */
  .date-chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip { background: #f1f5f9; border: 1.5px solid #e2e8f0; border-radius: 20px;
    padding: 4px 12px; font-size: .78rem; color: #475569; cursor: pointer;
    transition: all .15s; white-space: nowrap; }
  .chip:hover, .chip.active { background: #1a5f7a; border-color: #1a5f7a;
    color: white; }
  .chip-add { border-color: #10b981; color: #065f46; background: #ecfdf5; }
  .chip-add:hover, .chip-add.active { background: #10b981; border-color: #10b981; color: white; }
  .chip-rev { border-color: #7c3aed; color: #4c1d95; background: #f5f3ff; }
  .chip-rev:hover, .chip-rev.active { background: #7c3aed; border-color: #7c3aed; color: white; }

  /* ── Resultados ── */
  .status-bar { padding: 12px 32px; font-size: .85rem; color: #64748b;
    background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
  .status-bar strong { color: #1e293b; }
  .resultados { padding: 20px 32px; display: grid; gap: 14px;
    grid-template-columns: repeat(auto-fill, minmax(520px, 1fr)); }

  /* ── Card ── */
  .card { background: white; border-radius: 12px; padding: 18px 20px;
    box-shadow: 0 1px 6px rgba(0,0,0,.08); border: 1px solid #e9eef4;
    transition: box-shadow .15s; display: flex; flex-direction: column; gap: 8px; }
  .card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.12); }

  .card-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .badge-nota { font-weight: 700; font-size: .85rem; padding: 3px 10px;
    border-radius: 20px; white-space: nowrap; }
  .nota-10 { background: #dcfce7; color: #166534; }
  .nota-9  { background: #d1fae5; color: #065f46; }
  .nota-8  { background: #dbeafe; color: #1e40af; }
  .nota-7  { background: #ede9fe; color: #5b21b6; }
  .nota-low { background: #f1f5f9; color: #475569; }

  .badge-tipo { font-size: .75rem; padding: 3px 9px; border-radius: 20px;
    font-weight: 600; white-space: nowrap; }
  .tipo-original   { background: #fef3c7; color: #92400e; }
  .tipo-revisao    { background: #e0f2fe; color: #0c4a6e; }
  .tipo-metanalise { background: #f0fdf4; color: #14532d; }
  .tipo-guideline  { background: #fdf4ff; color: #6b21a8; }
  .tipo-outro      { background: #f1f5f9; color: #475569; }

  .card-revista { font-size: .8rem; color: #64748b; margin-left: auto; }
  .card-data { font-size: .78rem; color: #94a3b8; }
  .card-adicionado { font-size: .72rem; color: #10b981; background: #ecfdf5;
    border-radius: 10px; padding: 2px 7px; }

  .card-titulo { font-size: .97rem; font-weight: 600; color: #1e293b;
    line-height: 1.4; }
  .card-doenca { font-size: .78rem; color: #64748b; }
  .card-resumo { font-size: .84rem; color: #334155; line-height: 1.6;
    background: #f8fafc; border-radius: 6px; padding: 10px 12px;
    border-left: 3px solid #1a5f7a;
    max-height: 220px; overflow-y: auto; }
  .card-resumo h1,.card-resumo h2,.card-resumo h3 { font-size:.92rem; font-weight:700; color:#1a5f7a; margin:8px 0 4px; }
  .card-resumo h4,.card-resumo h5 { font-size:.86rem; font-weight:600; color:#334155; margin:6px 0 3px; }
  .card-resumo p { margin: 4px 0; }
  .card-resumo ul,.card-resumo ol { margin: 4px 0 4px 16px; padding: 0; }
  .card-resumo li { margin-bottom: 2px; }
  .card-resumo strong { color: #1e293b; }
  .card-resumo hr { border: none; border-top: 1px solid #e2e8f0; margin: 8px 0; }
  .card-resumo.vazio { color: #94a3b8; font-style: italic; border-left-color: #cbd5e1; }

  .card-acoes { display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
  .btn-primary { background: #1a5f7a; color: white; border: none; border-radius: 6px;
    padding: 7px 15px; font-size: .82rem; font-weight: 600; cursor: pointer;
    text-decoration: none; transition: opacity .15s; display: inline-flex;
    align-items: center; gap: 5px; }
  .btn-primary:hover { opacity: .85; }
  .btn-secondary { background: none; border: 1.5px solid #1a5f7a; color: #1a5f7a;
    border-radius: 6px; padding: 6px 14px; font-size: .82rem; font-weight: 600;
    cursor: pointer; text-decoration: none; transition: all .15s;
    display: inline-flex; align-items: center; gap: 5px; }
  .btn-secondary:hover { background: #1a5f7a; color: white; }
  .btn-secondary.disabled { border-color: #e2e8f0; color: #cbd5e1; cursor: default; pointer-events: none; }
  .btn-insta { background: linear-gradient(135deg, #833ab4, #fd1d1d, #fcb045); color: white;
    border: none; border-radius: 6px; padding: 7px 14px; font-size: .82rem; font-weight: 700;
    cursor: pointer; transition: opacity .15s; }
  .btn-insta:hover { opacity: .85; }

  /* Modal Instagram */
  .insta-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,.55);
    z-index:1000; align-items:center; justify-content:center; }
  .insta-overlay.open { display:flex; }
  .insta-modal { background:#fff; border-radius:16px; width:520px; max-width:95vw;
    max-height:90vh; overflow-y:auto; padding:28px; box-shadow:0 20px 60px rgba(0,0,0,.3); }
  .insta-modal h3 { font-size:1.1rem; font-weight:800; color:#1a1a2e; margin-bottom:16px;
    display:flex; align-items:center; gap:8px; }
  .insta-preview-img { width:100%; border-radius:10px; margin-bottom:16px;
    border:1px solid #e2e8f0; }
  .insta-caption-box { background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:8px;
    padding:14px; font-size:.88rem; line-height:1.6; color:#334155; white-space:pre-wrap;
    margin-bottom:14px; min-height:80px; }
  .insta-actions { display:flex; gap:10px; flex-wrap:wrap; }
  .insta-close { position:absolute; top:12px; right:16px; font-size:1.4rem; cursor:pointer;
    color:#94a3b8; background:none; border:none; }
  .insta-loading { color:#94a3b8; font-style:italic; font-size:.9rem; }
  .copy-ok { background: #16a34a !important; color: white !important; border-color: #16a34a !important; }

  /* ── Estado vazio / loading ── */
  .empty { text-align: center; padding: 60px 20px; color: #94a3b8; }
  .empty .icon { font-size: 3rem; margin-bottom: 12px; }
  .spinner { display: inline-block; width: 32px; height: 32px;
    border: 3px solid #e2e8f0; border-top-color: #1a5f7a;
    border-radius: 50%; animation: spin .7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .loading-wrap { text-align: center; padding: 50px; }
</style>
</head>
<body>

<div class="header">
  <div style="flex:1">
    <h1>🏥 CardioDaily — Biblioteca</h1>
    <p>Busca de artigos por tema, data, tipo e nota</p>
  </div>
  <a href="/radar" target="_blank"
     style="background:rgba(255,255,255,.15);border:1.5px solid rgba(255,255,255,.4);
            color:white;border-radius:8px;padding:8px 18px;font-size:.88rem;font-weight:600;
            text-decoration:none;white-space:nowrap;transition:background .15s"
     onmouseover="this.style.background='rgba(255,255,255,.25)'"
     onmouseout="this.style.background='rgba(255,255,255,.15)'">
    📡 Radar PubMed
  </a>
</div>

<div class="filtros">
  <div class="grupo">
    <label>Tema (opcional)</label>
    <input type="text" id="q" placeholder="ex: dac cronica, FA, SGLT2, HCM…"
           onkeydown="if(event.key==='Enter') buscar()">
  </div>

  <div class="grupo">
    <label>Revista</label>
    <div class="date-chips" style="flex-wrap:wrap">
      <span class="chip chip-rev" onclick="setRevista('nejm',this)">NEJM</span>
      <span class="chip chip-rev" onclick="setRevista('jacc',this)">JACC</span>
      <span class="chip chip-rev" onclick="setRevista('jama',this)">JAMA</span>
      <span class="chip chip-rev" onclick="setRevista('circulation',this)">Circulation</span>
      <span class="chip chip-rev" onclick="setRevista('ehj',this)">EHJ</span>
      <span class="chip chip-rev" onclick="setRevista('lancet',this)">Lancet</span>
    </div>
    <input type="text" id="revista" placeholder="ou digite outra revista…"
           style="margin-top:5px;font-size:.85rem"
           onkeydown="if(event.key==='Enter') buscar()">
  </div>

  <div class="grupo">
    <label>Adicionados ao sistema</label>
    <div class="date-chips">
      <span class="chip chip-add" onclick="setChip('add_semana', this)">&#128229; Esta semana</span>
      <span class="chip chip-add" onclick="setChip('add_mes', this)">&#128229; Este m&#234;s</span>
      <span class="chip chip-add" onclick="setChip('add_2meses', this)">&#128229; 2 meses</span>
    </div>
  </div>
  <div class="grupo">
    <label>Publicado na revista</label>
    <div class="date-chips">
      <span class="chip" onclick="setChip('semana', this)">Pub. semana</span>
      <span class="chip" onclick="setChip('mes', this)">Pub. m&#234;s</span>
      <span class="chip" onclick="setChip('2meses', this)">Pub. 2 meses</span>
      <span class="chip" onclick="setChip('todos', this)">Todos</span>
    </div>
  </div>

  <div class="grupo">
    <label>Publicado após</label>
    <input type="date" id="data_inicio">
  </div>
  <div class="grupo">
    <label>Publicado antes</label>
    <input type="date" id="data_fim">
  </div>

  <div class="grupo">
    <label>Tipo</label>
    <select id="tipo">
      <option value="">Todos</option>
      <option value="original">Artigo Original</option>
      <option value="revisao">Revisão</option>
      <option value="metanalise">Meta-análise</option>
      <option value="guideline">Diretriz / Guideline</option>
    </select>
  </div>

  <div class="grupo">
    <label>Nota mínima</label>
    <select id="nota">
      <option value="1">Qualquer</option>
      <option value="5" selected>≥ 5</option>
      <option value="6">≥ 6</option>
      <option value="7">≥ 7</option>
      <option value="8">≥ 8</option>
      <option value="9">≥ 9</option>
      <option value="10">10</option>
    </select>
  </div>

  <div class="grupo">
    <label>Máx. resultados</label>
    <select id="limite">
      <option value="20">20</option>
      <option value="50" selected>50</option>
      <option value="100">100</option>
      <option value="200">200</option>
    </select>
  </div>

  <button class="btn-buscar" onclick="buscar()">🔍 Buscar</button>
  <button class="btn-limpar" onclick="limpar()">✕ Limpar</button>
</div>

<div class="status-bar" id="status">
  Pronto. Use os filtros acima e clique em <strong>Buscar</strong>.
</div>

<div class="resultados" id="resultados">
  <div class="empty" style="grid-column:1/-1">
    <div class="icon">📚</div>
    <p>2.700+ artigos cardiológicos indexados</p>
    <p style="margin-top:8px;font-size:.85rem">Filtre por data, tipo ou tema para encontrar o que precisa</p>
  </div>
</div>

<script>
const TIPOS = {
  original:   ['tipo-original',   'Original'],
  revisao:    ['tipo-revisao',    'Revisão'],
  metanalise: ['tipo-metanalise', 'Meta-análise'],
  guideline:  ['tipo-guideline',  'Diretriz'],
};

function notaClass(n) {
  if (n >= 10) return 'nota-10';
  if (n >= 9)  return 'nota-9';
  if (n >= 8)  return 'nota-8';
  if (n >= 7)  return 'nota-7';
  return 'nota-low';
}

function formatDate(d) {
  if (!d) return '?';
  const meses = ['','Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  const [y, m, day] = d.split('-');
  return `${parseInt(day)}/${meses[parseInt(m)]}/${y}`;
}

function isoWeekStart(deltaWeeks = 0) {
  const d = new Date();
  d.setDate(d.getDate() - (d.getDay() === 0 ? 6 : d.getDay() - 1) - deltaWeeks * 7);
  return d.toISOString().split('T')[0];
}
function isoWeekEnd(deltaWeeks = 0) {
  const d = new Date();
  const start = new Date(isoWeekStart(deltaWeeks));
  start.setDate(start.getDate() + 6);
  return start.toISOString().split('T')[0];
}
function monthStart() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`;
}
function today() {
  return new Date().toISOString().split('T')[0];
}
function twoMonthsAgo() {
  const d = new Date();
  d.setMonth(d.getMonth() - 2);
  return d.toISOString().split('T')[0];
}

let activeChip = null;
let currentModo = '';

function nDaysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().split('T')[0];
}
function sixMonthsAgo() {
  const d = new Date();
  d.setMonth(d.getMonth() - 6);
  return d.toISOString().split('T')[0];
}

const _REVISTA_MAP = {
  nejm: 'N Engl J Med',
  jacc: 'JACC',
  jama: 'JAMA',
  circulation: 'Circulation',
  ehj: 'EHJ',
  lancet: 'Lancet',
};
function setRevista(key, el) {
  document.querySelectorAll('.chip-rev').forEach(c => c.classList.remove('active'));
  const inp = document.getElementById('revista');
  if (inp.value === (_REVISTA_MAP[key] || key)) {
    inp.value = ''; // toggle off
  } else {
    el.classList.add('active');
    inp.value = _REVISTA_MAP[key] || key;
  }
  buscar();
}

function setChip(tipo, el) {
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  if (el) el.classList.add('active');
  activeChip = tipo;
  const di = document.getElementById('data_inicio');
  const df = document.getElementById('data_fim');
  const td = today();
  if (tipo === 'add_semana')  { currentModo = 'recentes'; di.value = nDaysAgo(7);      df.value = td; }
  else if (tipo === 'add_mes')     { currentModo = 'recentes'; di.value = monthStart();     df.value = td; }
  else if (tipo === 'add_2meses')  { currentModo = 'recentes'; di.value = twoMonthsAgo();   df.value = td; }
  else if (tipo === 'semana')      { currentModo = '';          di.value = nDaysAgo(7);      df.value = td; }
  else if (tipo === '2semanas')    { currentModo = '';          di.value = nDaysAgo(14);     df.value = td; }
  else if (tipo === 'mes')         { currentModo = '';          di.value = monthStart();     df.value = td; }
  else if (tipo === '2meses')      { currentModo = '';          di.value = twoMonthsAgo();   df.value = td; }
  else if (tipo === '6meses')      { currentModo = '';          di.value = sixMonthsAgo();   df.value = td; }
  else if (tipo === 'todos')       { currentModo = '';          di.value = '';               df.value = ''; }
  buscar();
}

function limpar() {
  currentModo = '';
  document.getElementById('q').value = '';
  document.getElementById('revista').value = '';
  document.getElementById('data_inicio').value = '';
  document.getElementById('data_fim').value = '';
  document.getElementById('tipo').value = '';
  document.getElementById('nota').value = '5';
  document.getElementById('limite').value = '20';
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  document.getElementById('status').innerHTML = 'Filtros limpos.';
  document.getElementById('resultados').innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="icon">📚</div><p>Use os filtros acima para buscar</p></div>';
}

async function buscar() {
  const q = document.getElementById('q').value.trim();
  const tipo = document.getElementById('tipo').value;
  const nota = document.getElementById('nota').value;
  const limite = document.getElementById('limite').value;
  const data_inicio = document.getElementById('data_inicio').value;
  const data_fim = document.getElementById('data_fim').value;
  const revista = document.getElementById('revista').value.trim();

  const modo = currentModo;
  const params = new URLSearchParams({ q, tipo, nota, limite, data_inicio, data_fim, modo, revista });
  document.getElementById('status').innerHTML = '<span class="spinner"></span> Buscando...';
  document.getElementById('resultados').innerHTML = '<div class="loading-wrap"><span class="spinner"></span></div>';

  try {
    const resp = await fetch('/api/buscar?' + params);
    const data = await resp.json();
    renderResultados(data, q || tipo || data_inicio || 'filtros');
  } catch(e) {
    document.getElementById('status').textContent = '❌ Erro na busca: ' + e.message;
    document.getElementById('resultados').innerHTML = '';
  }
}

function renderResultados(artigos, query) {
  const n = artigos.length;
  document.getElementById('status').innerHTML =
    n === 0
      ? 'Nenhum artigo encontrado com esses critérios.'
      : `<strong>${n}</strong> artigo${n>1?'s':''} encontrado${n>1?'s':''} · clique em <strong>Abrir PDF</strong> para visualizar`;

  if (n === 0) {
    document.getElementById('resultados').innerHTML =
      '<div class="empty" style="grid-column:1/-1"><div class="icon">🔍</div><p>Nenhum resultado. Tente ampliar os filtros.</p></div>';
    return;
  }

  const html = artigos.map((a, idx) => {
    const nota = a.nota_aplicabilidade || '?';
    const nClass = notaClass(nota);
    const tipo = a.tipo_estudo || '';
    const [tipoClass, tipoLabel] = TIPOS[tipo] || ['tipo-outro', tipo || '?'];
    const revista = a.revista && !/^\\d+$/.test(a.revista) ? a.revista : '';
    const data = formatDate(a.data_publicacao);
    const adicionado = a.created_at ? a.created_at.split('T')[0].split(' ')[0] : null;
    const titulo = a.titulo_display || a.doc_id;
    const doenca = a.doenca_principal || '';
    const resumo = a.resumo_markdown || '';
    const resumoRendered = a.resumo_html || '';
    const doi = a.doi || '';
    const docId = a.doc_id;
    const temImagem = a.tem_imagem;
    const resumoId = `resumo_${idx}`;

    const resumoHtml = resumoRendered
      ? `<div class="card-resumo" id="${resumoId}">${resumoRendered}</div>`
      : resumo
      ? `<div class="card-resumo" id="${resumoId}">${escHtml(resumo)}</div>`
      : `<div class="card-resumo vazio" id="${resumoId}">Resumo clínico não disponível para este artigo.</div>`;

    const btnCopiar = resumo
      ? `<button class="btn-primary" onclick="copiar('${resumoId}', this)">📋 Copiar Resumo</button>`
      : `<button class="btn-secondary disabled">📋 Sem resumo</button>`;

    const btnImg = temImagem
      ? `<a class="btn-secondary" href="/img/${docId}" target="_blank">🗺️ Infográfico</a>`
      : `<span class="btn-secondary disabled">🗺️ Sem infográfico</span>`;

    const btnInsta = temImagem
      ? `<button class="btn-insta" onclick="abrirInstagram('${docId}')">📸 Instagram</button>`
      : ``;

    const btnAnalise = `<a class="btn-secondary" href="/analise/${docId}" target="_blank">📄 Análise · PDF</a>`;

    const btnDoi = doi
      ? `<a class="btn-secondary" href="https://doi.org/${doi}" target="_blank">🔗 DOI</a>`
      : '';

    return `<div class="card">
      <div class="card-top">
        <span class="badge-nota ${nClass}">⭐ ${nota}/10</span>
        <span class="badge-tipo ${tipoClass}">${tipoLabel}</span>
        ${revista ? `<span class="card-revista">${escHtml(revista)}</span>` : ''}
        <span class="card-data">${data}</span>
        ${adicionado ? `<span class="card-adicionado" title="Adicionado ao sistema">+${adicionado}</span>` : ''}
      </div>
      <div class="card-titulo">${escHtml(titulo)}</div>
      ${doenca ? `<div class="card-doenca">🏷️ ${escHtml(doenca)}</div>` : ''}
      ${resumoHtml}
      <div class="card-acoes">${btnCopiar}${btnImg}${btnInsta}${btnAnalise}${btnDoi}</div>
    </div>`;
  }).join('');

  document.getElementById('resultados').innerHTML = html;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function stripMd(t) {
  return t
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/^#+\s+/gm, '')
    .replace(/\|[-:\s|]+\|/g, '')
    .replace(/^\|(.+)\|$/gm, (_, r) => r.split('|').map(c => c.trim()).filter(Boolean).join(' · '))
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^[-*+]\s+/gm, '• ')
    .replace(/\\n{3,}/g, '\\n\\n')
    .trim();
}

function copiar(resumoId, btn) {
  const el = document.getElementById(resumoId);
  if (!el) return;
  const texto = stripMd(el.innerText || el.textContent || '');
  navigator.clipboard.writeText(texto).then(() => {
    btn.textContent = '✅ Copiado!';
    btn.classList.add('copy-ok');
    setTimeout(() => {
      btn.textContent = '📋 Copiar Resumo';
      btn.classList.remove('copy-ok');
    }, 2000);
  }).catch(() => {
    // fallback legado
    const ta = document.createElement('textarea');
    ta.value = texto; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
    btn.textContent = '✅ Copiado!';
    setTimeout(() => btn.textContent = '📋 Copiar Resumo', 2000);
  });
}

// ── Instagram Modal ──────────────────────────────────────────────────────────
async function abrirInstagram(docId) {
  const overlay = document.getElementById('instaOverlay');
  const img     = document.getElementById('instaImg');
  const caption = document.getElementById('instaCaption');
  const status  = document.getElementById('instaStatus');

  // Mostrar modal com loading
  img.src = `/img/${docId}`;
  caption.textContent = '';
  status.textContent = '⏳ Gerando caption com IA...';
  overlay.classList.add('open');
  document.getElementById('instaCopyBtn').dataset.docId = docId;

  // Buscar caption
  try {
    const r = await fetch(`/instagram/${docId}`);
    const data = await r.json();
    if (data.error) {
      status.textContent = '❌ ' + data.error;
    } else {
      caption.textContent = data.full_text;
      status.textContent = data.cached ? '📦 Caption do cache' : '✅ Caption gerada pelo Claude';
    }
  } catch(e) {
    status.textContent = '❌ Erro ao gerar caption';
  }
}

function fecharInstagram() {
  document.getElementById('instaOverlay').classList.remove('open');
}

async function copiarCaption() {
  const caption = document.getElementById('instaCaption').textContent;
  if (!caption) return;
  try {
    await navigator.clipboard.writeText(caption);
    const btn = document.getElementById('instaCopyBtn');
    btn.textContent = '✅ Copiado!';
    setTimeout(() => btn.textContent = '📋 Copiar Caption', 2000);
  } catch(e) {
    alert('Erro ao copiar. Selecione o texto manualmente.');
  }
}

async function copiarImagem(docId) {
  window.open(`/img/${docId}`, '_blank');
}

// Fechar ao clicar fora do modal
document.addEventListener('click', e => {
  const overlay = document.getElementById('instaOverlay');
  if (e.target === overlay) fecharInstagram();
});

// Busca automática ao carregar — artigos adicionados nos últimos 2 meses, nota ≥ 5
window.onload = () => {
  const chips = document.querySelectorAll('.chip-add');
  const chip2m = Array.from(chips).find(c => c.textContent.includes('2 meses'));
  setChip('add_2meses', chip2m || chips[2]);
};
</script>

<!-- Modal Instagram -->
<div class="insta-overlay" id="instaOverlay">
  <div class="insta-modal" style="position:relative;">
    <button class="insta-close" onclick="fecharInstagram()">✕</button>
    <h3>📸 Preview Instagram</h3>
    <img class="insta-preview-img" id="instaImg" src="" alt="Infográfico">
    <div class="insta-caption-box" id="instaCaption"></div>
    <div class="insta-loading" id="instaStatus"></div>
    <div class="insta-actions" style="margin-top:12px;">
      <button class="btn-primary" id="instaCopyBtn" onclick="copiarCaption()">📋 Copiar Caption</button>
      <button class="btn-secondary" onclick="copiarImagem(document.getElementById('instaCopyBtn').dataset.docId)">🖼️ Abrir Imagem</button>
      <button class="btn-secondary" onclick="fecharInstagram()">Fechar</button>
    </div>
  </div>
</div>

</body>
</html>
"""

# ─── Radar HTML ───────────────────────────────────────────────────────────────

_RADAR_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CardioDaily — Radar PubMed</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f8;min-height:100vh}}
.header{{background:linear-gradient(135deg,#1a5f7a 0%,#16213e 100%);color:white;padding:18px 28px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 12px rgba(0,0,0,.3)}}
.header h1{{font-size:1.3rem;font-weight:700}}
.header a{{color:rgba(255,255,255,.7);font-size:.82rem;text-decoration:none;margin-left:auto}}
.header a:hover{{color:white}}
.main{{max-width:900px;margin:28px auto;padding:0 20px}}
.tabs{{display:flex;gap:0;border-bottom:2px solid #e2e8f0;margin-bottom:24px}}
.tab{{padding:10px 22px;font-size:.9rem;font-weight:600;color:#64748b;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s}}
.tab.active{{color:#1a5f7a;border-bottom-color:#1a5f7a}}
.pane{{display:none}}.pane.active{{display:block}}
.card{{background:white;border-radius:12px;padding:22px;box-shadow:0 1px 8px rgba(0,0,0,.08);border:1px solid #e9eef4;margin-bottom:16px}}
.card h3{{font-size:1rem;font-weight:700;color:#1a3a5c;margin-bottom:14px}}
.form-row{{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin-bottom:14px}}
.grupo{{display:flex;flex-direction:column;gap:5px}}
.grupo label{{font-size:.75rem;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.5px}}
select,input[type=text],input[type=number]{{border:1.5px solid #e2e8f0;border-radius:8px;padding:8px 12px;font-size:.88rem;color:#1e293b;background:#f8fafc;outline:none;transition:border-color .2s}}
select:focus,input:focus{{border-color:#1a5f7a;background:white}}
.btn{{border:none;border-radius:8px;padding:9px 22px;font-size:.9rem;font-weight:600;cursor:pointer;transition:opacity .15s;white-space:nowrap}}
.btn-primary{{background:linear-gradient(135deg,#1a5f7a,#0e3d52);color:white}}
.btn-primary:hover{{opacity:.88}}
.btn-primary:disabled{{opacity:.5;cursor:not-allowed}}
.btn-secondary{{background:none;border:1.5px solid #1a5f7a;color:#1a5f7a}}
.btn-secondary:hover{{background:#1a5f7a;color:white}}
.status-box{{border-radius:8px;padding:12px 16px;font-size:.88rem;margin-bottom:14px;display:none}}
.status-running{{background:#eff6ff;border:1px solid #bfdbfe;color:#1e40af;display:flex;align-items:center;gap:10px}}
.status-ok{{background:#f0fdf4;border:1px solid #bbf7d0;color:#166534}}
.status-err{{background:#fef2f2;border:1px solid #fecaca;color:#991b1b}}
.spinner{{display:inline-block;width:18px;height:18px;border:2.5px solid #bfdbfe;border-top-color:#1a5f7a;border-radius:50%;animation:spin .7s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.result-area{{display:none}}
.script-box{{background:#f8fafc;border:1.5px solid #e2e8f0;border-radius:8px;padding:16px;font-size:.88rem;line-height:1.75;color:#334155;white-space:pre-wrap;max-height:500px;overflow-y:auto;margin-bottom:14px;width:100%;resize:vertical;font-family:inherit}}
.artigos-lista{{margin-bottom:14px}}
.artigo-item{{border-left:3px solid #1a5f7a;padding:8px 12px;margin-bottom:8px;background:#f8fafc;border-radius:0 6px 6px 0;font-size:.84rem}}
.artigo-item strong{{color:#1a3a5c;display:block;margin-bottom:2px}}
.artigo-item .meta{{color:#64748b;font-size:.78rem}}
.audio-box{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#fef9f0;border:1.5px solid #fde68a;border-radius:8px;padding:14px;margin-bottom:14px}}
.audio-player{{width:100%;margin-top:8px}}
h4{{font-size:.9rem;font-weight:700;color:#1a3a5c;margin:16px 0 8px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:600}}
.badge-rct{{background:#dcfce7;color:#166534}}
.badge-review{{background:#e0f2fe;color:#0c4a6e}}
.badge-other{{background:#f1f5f9;color:#475569}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>📡 CardioDaily — Radar PubMed</h1>
  </div>
  <a href="/">&#8592; Voltar à Biblioteca</a>
</div>
<div class="main">

  <!-- Tabs -->
  <div class="tabs">
    <div class="tab active" onclick="showTab('pubmed',this)">🔍 PubMed por Categoria</div>
    <div class="tab" onclick="showTab('numero',this)">📰 Número de Revista</div>
  </div>

  <!-- PANE: PubMed por Categoria -->
  <div class="pane active" id="pane-pubmed">
    <div class="card">
      <h3>Configuração da Busca</h3>
      <div class="form-row">
        <div class="grupo">
          <label>Modo</label>
          <select id="pm-modo" onchange="toggleModo()">
            <option value="categoria">Categoria</option>
            <option value="keywords">Keywords customizadas</option>
          </select>
        </div>
        <div class="grupo" id="grp-cat">
          <label>Categoria</label>
          <select id="pm-categoria">{CAT_OPTIONS}</select>
        </div>
        <div class="grupo" id="grp-kw" style="display:none;flex:1">
          <label>Keywords (separadas por vírgula)</label>
          <input type="text" id="pm-keywords" style="width:100%" placeholder="heart failure, SGLT2, HFpEF...">
        </div>
        <div class="grupo">
          <label>Últimos (dias)</label>
          <input type="number" id="pm-dias" value="7" min="1" max="30" style="width:80px">
        </div>
        <div class="grupo">
          <label>Máx. artigos</label>
          <input type="number" id="pm-max" value="50" min="10" max="100" style="width:80px">
        </div>
        <button class="btn btn-primary" id="pm-run" onclick="executarPubmed()">🔍 Buscar e Analisar</button>
      </div>
    </div>
    <div class="status-box" id="pm-status"></div>
    <div class="result-area" id="pm-result">
      <div class="card">
        <h3>Artigos Encontrados (<span id="pm-count">0</span>)</h3>
        <div class="artigos-lista" id="pm-artigos"></div>
      </div>
      <div class="card">
        <h3>Triagem com IA</h3>
        <div class="script-box" id="pm-triagem"></div>
      </div>
      <div class="card">
        <h3>Script de Podcast</h3>
        <textarea class="script-box" id="pm-script" rows="18" spellcheck="false"></textarea>
        <div class="audio-box" id="pm-audio-box">
          <div style="flex:1">
            <strong style="font-size:.88rem">Gerar Áudio</strong>
            <div style="font-size:.78rem;color:#92400e;margin-top:2px">OpenAI TTS-HD · voz onyx</div>
          </div>
          <button class="btn btn-primary" id="pm-audio-btn" onclick="gerarAudio('pubmed')">🎙️ Gerar MP3</button>
          <audio id="pm-player" class="audio-player" controls style="display:none"></audio>
        </div>
      </div>
    </div>
  </div>

  <!-- PANE: Número de Revista -->
  <div class="pane" id="pane-numero">
    <div class="card">
      <h3>Configuração</h3>
      <div class="form-row">
        <div class="grupo">
          <label>Revista</label>
          <select id="nr-revista">{JOURNAL_OPTIONS}</select>
        </div>
        <button class="btn btn-primary" id="nr-run" onclick="executarNumero()">📰 Buscar Último Número</button>
      </div>
    </div>
    <div class="status-box" id="nr-status"></div>
    <div class="result-area" id="nr-result">
      <div class="card">
        <h3 id="nr-titulo">Artigos</h3>
        <div class="artigos-lista" id="nr-artigos"></div>
      </div>
      <div class="card">
        <h3>Script de Podcast</h3>
        <textarea class="script-box" id="nr-script" rows="18" spellcheck="false"></textarea>
        <div class="audio-box" id="nr-audio-box">
          <div style="flex:1">
            <strong style="font-size:.88rem">Gerar Áudio</strong>
            <div style="font-size:.78rem;color:#92400e;margin-top:2px">OpenAI TTS-HD · voz onyx</div>
          </div>
          <button class="btn btn-primary" id="nr-audio-btn" onclick="gerarAudio('numero')">🎙️ Gerar MP3</button>
          <audio id="nr-player" class="audio-player" controls style="display:none"></audio>
        </div>
      </div>
    </div>
  </div>

</div>

<script>
let _lastScript = {{pubmed:'', numero:''}};
let _pollTimer = null;

function showTab(id, el) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('pane-' + id).classList.add('active');
}}

function toggleModo() {{
  const m = document.getElementById('pm-modo').value;
  document.getElementById('grp-cat').style.display = m === 'categoria' ? '' : 'none';
  document.getElementById('grp-kw').style.display = m === 'keywords' ? '' : 'none';
}}

function setStatus(prefix, msg, type) {{
  const el = document.getElementById(prefix + '-status');
  el.className = 'status-box status-' + type;
  el.style.display = 'flex';
  if (type === 'running') {{
    el.innerHTML = '<span class="spinner"></span> ' + msg;
  }} else {{
    el.innerHTML = msg;
  }}
}}

function renderArtigos(prefix, artigos) {{
  const el = document.getElementById(prefix + '-artigos');
  if (!artigos || !artigos.length) {{ el.innerHTML = '<em style="color:#94a3b8">Nenhum artigo</em>'; return; }}
  document.getElementById(prefix + '-count') && (document.getElementById(prefix + '-count').textContent = artigos.length);
  el.innerHTML = artigos.map(a => {{
    const badge = (a.types || []).includes('Randomized Controlled Trial') ? '<span class="badge badge-rct">RCT</span>' :
                  (a.types || []).includes('Meta-Analysis') ? '<span class="badge badge-review">Meta</span>' : '';
    const ttype = a.type ? `<span class="badge badge-other">${{a.type}}</span>` : '';
    return `<div class="artigo-item">
      <strong>${{esc(a.title || a.pmid || '?')}}</strong>
      <div class="meta">
        ${{badge}}${{ttype}}
        <span style="margin:0 6px">·</span>${{esc(a.journal || a.year || '')}}
        ${{a.pmid ? ` · <a href="https://pubmed.ncbi.nlm.nih.gov/${{a.pmid}}/" target="_blank" style="color:#1a5f7a">PubMed</a>` : ''}}
        ${{a.doi ? ` · <a href="https://doi.org/${{a.doi}}" target="_blank" style="color:#1a5f7a">DOI</a>` : ''}}
      </div>
    </div>`;
  }}).join('');
}}

function esc(s) {{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

async function executarPubmed() {{
  const modo = document.getElementById('pm-modo').value;
  const cat = document.getElementById('pm-categoria').value;
  const kw = document.getElementById('pm-keywords').value;
  const dias = document.getElementById('pm-dias').value;
  const max = document.getElementById('pm-max').value;

  document.getElementById('pm-run').disabled = true;
  document.getElementById('pm-result').style.display = 'none';
  setStatus('pm', 'Iniciando busca no PubMed…', 'running');

  try {{
    const r = await fetch('/api/radar/iniciar', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{tipo:'pubmed', modo, categoria:cat, keywords:kw, dias:parseInt(dias), max_results:parseInt(max)}})
    }});
    const d = await r.json();
    if (d.error) {{ setStatus('pm', '❌ ' + d.error, 'err'); document.getElementById('pm-run').disabled = false; return; }}
    pollJob(d.job_id, 'pm');
  }} catch(e) {{
    setStatus('pm', '❌ Erro: ' + e.message, 'err');
    document.getElementById('pm-run').disabled = false;
  }}
}}

async function executarNumero() {{
  const revista = document.getElementById('nr-revista').value;
  document.getElementById('nr-run').disabled = true;
  document.getElementById('nr-result').style.display = 'none';
  setStatus('nr', 'Detectando último número no PubMed…', 'running');

  try {{
    const r = await fetch('/api/radar/iniciar', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{tipo:'numero', revista}})
    }});
    const d = await r.json();
    if (d.error) {{ setStatus('nr', '❌ ' + d.error, 'err'); document.getElementById('nr-run').disabled = false; return; }}
    pollJob(d.job_id, 'nr');
  }} catch(e) {{
    setStatus('nr', '❌ Erro: ' + e.message, 'err');
    document.getElementById('nr-run').disabled = false;
  }}
}}

function pollJob(job_id, prefix) {{
  if (_pollTimer) clearInterval(_pollTimer);
  _pollTimer = setInterval(async () => {{
    try {{
      const r = await fetch('/api/radar/status/' + job_id);
      const d = await r.json();

      if (d.status === 'running') {{
        setStatus(prefix, (d.msg || 'Processando…'), 'running');
        return;
      }}

      clearInterval(_pollTimer);
      _pollTimer = null;

      if (d.status === 'error') {{
        setStatus(prefix, '❌ ' + d.error, 'err');
        document.getElementById(prefix === 'pm' ? 'pm-run' : 'nr-run').disabled = false;
        return;
      }}

      // Done
      const res = d.result;
      setStatus(prefix, `✅ Concluído — ${{res.artigos ? res.artigos.length : 0}} artigos`, 'ok');
      document.getElementById(prefix === 'pm' ? 'pm-run' : 'nr-run').disabled = false;

      if (prefix === 'pm') {{
        renderArtigos('pm', res.artigos || []);
        document.getElementById('pm-triagem').textContent = res.triagem || '';
        document.getElementById('pm-script').value = res.script || '';
        document.getElementById('pm-result').style.display = 'block';
      }} else {{
        renderArtigos('nr', res.artigos || []);
        if (res.journal && res.volume) {{
          document.getElementById('nr-titulo').textContent =
            `${{res.journal}} — Vol ${{res.volume}}, N ${{res.issue}} (${{res.artigos ? res.artigos.length : 0}} artigos)`;
        }}
        document.getElementById('nr-script').value = res.script || '';
        document.getElementById('nr-result').style.display = 'block';
      }}

    }} catch(e) {{
      clearInterval(_pollTimer); _pollTimer = null;
      setStatus(prefix, '❌ Erro de comunicação: ' + e.message, 'err');
    }}
  }}, 2000);
}}

async function gerarAudio(tipo) {{
  const prefix = tipo === 'pubmed' ? 'pm' : 'nr';
  const script = document.getElementById(prefix + '-script').value.trim();
  if (!script) {{ alert('Execute o radar primeiro para gerar o script.'); return; }}
  const btn = document.getElementById(prefix + '-audio-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Gerando…';

  try {{
    const r = await fetch('/api/radar/audio', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{script, nome: 'radar_' + tipo}})
    }});
    const d = await r.json();
    if (d.error) {{ alert('❌ ' + d.error); btn.disabled = false; btn.textContent = '🎙️ Gerar MP3'; return; }}

    const player = document.getElementById(prefix + '-player');
    player.src = '/api/radar/audio/' + d.filename;
    player.style.display = 'block';
    btn.disabled = false;
    btn.textContent = '🎙️ Regenerar MP3';
  }} catch(e) {{
    alert('❌ Erro: ' + e.message);
    btn.disabled = false;
    btn.textContent = '🎙️ Gerar MP3';
  }}
}}
</script>
</body>
</html>
"""

_RADAR_HTML_POPULATED = None  # lazy — built on first request

def _build_radar_html():
    global _RADAR_HTML_POPULATED
    if _RADAR_HTML_POPULATED:
        return _RADAR_HTML_POPULATED

    cat_opts = '\n'.join(
        f'<option value="{k}">{v}</option>'
        for k, v in (CATEGORIAS_PT.items() if RADAR_AVAILABLE else {}.items())
    )
    cat_opts = cat_opts or '<option value="insuficiencia_cardiaca">Insuficiência Cardíaca</option>'

    journal_opts = '\n'.join(
        f'<option value="{k}">{k}</option>'
        for k in (JOURNAL_MAP.keys() if RADAR_AVAILABLE else ['Circulation', 'J Am Coll Cardiol', 'N Engl J Med'])
    )

    _RADAR_HTML_POPULATED = _RADAR_HTML.replace('{CAT_OPTIONS}', cat_opts) \
                                        .replace('{JOURNAL_OPTIONS}', journal_opts) \
                                        .replace('{{', '{').replace('}}', '}')
    return _RADAR_HTML_POPULATED


# ─── Lógica de busca ──────────────────────────────────────────────────────────

_PT_TO_EN = {
    "dac": ["coronary", "cad", "ischemic"],
    "coronariana": ["coronary"], "coronaria": ["coronary"],
    "angina": ["angina", "coronary"],
    "infarto": ["myocardial infarction", "ami", "stemi", "nstemi"],
    "iam": ["myocardial infarction", "stemi", "nstemi"],
    "stemi": ["stemi", "myocardial infarction"],
    "nstemi": ["nstemi", "myocardial infarction"],
    "sca": ["acute coronary", "acs"],
    "icp": ["pci", "percutaneous coronary"],
    "angioplastia": ["pci", "angioplasty"],
    "stent": ["stent", "pci"],
    "revascularizacao": ["revascularization", "cabg", "bypass"],
    "ponte": ["bypass", "cabg"],
    "ic": ["heart failure"],
    "insuficiencia cardiaca": ["heart failure"],
    "insuficiência cardíaca": ["heart failure"],
    "hfref": ["heart failure", "reduced ejection"],
    "hfpef": ["heart failure", "preserved ejection"],
    "fa": ["atrial fibrillation"],
    "fibrilacao atrial": ["atrial fibrillation"],
    "fibrilação atrial": ["atrial fibrillation"],
    "arritmia": ["arrhythmia", "atrial fibrillation", "ventricular"],
    "ablacao": ["ablation"], "ablação": ["ablation"],
    "marcapasso": ["pacemaker"],
    "taquicardia": ["tachycardia", "arrhythmia"],
    "morte subita": ["sudden death", "sudden cardiac"],
    "has": ["hypertension"],
    "hipertensao": ["hypertension"], "hipertensão": ["hypertension"],
    "valvopatia": ["valve", "valvular"],
    "estenose aortica": ["aortic stenosis"],
    "tavi": ["transcatheter", "tavi", "tavr"],
    "tavr": ["transcatheter", "tavr"],
    "mitral": ["mitral"],
    "miocardiopatia hipertrofica": ["hypertrophic cardiomyopathy"],
    "miocardiopatia hipertrófica": ["hypertrophic cardiomyopathy"],
    "hcm": ["hypertrophic cardiomyopathy"],
    "mco": ["hypertrophic cardiomyopathy"],
    "amiloidose": ["amyloidosis"],
    "miocardiopatia": ["cardiomyopathy"],
    "colesterol": ["cholesterol", "lipid", "dyslipidemia"],
    "ldl": ["ldl", "cholesterol", "statin"],
    "estatina": ["statin"],
    "aterosclerose": ["atherosclerosis"],
    "triglicerides": ["triglyceride"],
    "diabetes": ["diabetes"], "dm": ["diabetes"],
    "sglt2": ["sglt2"], "glp1": ["glp-1", "glp1"],
    "tvp": ["deep vein thrombosis", "dvt"],
    "tep": ["pulmonary embolism"],
    "embolia pulmonar": ["pulmonary embolism"],
    "anticoagulacao": ["anticoagulation", "anticoagulant"],
    "noac": ["anticoagulant", "noac", "doac"],
    "warfarina": ["warfarin"],
    "aspirina": ["aspirin", "antiplatelet"],
    "clopidogrel": ["clopidogrel", "antiplatelet", "p2y12"],
    "ticagrelor": ["ticagrelor", "antiplatelet", "p2y12"],
    "prasugrel": ["prasugrel", "antiplatelet", "p2y12"],
    "antiplaquetario": ["antiplatelet", "p2y12", "clopidogrel", "ticagrelor", "prasugrel"],
    "antiplaquetários": ["antiplatelet", "p2y12", "clopidogrel", "ticagrelor", "prasugrel"],
    "antiplaquetarios": ["antiplatelet", "p2y12", "clopidogrel", "ticagrelor", "prasugrel"],
    "antiagregacao": ["antiplatelet", "antiplatelet therapy", "dapt"],
    "antiagregação": ["antiplatelet", "antiplatelet therapy", "dapt"],
    "dapt": ["dapt", "dual antiplatelet", "antiplatelet"],
    "sapt": ["single antiplatelet", "antiplatelet monotherapy"],
    "p2y12": ["p2y12", "antiplatelet", "clopidogrel", "ticagrelor", "prasugrel"],
    "avc": ["stroke"],
    "hap": ["pulmonary hypertension"],
    "hipertensao pulmonar": ["pulmonary hypertension"],
    "pericardite": ["pericarditis"],
    "miocardite": ["myocarditis"],
    "aorta": ["aorta", "aortic"],
    "idosos": ["elderly", "older adults"],
    "envelhecimento": ["aging", "elderly"],
    "renal": ["renal", "kidney"],
    "sacubitril": ["sacubitril", "neprilysin"],
    "colchicina": ["colchicine"],
    "inflamacao": ["inflammation", "inflammatory"],
    "pcr": ["c-reactive protein", "inflammation"],
    # Imagem cardiovascular
    "imagem": ["imaging", "magnetic", "resonance", "echocardiography", "tomography"],
    "ressonancia": ["magnetic resonance", "cmr", "cardiac mri"],
    "ressonância": ["magnetic resonance", "cmr", "cardiac mri"],
    "cmr": ["cardiac magnetic resonance", "cmr", "cardiac mri"],
    "mri": ["magnetic resonance", "cmr", "mri"],
    "stress cmr": ["stress cardiac magnetic", "cmr stress", "stress perfusion"],
    "stress cardiac": ["stress cardiac magnetic", "cmr stress", "stress perfusion"],
    "stress mri": ["stress cardiac magnetic", "cmr stress", "stress perfusion"],
    "perfusao": ["perfusion", "cmr", "stress"],
    "perfusão": ["perfusion", "cmr", "stress"],
    "ecocardiograma": ["echocardiography", "echocardiogram"],
    "ecocardiografia": ["echocardiography"],
    "eco": ["echocardiography", "echocardiogram"],
    "tc": ["computed tomography", "ct scan", "coronary cta"],
    "tomografia": ["computed tomography", "ct scan", "coronary cta"],
    "cta": ["coronary cta", "computed tomography"],
    "spect": ["spect", "nuclear", "myocardial perfusion"],
    "pet": ["pet scan", "positron emission", "nuclear"],
    "calcio": ["calcium score", "coronary calcium"],
    "cálcio": ["calcium score", "coronary calcium"],
    "strain": ["strain", "speckle tracking", "deformation"],
    "ivus": ["intravascular ultrasound", "ivus"],
    "oct": ["optical coherence", "oct"],
    "lge": ["late gadolinium enhancement", "gadolinium", "lge"],
    "realce tardio": ["late gadolinium enhancement", "gadolinium", "lge"],
    "gadolineo": ["gadolinium", "late gadolinium enhancement", "lge"],
    "gadolínio": ["gadolinium", "late gadolinium enhancement", "lge"],
    # Cardio-Oncologia
    "oncologia": ["cardiotoxicity", "cancer", "oncology cardiac"],
    "cardio oncologia": ["cardiotoxicity", "cancer cardiovascular", "oncology cardiac"],
    "cardiooncologia": ["cardiotoxicity", "cancer cardiovascular", "oncology cardiac"],
    "cardiotoxicidade": ["cardiotoxicity", "cancer cardiac"],
    "quimioterapia": ["chemotherapy", "cardiotoxicity"],
    "imunoterapia": ["checkpoint inhibitor", "immunotherapy cardiac"],
    "checkpoint": ["checkpoint inhibitor", "immunotherapy cardiac"],
    # Cardio-Genômica
    "genomica": ["genetics", "genomics", "polygenic"],
    "genômica": ["genetics", "genomics", "polygenic"],
    "genetica": ["genetics", "inherited", "hereditary"],
    "genética": ["genetics", "inherited", "hereditary"],
    "pcsk9": ["pcsk9", "familial hypercholesterolemia"],
    "hipercolesterolemia familiar": ["familial hypercholesterolemia", "pcsk9"],
    "poligenico": ["polygenic risk", "gwas"],
    "poligênico": ["polygenic risk", "gwas"],
    "rna terapia": ["rna therapy", "sirna", "inclisiran"],
    "inclisiran": ["inclisiran", "sirna", "pcsk9"],
    "crispr": ["crispr", "gene editing", "gene therapy"],
    # Imagem — termos adicionais
    "global longitudinal strain": ["global longitudinal strain", "gls", "strain"],
    "gls": ["global longitudinal strain", "gls", "strain"],
    "ffrct": ["ffrct", "ct fractional flow", "coronary cta"],
    "eco stress": ["stress echocardiography", "dobutamine stress"],
    "ecoestresse": ["stress echocardiography", "dobutamine stress"],
    "nuclear": ["nuclear cardiology", "myocardial perfusion", "spect", "pet"],
    "cintilografia": ["scintigraphy", "myocardial perfusion", "nuclear"],
    "angiografia": ["angiography", "coronary angiography", "cta"],
    "multimodalidade": ["multimodality imaging", "hybrid imaging"],
}

_TIPO_DB = {
    "original": "original", "revisao": "revisao",
    "metanalise": "metanalise", "guideline": "guideline",
}


def _expand(query: str) -> list[str]:
    q = query.lower().strip()
    terms = [q]
    if q in _PT_TO_EN:
        terms.extend(_PT_TO_EN[q])
    else:
        for k, v in _PT_TO_EN.items():
            if k in q or q in k:
                terms.extend(v)
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t); out.append(t)
    return out


def _clean_titulo(titulo: str | None, doc_id: str | None) -> str:
    """Extrai título limpo via pdf_filename → analysis.md."""
    if not titulo:
        titulo = ""
    # Remove emojis/símbolos no início
    titulo = re.sub(r'^[^\w\s]+\s*', '', titulo).strip()
    titulo = re.sub(r'^(Análise|Analysis)\s*(Completa|Clínica)?\s*[:\—–-]\s*', '', titulo, flags=re.IGNORECASE).strip()
    titulo = re.sub(r'\.pdf\s*$', '', titulo, flags=re.IGNORECASE).strip()

    _GENERIC = re.compile(
        r'^(Contextualiz|Análise|Analysis|'
        r'BLOCO|Ficha|Seção|Introdução|Background|Implicação|Take.Home|Conclusão)',
        re.IGNORECASE)
    # Títulos editoriais gerados pelo analisador — vagos, sem identificar o assunto
    _EDITORIAL_VAGO = re.compile(
        r'^(O que (muda|fazer|considerar|sabemos)|'
        r'Como (tratar|manejar|prescrever|avaliar)|'
        r'Quando (indicar|usar|tratar)|'
        r'Por que|'
        r'Vale a pena|'
        r'Estado da Arte|'
        r'Revisão|'
        r'\d+\.\d+\s*[—–-]\s*$|'   # ex: "2.1 —" sozinho (sem texto após)
        r'Dimensão\s*\|)',
        re.IGNORECASE)
    # Títulos que começam com ano (20XX ou 19XX) + espaço + texto longo são guidelines reais — nunca ruins
    _is_year_guideline = bool(re.match(r'^\d{4}\s+\S', titulo) and len(titulo.split()) >= 4)

    is_bad = bool(
        not _is_year_guideline and (
            re.match(r'^\d{4}-\d{2}', titulo)
            or (('-' in titulo or '_' in titulo) and ' ' not in titulo)
            or _GENERIC.match(titulo)
            or _EDITORIAL_VAGO.match(titulo)
            or len(titulo.split()) < 5  # menos de 5 palavras provavelmente vago
            or not titulo
        )
    )
    if not is_bad:
        return titulo[:120]

    folder = CORPUS_DIR / (doc_id or '')

    _SKIP = re.compile(
        r'^(Análise|Analysis|Contextualiz|Descrição|Principais|Interpretação|'
        r'Discussão|Conclusão|Take.Home|ETAPA|Resumo|BLOCO|Ficha|Seção|'
        r'Introdução|Background|Methods|Results|Contribuição|Limitaç|'
        r'Pontos|Perspectiv|Implicaç|Script|Pérola|Dados|Study|Clinical|'
        r'Nota\s+de\s+Aplicabilidade|Classificação|Endpoint|Justificativa|'
        r'Material\s+de|Observaç|Valor(es)?\s+de\s+Ref|A\d+\s*[—–-]|'
        r'\d+[A-Z]?\.\s*(Quem|Como|Quando|Por que|O que|Caso|Discuss|Conclu)|'  # "3A. Quem é essa paciente?"
        r'Quem é ess[ao] paciente|'   # título de seção de caso clínico
        r'Caso\s+Cl[íi]nico)',
        re.IGNORECASE)

    # 1. analysis.md — tabela Markdown (prioridade máxima, formato novo) + headings (formato antigo)
    try:
        md = (folder / "analysis.md").read_text(encoding='utf-8', errors='ignore')

        # 1a. Tabela Markdown: | **Título** | Real title |
        for pattern in [
            r'\|\s*\*\*Título(?:\s+do\s+artigo)?\*\*\s*\|\s*(.+?)\s*\|',
            r'\|\s*Título(?:\s+do\s+artigo)?\s*\|\s*(.+?)\s*\|',
        ]:
            tm = re.search(pattern, md, re.IGNORECASE)
            if tm:
                t = tm.group(1).strip()
                if len(t) > 10 and len(t.split()) >= 3 and not re.match(r'^[\-\?]+$', t):
                    return t[:120]

        # 1b. Headings reais (formato antigo, incluindo "ANÁLISE CRÍTICA: Título real")
        _ANALISE_PREFIX = re.compile(
            r'^ANÁLISE\s+CRÍTICA(?:\s+DE\s+[\w\s]+?)?\s*[:\-–—]\s*',
            re.IGNORECASE
        )
        for m in re.finditer(r'^#+\s+(.+)$', md, re.MULTILINE):
            c = m.group(1).strip()
            c = re.sub(r'^[^\w\s]*\s*', '', c).strip()
            c = re.sub(r'^(Análise|Analysis)\s*:\s*', '', c, flags=re.IGNORECASE).strip()
            c = re.sub(r'\.pdf\s*$', '', c, flags=re.IGNORECASE).strip()
            # Formato legado: "ANÁLISE CRÍTICA: Título real"
            m_pref = _ANALISE_PREFIX.match(c)
            if m_pref:
                c = c[m_pref.end():].strip()
            if not c or _SKIP.match(c): continue
            if _EDITORIAL_VAGO.match(c): continue  # ex: "O que muda na prescrição?"
            if re.match(r'^\d{4}-\d{2}', c): continue
            if '-' in c and '_' in c: continue
            if c.endswith(':'): continue
            alpha = [ch for ch in c if ch.isalpha()]
            if alpha and sum(ch.isupper() for ch in alpha) / len(alpha) > 0.75:
                continue
            if len(c.split()) >= 3:
                return c[:120]
    except Exception:
        pass

    # 2. analysis.json — source.titulo ou source.pdf_filename
    try:
        jp = folder / "analysis.json"
        if jp.exists():
            aj = json.loads(jp.read_text(encoding='utf-8', errors='ignore'))
            src = aj.get('source') or {}

            # 2a. source.titulo (campo mais limpo, sem extensão)
            fn = src.get('titulo', '') or src.get('pdf_filename', '')
            if fn and len(fn) > 15:
                clean = re.sub(r'^\d{4}-\d{2}-?(?:\d{2}-)?', '', fn)
                clean = re.sub(r'\s*\(\d+\)\s*\.pdf\s*$', '', clean, flags=re.IGNORECASE)
                clean = re.sub(r'\.pdf\s*$', '', clean, flags=re.IGNORECASE)
                clean = clean.replace('_', ' ').replace('-', ' ')
                # Remove prefixo de journal (sigla em maiúsculas: EHJ, JAMA, NEJM, JACC…)
                clean = re.sub(r'^[A-Z]{2,6}\s+', '', clean).strip()
                if len(clean.split()) >= 4:
                    return clean[:120]
    except Exception:
        pass

    return titulo.replace('-', ' ').replace('_', ' ').strip()[:120] or "Título não disponível"


def _asset(doc_id: str, *names: str) -> str | None:
    """Retorna o nome do primeiro asset existente na pasta assets/ do artigo."""
    folder = CORPUS_DIR / doc_id / "assets"
    for name in names:
        if (folder / name).exists():
            return name
    return None


def _resumo_from_disk(doc_id: str) -> str:
    """Lê o resumo/take-home da analysis.md quando resumo_markdown está vazio."""
    md_path = CORPUS_DIR / doc_id / "analysis.md"
    if not md_path.exists():
        return ""
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
        # Procurar seção Take-Home / Conclusão / Pontos-chave
        m = re.search(
            r'(?:Take.Home|Conclusão|Pontos.Chave|Pérolas)[^\n]*\n+([\s\S]{80,1500}?)(?=\n#+|\Z)',
            text, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:1200]
    except Exception:
        pass
    return ""


def buscar_api(q: str, tipo: str, nota: str, limite: str,
               data_inicio: str, data_fim: str, modo: str = "",
               revista: str = "") -> list[dict]:
    params = {
        "select": "doc_id,titulo,revista,nota_aplicabilidade,doenca_principal,"
                  "tipo_estudo,data_publicacao,doi,caminho_pasta,resumo_markdown,created_at",
        "nota_aplicabilidade": f"gte.{nota or 1}",
        "order": "created_at.desc,nota_aplicabilidade.desc" if modo == "recentes" else "nota_aplicabilidade.desc,data_publicacao.desc",
        "limit": str(min(int(limite or 50), 200)),
        # Excluir entradas de teste
        "titulo": "neq.teste",
        "doc_id": "not.like.pdf_%",
    }
    if tipo and tipo in _TIPO_DB:
        params["tipo_estudo"] = f"eq.{_TIPO_DB[tipo]}"
    # Filtro de data: created_at (adicionados) ou data_publicacao (publicados)
    date_col = "created_at" if modo == "recentes" else "data_publicacao"
    date_params = []
    if data_inicio:
        date_params.append((date_col, f"gte.{data_inicio}"))
    if data_fim:
        date_params.append((date_col, f"lte.{data_fim}"))

    # Construir filtros OR para revista e q (sem sobrescrever um ao outro)
    _REV_MAP = {
        "N Engl J Med": "nejm", "NEJM": "nejm",
        "JACC": "jacc", "EHJ": "ehj", "JAMA": "jama",
        "Circulation": "circulation", "Lancet": "lancet",
    }
    rev_or = []
    if revista:
        rev_key = _REV_MAP.get(revista, revista.lower())
        if rev_key == "nejm":
            rev_or = ["revista.ilike.%nejm%", "revista.ilike.%Engl%"]
        elif rev_key == "jacc":
            rev_or = ["revista.ilike.%jacc%"]
        elif rev_key == "jama":
            rev_or = ["revista.ilike.%jama%"]
        elif rev_key == "ehj":
            rev_or = ["revista.ilike.%ehj%", "revista.ilike.%EurHeart%"]
        elif rev_key == "circulation":
            rev_or = ["revista.ilike.%irculation%"]
        elif rev_key == "lancet":
            rev_or = ["revista.ilike.%ancet%"]
        else:
            s = revista.replace("'", "''")
            rev_or = [f"revista.ilike.%{s}%"]

    q_or = []
    if q:
        for t in _expand(q)[:5]:
            s = t.replace("'", "''")
            q_or.append(f"doenca_principal.ilike.%{s}%")
            q_or.append(f"titulo.ilike.%{s}%")
            q_or.append(f"resumo_markdown.ilike.%{s}%")

    # Combinar: se ambos, usar and(or(...),or(...)); se só um, usar or(...)
    if rev_or and q_or:
        params["and"] = f"(or({','.join(rev_or)}),or({','.join(q_or)}))"
    elif rev_or:
        params["or"] = f"({','.join(rev_or)})"
    elif q_or:
        params["or"] = f"({','.join(q_or)})"

    # Combinar params dict + date_params (lista de tuplas para permitir chave duplicada)
    all_params = list(params.items()) + date_params

    url = f"{SUPABASE_URL}/rest/v1/artigos"
    try:
        resp = req_lib.get(url, headers=_SB_HEADERS, params=all_params, timeout=15)
        artigos = resp.json() if resp.status_code == 200 else []
    except Exception:
        artigos = []

    out = []
    for a in artigos:
        doc_id = a.get("doc_id", "")
        titulo = _clean_titulo(a.get("titulo"), doc_id)
        resumo = a.get("resumo_markdown") or ""
        if not resumo:
            resumo = _resumo_from_disk(doc_id)
        resumo_html = _md_to_html(resumo) if resumo else ""
        img = _asset(doc_id, "visual_abstract.png", "infografico_portrait.png", "mindmap.png")
        out.append({
            "doc_id": doc_id,
            "titulo_display": titulo,
            "revista": a.get("revista") or "",
            "nota_aplicabilidade": a.get("nota_aplicabilidade"),
            "doenca_principal": a.get("doenca_principal") or "",
            "tipo_estudo": a.get("tipo_estudo") or "",
            "data_publicacao": a.get("data_publicacao") or "",
            "created_at": (a.get("created_at") or "")[:10],
            "doi": a.get("doi") or "",
            "resumo_markdown": resumo,
            "resumo_html": resumo_html,
            "tem_imagem": img is not None,
            "img_file": img or "",
        })
    return out


# ─── HTTP Handler ─────────────────────────────────────────────────────────────

def _configure_radar():
    """Configura o radar com as keys do .env (lazy, só uma vez)."""
    if not RADAR_AVAILABLE or _radar is None:
        raise RuntimeError("Módulo radar não disponível — pip install google-genai biopython")
    if getattr(_radar, '_configured', False):
        return
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")
    ncbi_key = os.getenv("NCBI_API_KEY", "")
    email = os.getenv("PUBMED_EMAIL", "edcastro77@gmail.com")
    if not gemini_key:
        raise RuntimeError("GEMINI_API_KEY ou GOOGLE_API_KEY não configurado no .env")
    _radar.configure(
        gemini_key=gemini_key,
        email=email,
        ncbi_key=ncbi_key,
        elevenlabs_key=elevenlabs_key,
    )


def _run_radar_job(job_id: str, tipo: str, params: dict):
    """Executa o radar em background thread."""
    def upd(msg):
        with _jobs_lock:
            _jobs[job_id]["msg"] = msg

    try:
        upd("Configurando APIs…")
        _configure_radar()

        if tipo == "pubmed":
            modo = params.get("modo", "categoria")
            dias = int(params.get("dias", 7))
            max_r = int(params.get("max_results", 50))

            upd("Buscando artigos no PubMed…")
            if modo == "keywords":
                kw_str = params.get("keywords", "cardiology")
                artigos = _radar.buscar_por_keywords(kw_str, dias=dias, max_results=max_r)
                contexto = f"Keywords: {kw_str} | Últimos {dias} dias"
            else:
                cat = params.get("categoria", "insuficiencia_cardiaca")
                artigos = _radar.buscar_por_categoria(cat, dias=dias, max_results=max_r)
                contexto = f"Categoria: {cat} | Últimos {dias} dias"

            if not artigos:
                with _jobs_lock:
                    _jobs[job_id] = {"status": "done", "result": {
                        "artigos": [], "triagem": "Nenhum artigo encontrado.", "script": ""
                    }}
                return

            upd(f"{len(artigos)} artigos — analisando triagem com Gemini…")
            triagem = _radar.analisar_triagem(artigos, contexto)

            upd("Gerando script de podcast…")
            script = _radar.gerar_script_pubmed(artigos, triagem, contexto)

            with _jobs_lock:
                _jobs[job_id] = {"status": "done", "result": {
                    "artigos": artigos,
                    "triagem": triagem,
                    "script": script,
                }}

        elif tipo == "numero":
            revista = params.get("revista", "Circulation")
            pubmed_journal = JOURNAL_MAP.get(revista, revista)

            upd(f"Detectando último número de {revista}…")
            vol, iss = _radar.get_ultimo_numero(pubmed_journal)
            if not vol:
                with _jobs_lock:
                    _jobs[job_id] = {"status": "error", "error": "Não foi possível detectar o último número no PubMed."}
                return

            upd(f"Vol {vol}, N {iss} — buscando artigos…")
            artigos = _radar.fetch_artigos_numero(pubmed_journal, vol, iss)

            if not artigos:
                with _jobs_lock:
                    _jobs[job_id] = {"status": "error", "error": "Nenhum artigo encontrado neste número."}
                return

            upd(f"{len(artigos)} artigos — gerando script com Gemini…")
            script = _radar.gerar_script_numero(pubmed_journal, vol, iss, artigos)

            with _jobs_lock:
                _jobs[job_id] = {"status": "done", "result": {
                    "artigos": artigos,
                    "journal": pubmed_journal,
                    "volume": vol,
                    "issue": iss,
                    "script": script,
                }}

        else:
            with _jobs_lock:
                _jobs[job_id] = {"status": "error", "error": f"Tipo desconhecido: {tipo}"}

    except Exception as e:
        with _jobs_lock:
            _jobs[job_id] = {"status": "error", "error": str(e)}


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silenciar logs

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        def get(k): return qs.get(k, [''])[0]

        if path == "/" or path == "/index.html":
            self._send(200, "text/html; charset=utf-8", HTML.encode())

        elif path == "/api/buscar":
            results = buscar_api(
                q=get('q'), tipo=get('tipo'), nota=get('nota') or '7',
                limite=get('limite') or '20',
                data_inicio=get('data_inicio'), data_fim=get('data_fim'),
                modo=get('modo'), revista=get('revista'),
            )
            body = json.dumps(results, ensure_ascii=False).encode('utf-8')
            self._send(200, "application/json; charset=utf-8", body)

        elif path.startswith("/img/"):
            # /img/{doc_id}  → infografico.png ou mindmap.png
            doc_id = path[5:].strip("/")
            img_name = _asset(doc_id, "visual_abstract.png", "infografico_portrait.png", "mindmap.png")
            if img_name:
                data = (CORPUS_DIR / doc_id / "assets" / img_name).read_bytes()
                self._send(200, "image/png", data)
            else:
                self._send(404, "text/plain", b"Imagem nao encontrada")

        elif path.startswith("/analise/"):
            # /analise/{doc_id}  → Markdown renderizado + botão Salvar PDF
            doc_id = path[9:].strip("/")
            md_path = CORPUS_DIR / doc_id / "analysis.md"
            if md_path.exists():
                md = md_path.read_text(encoding="utf-8", errors="ignore")

                # 1. Remove YAML frontmatter (--- ... ---)
                md = re.sub(r'^---\s*\n.*?\n---\s*\n?', '', md, flags=re.DOTALL)

                # 1b. Remove bloco de metadados markdown (# Análise: ... + campos bold + ---)
                # Gerado pelo ArticleAnalyzer antigo logo após o frontmatter YAML
                md = re.sub(
                    r'^#\s*(?:An[aá]lise|Analysis)\s*:.*?\n---\s*\n?',
                    '', md.lstrip(), flags=re.DOTALL | re.IGNORECASE)

                # 1c. Converte blocos ```...``` em texto plano formatado.
                # Os analysis.md novos têm um ### CABEÇALHO seguido de um bloco
                # com TÍTULO:, REVISTA:, TIPO: etc. dentro de ```.
                # Renderizar como <pre><code> produz fonte monospace — convertemos
                # cada linha "CHAVE: valor" em "**CHAVE:** valor" para markdown normal.
                def _codeblock_to_plain(m):
                    content = m.group(1)
                    linhas = []
                    for linha in content.split('\n'):
                        linha = linha.rstrip()
                        if not linha:
                            continue
                        # Se é "CHAVE: valor" → formata como bold
                        if ':' in linha:
                            chave, _, valor = linha.partition(':')
                            chave_stripped = chave.strip()
                            valor_stripped = valor.strip()
                            if chave_stripped and valor_stripped:
                                linhas.append(f"**{chave_stripped}:** {valor_stripped}  ")
                            elif chave_stripped:
                                linhas.append(f"**{chave_stripped}**  ")
                        else:
                            linhas.append(linha + "  ")
                    return '\n' + '\n'.join(linhas) + '\n'
                md = re.sub(r'```[a-zA-Z]*\n(.*?)```', _codeblock_to_plain, md, flags=re.DOTALL)

                # 2. Remove seção SCRIPT MAPA MENTAL e tudo abaixo dela
                cut = re.search(
                    r'\n#{1,3}[^\n]*(?:MAPA MENTAL|MindNode|SCRIPT PARA|FINE-ONE)[^\n]*',
                    md, re.IGNORECASE)
                if cut:
                    md = md[:cut.start()].rstrip()

                # 3. Obter metadados do Supabase (revista, data, nota, DOI)
                revista_art, data_pub_art, nota_art, doi_art, titulo_art = "", "", "", "", ""
                try:
                    r_sb = req_lib.get(
                        f"{SUPABASE_URL}/rest/v1/artigos",
                        headers=_SB_HEADERS,
                        params={"select": "titulo,revista,data_publicacao,nota_aplicabilidade,doi",
                                "doc_id": f"eq.{doc_id}"},
                        timeout=5)
                    if r_sb.status_code == 200 and r_sb.json():
                        row = r_sb.json()[0]
                        titulo_art  = _clean_titulo(row.get("titulo") or "", doc_id)
                        revista_art = row.get("revista") or ""
                        data_pub_art = row.get("data_publicacao") or ""
                        nota_art    = row.get("nota_aplicabilidade") or ""
                        doi_art     = row.get("doi") or ""
                except Exception:
                    pass

                # Formatar data
                _MESES = ['','Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
                def _fmt_date(d):
                    if not d: return ""
                    parts = str(d).split("-")
                    try:
                        return f"{int(parts[2])}/{_MESES[int(parts[1])]}/{parts[0]}"
                    except Exception:
                        return d
                data_fmt = _fmt_date(data_pub_art)

                # Montar linha de metadados para o cabeçalho
                meta_parts = []
                if revista_art and not revista_art.isdigit():
                    meta_parts.append(f"<strong>{revista_art}</strong>")
                if data_fmt:
                    meta_parts.append(data_fmt)
                if nota_art:
                    meta_parts.append(f"&#9733; {nota_art}/10")
                if doi_art:
                    safe_doi = doi_art.replace('"', '&quot;')
                    meta_parts.append(f'<a href="https://doi.org/{safe_doi}" target="_blank" style="color:#1a5f7a">{safe_doi}</a>')
                meta_line = " &nbsp;·&nbsp; ".join(meta_parts)

                md_json = json.dumps(md)
                body = f"""<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CardioDaily — Análise</title>
<style>
@media print{{
  .toolbar{{display:none!important}}
  body{{background:#fff}}
  .container{{max-width:100%;margin:0;padding:10mm 15mm;box-shadow:none;border-radius:0}}
  .art-meta{{border:none!important;background:none!important;padding:0!important;margin-bottom:18px}}
}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f8;color:#1e293b;margin:0}}
.toolbar{{position:sticky;top:0;z-index:100;background:#1a5f7a;color:#fff;padding:12px 24px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 8px rgba(0,0,0,.25)}}
.toolbar-title{{font-size:.95rem;font-weight:600;flex:1}}
.btn-pdf{{background:#fff;color:#1a5f7a;border:none;border-radius:6px;padding:8px 22px;font-size:.92rem;font-weight:700;cursor:pointer;transition:opacity .15s}}
.btn-pdf:hover{{opacity:.85}}
.container{{max-width:860px;margin:32px auto 60px;background:#fff;padding:44px 52px;border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.09)}}
.art-meta{{font-size:.88rem;color:#475569;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 16px;margin-bottom:28px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
h1{{font-size:1.5rem;color:#1a3a5c;line-height:1.35;margin-bottom:10px}}
h2{{font-size:1.12rem;color:#1a5f7a;margin:30px 0 10px;padding-bottom:6px;border-bottom:2px solid #e2e8f0}}
h3{{font-size:1rem;color:#334155;margin:20px 0 8px}}
p{{line-height:1.8;margin-bottom:12px}}
ul,ol{{padding-left:24px;margin-bottom:12px}}
li{{margin-bottom:6px;line-height:1.65}}
strong{{color:#1a3a5c}}
em{{color:#475569}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:.88rem}}
th{{background:#1a5f7a;color:#fff;padding:10px 14px;text-align:left;font-weight:600}}
td{{padding:9px 14px;border-bottom:1px solid #e2e8f0}}
tr:nth-child(even) td{{background:#f8fafc}}
code{{background:#f1f5f9;padding:2px 7px;border-radius:4px;font-size:.87em;font-family:'Menlo','Courier New',monospace}}
pre{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;margin:12px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:.88rem;line-height:1.7;color:#334155;white-space:pre-wrap;word-break:break-word;overflow-x:auto}}
pre code{{background:none;padding:0;border-radius:0;font-family:inherit;font-size:inherit;color:inherit}}
blockquote{{border-left:4px solid #1a5f7a;margin:16px 0;padding:10px 16px;background:#f0f7fb;border-radius:0 6px 6px 0;color:#334155}}
hr{{border:none;border-top:1px solid #e2e8f0;margin:24px 0}}
</style>
</head><body>
<div class="toolbar">
  <span class="toolbar-title">CardioDaily — Análise Completa</span>
  <button class="btn-pdf" onclick="window.print()">&#8659; Salvar PDF / Imprimir</button>
</div>
<div class="container">
  {f'<div class="art-meta">{meta_line}</div>' if meta_line else ''}
  <div id="content"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/marked@9/marked.min.js"></script>
<script>
const md = {md_json};
document.getElementById('content').innerHTML = marked.parse(md);
</script>
</body></html>""".encode("utf-8")
                self._send(200, "text/html; charset=utf-8", body)
            else:
                # analysis.md não existe localmente — mostrar dados do Supabase
                titulo_fb, revista_fb, nota_fb, doi_fb, resumo_fb = "", "", "", "", ""
                try:
                    r_fb = req_lib.get(
                        f"{SUPABASE_URL}/rest/v1/artigos",
                        headers=_SB_HEADERS,
                        params={"select": "titulo,revista,data_publicacao,nota_aplicabilidade,doi,resumo_markdown",
                                "doc_id": f"eq.{doc_id}"},
                        timeout=5)
                    if r_fb.status_code == 200 and r_fb.json():
                        row = r_fb.json()[0]
                        titulo_fb   = _clean_titulo(row.get("titulo") or "", doc_id)
                        revista_fb  = row.get("revista") or ""
                        nota_fb     = row.get("nota_aplicabilidade") or ""
                        doi_fb      = row.get("doi") or ""
                        resumo_fb   = row.get("resumo_markdown") or ""
                except Exception:
                    pass

                doi_link = f'<a href="https://doi.org/{doi_fb}" target="_blank">{doi_fb}</a>' if doi_fb else "—"
                resumo_html_fb = _md_to_html(resumo_fb) if resumo_fb else "<p style='color:#94a3b8;font-style:italic'>Resumo não disponível.</p>"

                body = f"""<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CardioDaily — {titulo_fb or doc_id}</title>
<style>
body{{font-family:'Segoe UI',sans-serif;max-width:820px;margin:40px auto;padding:0 20px;color:#1e293b;background:#f8fafc}}
.header{{background:#1a5f7a;color:white;border-radius:10px;padding:24px 28px;margin-bottom:24px}}
.header h1{{margin:0 0 8px;font-size:1.25rem;line-height:1.4}}
.meta{{font-size:.85rem;opacity:.85}}
.nota{{display:inline-block;background:rgba(255,255,255,.2);border-radius:6px;padding:2px 10px;font-weight:700;margin-right:8px}}
.content{{background:white;border-radius:10px;padding:24px 28px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.aviso{{background:#fef9c3;border-left:4px solid #f59e0b;padding:12px 16px;border-radius:6px;margin-bottom:20px;font-size:.88rem;color:#92400e}}
h2,h3{{color:#1a5f7a}}
</style></head><body>
<div class="header">
  <div class="meta"><span class="nota">&#9733; {nota_fb}/10</span>{revista_fb}</div>
  <h1>{titulo_fb or doc_id}</h1>
  <div class="meta">DOI: {doi_link}</div>
</div>
<div class="content">
  <div class="aviso">⚠️ Análise local não encontrada — este artigo está indexado no Supabase mas não foi analisado nesta máquina. Rode o pipeline para gerar a análise completa.</div>
  {resumo_html_fb}
</div>
</body></html>""".encode("utf-8")
                self._send(200, "text/html; charset=utf-8", body)

        elif path.startswith("/instagram/"):
            # /instagram/{doc_id}  → JSON com caption gerada
            doc_id = path[11:].strip("/")
            pub = _get_instagram_publisher()
            if pub:
                result = pub.generate_caption(doc_id)
            else:
                result = {"error": "Instagram publisher não disponível"}
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

        elif path == "/radar":
            body = _build_radar_html().encode("utf-8")
            self._send(200, "text/html; charset=utf-8", body)

        elif path.startswith("/api/radar/status/"):
            job_id = path[len("/api/radar/status/"):].strip("/")
            with _jobs_lock:
                job = _jobs.get(job_id)
            if not job:
                body = json.dumps({"status": "notfound"}).encode()
            else:
                body = json.dumps(job, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

        elif path.startswith("/api/radar/audio/"):
            filename = path[len("/api/radar/audio/"):].strip("/")
            audio_dir = _ROOT / "outputs" / "radar_audio"
            fpath = audio_dir / filename
            if fpath.exists() and fpath.suffix == ".mp3":
                self._send(200, "audio/mpeg", fpath.read_bytes())
            else:
                self._send(404, "text/plain", b"Audio nao encontrado")

        elif path == "/api/whatsapp/users":
            if not WHATSAPP_AVAILABLE:
                self._send(503, "application/json",
                           json.dumps({"error": "WhatsApp não disponível"}).encode())
                return
            try:
                users = get_all_users()
                body = json.dumps(users, ensure_ascii=False, default=str).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self._send(500, "application/json", body)

        elif path == "/api/whatsapp/status":
            connected = _zapi.is_connected() if WHATSAPP_AVAILABLE else False
            body = json.dumps({"connected": connected, "available": WHATSAPP_AVAILABLE}).encode()
            self._send(200, "application/json; charset=utf-8", body)

        else:
            self._send(404, "text/plain", b"404")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw)
        except Exception:
            data = {}

        if path == "/api/radar/iniciar":
            if not RADAR_AVAILABLE:
                body = json.dumps({"error": "Módulo radar não disponível"}).encode()
                self._send(503, "application/json", body)
                return

            job_id = str(uuid.uuid4())[:8]
            with _jobs_lock:
                _jobs[job_id] = {"status": "running", "msg": "Iniciando…"}

            tipo = data.get("tipo", "pubmed")
            threading.Thread(
                target=_run_radar_job,
                args=(job_id, tipo, data),
                daemon=True,
            ).start()

            body = json.dumps({"job_id": job_id}).encode()
            self._send(200, "application/json; charset=utf-8", body)

        elif path == "/api/radar/audio":
            if not RADAR_AVAILABLE:
                body = json.dumps({"error": "Módulo radar não disponível"}).encode()
                self._send(503, "application/json", body)
                return

            script = data.get("script", "")
            nome = data.get("nome", "radar")
            if not script:
                body = json.dumps({"error": "Script vazio"}).encode()
                self._send(400, "application/json", body)
                return

            try:
                _configure_radar()
                ts = time.strftime("%Y%m%d_%H%M%S")
                audio_dir = _ROOT / "outputs" / "radar_audio"
                audio_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{nome}_{ts}.mp3"
                fpath = audio_dir / filename
                ok = _radar.gerar_audio(script, str(fpath))
                if ok:
                    body = json.dumps({"filename": filename}).encode()
                    self._send(200, "application/json; charset=utf-8", body)
                else:
                    body = json.dumps({"error": "Falha ao gerar áudio"}).encode()
                    self._send(500, "application/json", body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self._send(500, "application/json", body)

        # ── WhatsApp Webhook (recebido do Z-API via n8n) ───────────────────────
        elif path == "/api/whatsapp/webhook":
            if not WHATSAPP_AVAILABLE:
                self._send(503, "application/json",
                           json.dumps({"error": "WhatsApp não disponível"}).encode())
                return
            try:
                result = handle_webhook(data)
                body = json.dumps(result).encode()
                self._send(200, "application/json; charset=utf-8", body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self._send(500, "application/json", body)

        # ── WhatsApp: adicionar usuário manualmente ───────────────────────────
        elif path == "/api/whatsapp/users":
            if not WHATSAPP_AVAILABLE:
                self._send(503, "application/json",
                           json.dumps({"error": "WhatsApp não disponível"}).encode())
                return
            try:
                phone = data.get("phone", "").strip()
                nome  = data.get("nome", "")
                if not phone:
                    self._send(400, "application/json",
                               json.dumps({"error": "phone obrigatório"}).encode())
                    return
                user = create_user(phone, nome)
                # Envia boas-vindas via Z-API se estiver conectado
                if _zapi.is_connected():
                    from whatsapp.user_manager import menu_temas_text
                    _zapi.send_text(phone,
                        "👋 Bem-vindo ao *CardioDaily*!\n\nPara configurar seus temas 👇")
                    _zapi.send_text(phone, menu_temas_text())
                body = json.dumps({"ok": True, "user": user}).encode()
                self._send(200, "application/json; charset=utf-8", body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self._send(500, "application/json", body)

        # ── WhatsApp: batch send (chamado pelo cron n8n às 7h) ───────────────
        elif path == "/api/whatsapp/batch_send":
            if not WHATSAPP_AVAILABLE:
                self._send(503, "application/json",
                           json.dumps({"error": "WhatsApp não disponível"}).encode())
                return
            try:
                dry_run = data.get("dry_run", False)
                phone_filter = data.get("phone")
                def _run():
                    from whatsapp.daily_sender import run
                    run(phone_filter=phone_filter, dry_run=dry_run)
                threading.Thread(target=_run, daemon=True).start()
                body = json.dumps({"ok": True, "msg": "Envio iniciado em background"}).encode()
                self._send(200, "application/json; charset=utf-8", body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self._send(500, "application/json", body)

        # ── Radar Diário (chamado pelo cron n8n às 8h) ───────────────────────
        elif path == "/api/radar/diario":
            if not RADAR_AVAILABLE:
                self._send(503, "application/json",
                           json.dumps({"error": "Módulo radar não disponível"}).encode())
                return
            try:
                categoria = data.get("categoria")  # opcional — omitir para usar rotação do dia
                dry_run   = data.get("dry_run", False)
                def _run_diario():
                    import subprocess
                    cmd = [sys.executable, str(_ROOT / "scripts" / "run_radar_diario.py")]
                    if categoria:
                        cmd += ["--categoria", categoria]
                    if dry_run:
                        cmd += ["--dry-run"]
                    subprocess.run(cmd, cwd=str(_ROOT))
                threading.Thread(target=_run_diario, daemon=True).start()
                body = json.dumps({"ok": True, "msg": "Radar diário iniciado em background"}).encode()
                self._send(200, "application/json; charset=utf-8", body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self._send(500, "application/json", body)

        else:
            self._send(404, "text/plain", b"404")

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL ou SUPABASE_KEY não configurados em .env")
        sys.exit(1)

    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"

    print(f"\n{'='*50}")
    print(f"🏥 CardioDaily — Biblioteca Web")
    print(f"   Acesse: {url}")
    print(f"   Ctrl+C para parar")
    print(f"{'='*50}\n")

    # Abrir browser após 0.8s
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✅ Servidor encerrado.")


if __name__ == "__main__":
    main()
