from flask import Flask, request, render_template_string, jsonify
import os
import json

try:
    import openai
except Exception:
    openai = None

# Newer Gemini SDK: google-genai (`pip install google-genai`)
try:
    from google import genai
except Exception:
    genai = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    import yaml  # For agents.yaml
except Exception:
    yaml = None

app = Flask(__name__)

# In-memory API keys store (do not expose values)
API_KEYS = {
    "openai": os.getenv("OPENAI_API_KEY") or "",
    "gemini": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "",
}

PAINTERS = [
    "Van Gogh", "Monet", "Picasso", "Da Vinci", "Rembrandt", "Matisse", "Kandinsky",
    "Hokusai", "Yayoi Kusama", "Frida Kahlo", "Salvador Dali", "Rothko", "Pollock",
    "Chagall", "Basquiat", "Haring", "Georgia O'Keeffe", "Turner", "Seurat", "Escher"
]

# Default prompts (user can edit these in the UI)
SUBMISSION_PROMPT_DEFAULT = (
    "Organize the following 510(k) submission into structured markdown with "
    "headings, summary, and checklist."
)

CHECKLIST_PROMPT_DEFAULT = (
    "Organize the following checklist into a clear markdown checklist grouped by sections."
)

REVIEW_PROMPT_DEFAULT = (
    "Using the checklist below, evaluate the submission and produce a structured review "
    "report with findings, recommended actions, and missing documents."
)

NOTE_PROMPT_DEFAULT = (
    "Organize the following note into clear markdown with sections, bullet points, and a "
    "keyword summary. Highlight important keywords inline using HTML spans like "
    "<span style=\"color:coral\">keyword</span> so they appear in coral color."
)

# Agents loaded from agents.yaml
AGENTS = []


def load_agents():
    """Load agents from agents.yaml if present."""
    global AGENTS
    AGENTS = []
    if yaml is None:
        return
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "agents.yaml")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
        if isinstance(data, dict):
            # Allow a dict with "agents": [...]
            data = data.get("agents", [])
        if not isinstance(data, list):
            return
        for idx, ag in enumerate(data):
            if not isinstance(ag, dict):
                continue
            agent_id = str(ag.get("id", idx))
            AGENTS.append(
                {
                    "id": agent_id,
                    "name": ag.get("name", f"Agent {agent_id}"),
                    "description": ag.get("description", ""),
                    "prompt": ag.get("prompt", ""),
                    "default_model": ag.get("default_model", "gpt-4o-mini"),
                    "max_tokens": int(ag.get("max_tokens", 12000)),
                }
            )
    except Exception:
        # Fail silently; agents will be empty
        AGENTS = []


load_agents()

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>WOW 510(k) Assistant</title>
  <style>
    :root{
      --bg:#fff;
      --fg:#111;
      --accent:#2563eb;
      --accent-soft:rgba(37,99,235,0.12);
      --border-soft:rgba(15,23,42,0.08);
    }
    [data-theme='dark']{
      --bg:#020617;
      --fg:#e5e7eb;
      --accent:#60a5fa;
      --accent-soft:rgba(96,165,250,0.25);
      --border-soft:rgba(148,163,184,0.25);
    }
    body{
      background:
        radial-gradient(circle at top left,rgba(37,99,235,0.12),transparent),
        radial-gradient(circle at bottom right,rgba(14,165,233,0.10),transparent),
        var(--bg);
      color:var(--fg);
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
      margin:0;
    }
    .app{display:flex;min-height:100vh;backdrop-filter:blur(10px)}
    .sidebar{
      width:340px;
      padding:16px;
      border-right:1px solid var(--border-soft);
      box-sizing:border-box;
      background:linear-gradient(to bottom,rgba(15,23,42,0.04),transparent);
    }
    .main{flex:1;padding:18px 24px;box-sizing:border-box}
    h1{margin:4px 0 6px;font-size:1.4rem}
    h2{margin:4px 0 6px;font-size:1.1rem}
    h3{margin:0;font-size:1rem}
    label{display:block;margin-top:8px;font-weight:600;font-size:0.9rem}
    textarea{
      width:100%;
      min-height:80px;
      padding:8px 10px;
      border-radius:8px;
      border:1px solid var(--border-soft);
      background:rgba(15,23,42,0.01);
      color:var(--fg);
      box-sizing:border-box;
      font-size:0.9rem;
    }
    textarea:focus{
      outline:none;
      border-color:var(--accent);
      box-shadow:0 0 0 1px var(--accent-soft);
    }
    input[type="file"]{margin-top:6px}
    input[type="password"],input[type="text"],input[type="number"]{
      width:100%;
      padding:6px 8px;
      border-radius:6px;
      border:1px solid var(--border-soft);
      background:rgba(15,23,42,0.01);
      color:var(--fg);
      box-sizing:border-box;
      font-size:0.85rem;
    }
    input:focus{
      outline:none;
      border-color:var(--accent);
      box-shadow:0 0 0 1px var(--accent-soft);
    }
    select{
      padding:6px 8px;
      border-radius:6px;
      border:1px solid var(--border-soft);
      background:rgba(15,23,42,0.02);
      color:var(--fg);
      font-size:0.85rem;
    }
    .row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
    .btn{
      padding:7px 11px;
      border-radius:999px;
      border:0;
      background:linear-gradient(to right,var(--accent),#1d4ed8);
      color:#f9fafb;
      cursor:pointer;
      font-size:0.85rem;
      display:inline-flex;
      align-items:center;
      gap:6px;
      box-shadow:0 10px 18px rgba(37,99,235,0.28);
      transition:transform 0.08s ease,box-shadow 0.08s ease,background 0.12s ease;
    }
    .btn.secondary{
      background:rgba(15,23,42,0.08);
      box-shadow:none;
      color:var(--fg);
    }
    [data-theme='dark'] .btn.secondary{
      background:rgba(15,23,42,0.6);
    }
    .btn:hover{
      transform:translateY(-1px);
      box-shadow:0 14px 22px rgba(37,99,235,0.35);
    }
    .btn.secondary:hover{box-shadow:0 6px 14px rgba(15,23,42,0.35)}
    .muted{opacity:0.75;font-size:0.85rem}
    .small{font-size:0.8rem}
    .painter{
      display:inline-flex;
      align-items:center;
      gap:6px;
      padding:6px 9px;
      margin:3px;
      border-radius:999px;
      background:rgba(15,23,42,0.04);
      cursor:pointer;
      border:1px solid transparent;
      font-size:0.78rem;
      user-select:none;
      transition:border 0.12s ease,background 0.12s ease,transform 0.08s ease;
    }
    [data-theme='dark'] .painter{background:rgba(15,23,42,0.7)}
    .painter:hover{transform:translateY(-1px);background:var(--accent-soft)}
    .painter[data-sel]{border-color:var(--accent);background:var(--accent-soft)}
    .painter-swatch{
      width:10px;
      height:10px;
      border-radius:999px;
      background:conic-gradient(from 180deg at 50% 50%,#f97316,#eab308,#22c55e,#06b6d4,#3b82f6,#a855f7,#ec4899,#f97316);
    }
    .result{
      white-space:pre-wrap;
      background:rgba(15,23,42,0.02);
      padding:12px;
      border-radius:10px;
      margin-top:4px;
      border:1px solid var(--border-soft);
      font-size:0.88rem;
      max-height:420px;
      overflow:auto;
    }
    .result-edit{
      resize:vertical;
      font-family:ui-monospace,Menlo,Monaco,Consolas,monospace;
      min-height:120px;
    }
    .result-container{margin-top:8px}
    .result-header{
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:4px;
    }
    .result-tabs{
      display:flex;
      gap:6px;
      font-size:0.78rem;
    }
    .result-tab{
      padding:3px 9px;
      border-radius:999px;
      border:1px solid var(--border-soft);
      background:transparent;
      cursor:pointer;
      font-size:0.78rem;
    }
    .result-tab.active{
      border-color:var(--accent);
      background:var(--accent-soft);
    }
    .result-actions{
      display:flex;
      gap:4px;
      align-items:center;
    }
    .chip-btn{
      padding:3px 8px;
      border-radius:999px;
      border:1px solid var(--border-soft);
      background:rgba(15,23,42,0.02);
      font-size:0.75rem;
      cursor:pointer;
    }
    .chip-btn:hover{
      border-color:var(--accent);
      background:var(--accent-soft);
    }
    .flex-between{display:flex;justify-content:space-between;align-items:center}
    .pill{
      padding:3px 8px;
      border-radius:999px;
      border:1px solid var(--border-soft);
      font-size:0.7rem;
      text-transform:uppercase;
      letter-spacing:0.05em;
      opacity:0.8;
    }
    .wow-header-meta{
      display:flex;
      gap:8px;
      align-items:center;
      font-size:0.75rem;
      margin-bottom:6px;
    }
    hr{
      border:0;
      border-top:1px dashed var(--border-soft);
      margin:14px 0;
    }
    .status-bar{
      display:flex;
      align-items:center;
      gap:8px;
      padding:6px 8px;
      border-radius:999px;
      border:1px solid var(--border-soft);
      background:rgba(15,23,42,0.02);
      margin-top:6px;
    }
    .status-dot{
      width:9px;
      height:9px;
      border-radius:999px;
      background:#22c55e;
      box-shadow:0 0 0 0 rgba(34,197,94,0.45);
      transition:background 0.18s ease,box-shadow 0.18s ease;
    }
    .status-bar.busy .status-dot{
      background:#f97316;
      animation:pulse 1.1s infinite;
    }
    .status-bar.error .status-dot{
      background:#ef4444;
      box-shadow:0 0 0 0 rgba(239,68,68,0.6);
      animation:none;
    }
    .status-bar.ok .status-dot{
      background:#22c55e;
      animation:none;
    }
    .status-label{font-size:0.8rem}
    @keyframes pulse{
      0%{box-shadow:0 0 0 0 rgba(248,150,73,0.55);}
      70%{box-shadow:0 0 0 8px rgba(248,150,73,0);}
      100%{box-shadow:0 0 0 0 rgba(248,150,73,0);}
    }
    .advanced-row label{font-weight:500;font-size:0.8rem;margin-top:4px}
    .prompt-textarea{
      min-height:70px;
      font-size:0.8rem;
    }
    .section-caption{
      font-size:0.8rem;
      margin-bottom:4px;
    }
  </style>
  <!-- Client-side Markdown renderer for Preview -->
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body data-theme="light">
  <div class="app">
    <div class="sidebar">
      <div class="flex-between">
        <h3>WOW Control Deck</h3>
        <div class="wow-header-meta">
          <span class="pill">v1.1 • LLM</span>
        </div>
      </div>
      <div class="row" style="margin-top:6px">
        <div>
          <span class="small muted">Theme</span><br>
          <select id="themeSel">
            <option>light</option>
            <option>dark</option>
          </select>
        </div>
        <div>
          <span class="small muted">Language</span><br>
          <select id="langSel">
            <option value="en">English</option>
            <option value="zh">繁體中文</option>
          </select>
        </div>
      </div>

      <label style="margin-top:12px;">API Keys (stored server-side)</label>
      <div class="muted small">Keys from environment will be used and remain hidden.</div>

      {% if has_openai_env %}
        <input id="openaiKey" type="hidden">
        <div class="muted small">OpenAI key detected in environment (no need to enter).</div>
      {% else %}
        <input id="openaiKey" placeholder="OpenAI API Key" style="margin-top:6px" type="password">
      {% endif %}

      {% if has_gemini_env %}
        <input id="geminiKey" type="hidden">
        <div class="muted small">Gemini key detected in environment (no need to enter).</div>
      {% else %}
        <input id="geminiKey" placeholder="Gemini (Google) API Key" style="margin-top:6px" type="password">
      {% endif %}

      <div class="row">
        <button class="btn" id="saveKeys">Save Keys</button>
        {% if not has_openai_env or not has_gemini_env %}
          <button id="toggleShow" class="btn secondary">Hide/Show</button>
        {% endif %}
      </div>

      <hr>

      <label>Painter Styles (WOW Magic Wheel)</label>
      <div id="painters"></div>
      <div class="row">
        <button class="btn secondary" id="jackpot">🎰 Jackpot</button>
        <button class="btn secondary" id="applyStyle">Apply Style</button>
      </div>

      <hr>

      <label>LLM Connectivity Test</label>
      <div class="row">
        <select id="testModelSel" style="flex:1;min-width:150px"></select>
      </div>
      <input id="testPrompt" type="text" class="small" placeholder="Short test prompt (e.g. Say OK)" style="margin-top:4px;">
      <div class="row">
        <button class="btn secondary" id="testLLM">Test LLM Call</button>
      </div>

      <hr>

      <div id="statusBar" class="muted small status-bar ok">
        <span class="status-dot"></span>
        <span class="status-label">Status: <span id="statusText">Idle</span></span>
      </div>
    </div>

    <div class="main">
      <div class="flex-between">
        <div>
          <div class="small muted">WOW 510(k) Assistant</div>
          <h1>Review & Checklist Co‑Pilot</h1>
        </div>
      </div>

      <!-- SUBMISSION TRANSFORM -->
      <div>
        <label>Submission Prompt (editable)</label>
        <textarea id="subPrompt" class="prompt-textarea">{{ sub_prompt_default }}</textarea>

        <label>Paste Submission (text/markdown) or upload PDF</label>
        <textarea id="submissionText" placeholder="Paste submission here..."></textarea>
        <input type="file" id="submissionFile">

        <div class="row advanced-row">
          <div style="width:140px">
            <label for="subMaxTokens" class="small">Max tokens</label>
            <input id="subMaxTokens" type="number" min="256" max="32000" value="12000">
          </div>
        </div>

        <div class="row">
          <select id="modelSel"></select>
          <button class="btn" id="transformSub">Transform Submission</button>
        </div>

        <div class="result-container">
          <div class="result-header">
            <div class="result-tabs">
              <button class="result-tab active" data-target="submission" data-mode="edit">Edit (markdown/text)</button>
              <button class="result-tab" data-target="submission" data-mode="preview">Preview</button>
            </div>
            <div class="result-actions small">
              <button type="button" class="chip-btn" onclick="copyResult('submission')">Copy</button>
              <button type="button" class="chip-btn" onclick="downloadResult('submission','md')">.md</button>
              <button type="button" class="chip-btn" onclick="downloadResult('submission','txt')">.txt</button>
            </div>
          </div>
          <textarea id="submissionResultEdit" class="result result-edit"></textarea>
          <div id="submissionResultPreview" class="result" style="display:none;"></div>
        </div>
      </div>

      <hr>

      <!-- CHECKLIST TRANSFORM -->
      <div>
        <label>Checklist Prompt (editable)</label>
        <textarea id="chkPrompt" class="prompt-textarea">{{ checklist_prompt_default }}</textarea>

        <label>Paste Checklist or upload CSV</label>
        <textarea id="checklistText" placeholder="Paste checklist here..."></textarea>
        <input type="file" id="checklistFile">

        <div class="row advanced-row">
          <div style="width:140px">
            <label for="chkMaxTokens" class="small">Max tokens</label>
            <input id="chkMaxTokens" type="number" min="256" max="32000" value="12000">
          </div>
        </div>

        <div class="row">
          <select id="modelSel2"></select>
          <button class="btn" id="transformChecklist">Transform Checklist</button>
        </div>

        <div class="result-container">
          <div class="result-header">
            <div class="result-tabs">
              <button class="result-tab active" data-target="checklist" data-mode="edit">Edit (markdown/text)</button>
              <button class="result-tab" data-target="checklist" data-mode="preview">Preview</button>
            </div>
            <div class="result-actions small">
              <button type="button" class="chip-btn" onclick="copyResult('checklist')">Copy</button>
              <button type="button" class="chip-btn" onclick="downloadResult('checklist','md')">.md</button>
              <button type="button" class="chip-btn" onclick="downloadResult('checklist','txt')">.txt</button>
            </div>
          </div>
          <textarea id="checklistResultEdit" class="result result-edit"></textarea>
          <div id="checklistResultPreview" class="result" style="display:none;"></div>
        </div>
      </div>

      <hr>

      <!-- REVIEW -->
      <div>
        <label>Review Prompt (editable)</label>
        <textarea id="revPrompt" class="prompt-textarea">{{ review_prompt_default }}</textarea>

        <label>Run Review</label>
        <textarea id="reviewSubmission" placeholder="Paste organized submission markdown (or leave blank to reuse transformed submission above)"></textarea>
        <textarea id="reviewChecklist" placeholder="Paste organized checklist markdown (or leave blank to reuse transformed checklist above)"></textarea>

        <div class="row advanced-row">
          <div style="width:140px">
            <label for="revMaxTokens" class="small">Max tokens</label>
            <input id="revMaxTokens" type="number" min="256" max="32000" value="12000">
          </div>
        </div>

        <div class="row">
          <select id="modelSel3"></select>
          <button class="btn" id="runReview">Run Review</button>
        </div>

        <div class="result-container">
          <div class="result-header">
            <div class="result-tabs">
              <button class="result-tab active" data-target="review" data-mode="edit">Edit (markdown/text)</button>
              <button class="result-tab" data-target="review" data-mode="preview">Preview</button>
            </div>
            <div class="result-actions small">
              <button type="button" class="chip-btn" onclick="copyResult('review')">Copy</button>
              <button type="button" class="chip-btn" onclick="downloadResult('review','md')">.md</button>
              <button type="button" class="chip-btn" onclick="downloadResult('review','txt')">.txt</button>
            </div>
          </div>
          <textarea id="reviewResultEdit" class="result result-edit"></textarea>
          <div id="reviewResultPreview" class="result" style="display:none;"></div>
        </div>
      </div>

      <hr>

      <!-- AI NOTE KEEPER -->
      <div>
        <h2>AI Note Keeper</h2>
        <div class="section-caption muted">
          Paste any note or markdown. The assistant will organize it and highlight keywords in coral color.
        </div>

        <label>Note Organizer Prompt (editable)</label>
        <textarea id="notePrompt" class="prompt-textarea">{{ note_prompt_default }}</textarea>

        <label>Paste Note (text/markdown)</label>
        <textarea id="noteInput" placeholder="Paste your note here..."></textarea>

        <div class="row advanced-row">
          <div style="width:140px">
            <label for="noteMaxTokens" class="small">Max tokens</label>
            <input id="noteMaxTokens" type="number" min="256" max="32000" value="4000">
          </div>
        </div>

        <div class="row">
          <select id="noteModelSel"></select>
          <button class="btn" id="transformNote">Organize Note</button>
        </div>

        <div class="result-container">
          <div class="result-header">
            <div class="result-tabs">
              <button class="result-tab active" data-target="note" data-mode="edit">Edit (markdown/text)</button>
              <button class="result-tab" data-target="note" data-mode="preview">Preview</button>
            </div>
            <div class="result-actions small">
              <button type="button" class="chip-btn" onclick="copyResult('note')">Copy</button>
              <button type="button" class="chip-btn" onclick="downloadResult('note','md')">.md</button>
              <button type="button" class="chip-btn" onclick="downloadResult('note','txt')">.txt</button>
            </div>
          </div>
          <textarea id="noteResultEdit" class="result result-edit"></textarea>
          <div id="noteResultPreview" class="result" style="display:none;"></div>
        </div>

        <hr>

        <!-- Follow-up prompt on note -->
        <div>
          <label>Custom Prompt on This Note</label>
          <textarea id="noteFollowupPrompt" class="prompt-textarea" placeholder="e.g. Extract action items and deadlines from this note."></textarea>

          <div class="row advanced-row">
            <div style="width:140px">
              <label for="noteFollowupMaxTokens" class="small">Max tokens</label>
              <input id="noteFollowupMaxTokens" type="number" min="256" max="32000" value="2000">
            </div>
          </div>

          <div class="row">
            <select id="noteFollowupModelSel"></select>
            <button class="btn secondary" id="runNotePrompt">Run Prompt on Note</button>
          </div>
        </div>

        <hr>

        <!-- Agents on note -->
        <div>
          <h3>Agents on Note</h3>
          {% if agents %}
            <div class="section-caption muted">
              Select an agent from agents.yaml to run on the current note. You can tweak its prompt and model before execution.
            </div>
            <label>Agent</label>
            <div class="row">
              <select id="agentSel" style="flex:1;min-width:200px"></select>
            </div>
            <div id="agentDescription" class="small muted" style="margin-top:4px;"></div>

            <label>Agent Prompt (editable)</label>
            <textarea id="agentPrompt" class="prompt-textarea"></textarea>

            <div class="row advanced-row">
              <div style="width:140px">
                <label for="agentMaxTokens" class="small">Max tokens</label>
                <input id="agentMaxTokens" type="number" min="256" max="32000" value="2000">
              </div>
            </div>

            <div class="row">
              <select id="agentModelSel"></select>
              <button class="btn secondary" id="runAgent">Run Agent on Note</button>
            </div>

            <div class="result-container">
              <div class="result-header">
                <div class="result-tabs">
                  <button class="result-tab active" data-target="noteAgent" data-mode="edit">Edit (markdown/text)</button>
                  <button class="result-tab" data-target="noteAgent" data-mode="preview">Preview</button>
                </div>
                <div class="result-actions small">
                  <button type="button" class="chip-btn" onclick="copyResult('noteAgent')">Copy</button>
                  <button type="button" class="chip-btn" onclick="downloadResult('noteAgent','md')">.md</button>
                  <button type="button" class="chip-btn" onclick="downloadResult('noteAgent','txt')">.txt</button>
                </div>
              </div>
              <textarea id="noteAgentResultEdit" class="result result-edit"></textarea>
              <div id="noteAgentResultPreview" class="result" style="display:none;"></div>
            </div>
          {% else %}
            <div class="muted small">
              No agents.yaml found or no agents configured. Add an agents.yaml file next to app.py to enable agents.
            </div>
          {% endif %}
        </div>
      </div>
    </div>
  </div>

  <script>
    const painters = {{ painters_json|safe }};
    const models = {{ models_json|safe }};
    const agents = {{ agents_json|safe }};

    // Painter wheel
    const painterDiv = document.getElementById('painters');
    painters.forEach(p => {
      const d = document.createElement('div');
      d.className = 'painter';
      const sw = document.createElement('span');
      sw.className = 'painter-swatch';
      const txt = document.createElement('span');
      txt.textContent = p;
      d.appendChild(sw);
      d.appendChild(txt);
      d.onclick = () => {
        document.querySelectorAll('.painter').forEach(x => {x.style.border='1px solid transparent'; delete x.dataset.sel;});
        d.style.border='1px solid var(--accent)';
        d.dataset.sel='1';
      };
      painterDiv.appendChild(d);
    });

    document.getElementById('jackpot').onclick = () => {
      const items = document.querySelectorAll('.painter');
      if (!items.length) return;
      items.forEach(x => {x.style.border='1px solid transparent'; delete x.dataset.sel;});
      const idx = Math.floor(Math.random() * items.length);
      items[idx].click();
    };

    document.getElementById('applyStyle').onclick = () => {
      const sel = document.querySelector('.painter[data-sel]');
      alert('Style applied: ' + (sel ? sel.textContent.trim() : 'Default'));
    };

    // Status indicator
    function setStatus(text, mode){
      // mode: 'idle' | 'busy' | 'ok' | 'success' | 'error'
      const label = document.getElementById('statusText');
      const bar = document.getElementById('statusBar');
      if (label) label.textContent = text;
      if (!bar) return;
      bar.classList.remove('busy','ok','error');
      if (mode === 'busy'){
        bar.classList.add('busy');
      } else if (mode === 'error'){
        bar.classList.add('error');
      } else {
        bar.classList.add('ok');
      }
    }

    // API keys save / toggle
    document.getElementById('saveKeys').onclick = async () => {
      try{
        setStatus('Saving API keys…', 'busy');
        const openaiEl = document.getElementById('openaiKey');
        const geminiEl = document.getElementById('geminiKey');
        const openaiKey = openaiEl ? openaiEl.value : '';
        const geminiKey = geminiEl ? geminiEl.value : '';
        const res = await fetch('/set_api_keys', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({openai:openaiKey, gemini:geminiKey})
        });
        const data = await res.json();
        setStatus(data.status || 'Keys saved', 'ok');
      } catch(e){
        setStatus('Error saving keys', 'error');
      }
    };

    const toggleShowBtn = document.getElementById('toggleShow');
    if (toggleShowBtn){
      toggleShowBtn.onclick = () => {
        const a = document.getElementById('openaiKey');
        const b = document.getElementById('geminiKey');
        if (!a && !b) return;
        const isHidden = (a && a.type === 'password') || (b && b.type === 'password');
        const newType = isHidden ? 'text' : 'password';
        if (a && a.type !== 'hidden') a.type = newType;
        if (b && b.type !== 'hidden') b.type = newType;
      };
    }

    // Generic POST helper
    async function postFormData(url, form){
      const res = await fetch(url,{method:'POST', body:form});
      return res.json();
    }

    // Result editor/preview wiring
    function updatePreview(kind){
      const srcEl = document.getElementById(kind + 'ResultEdit');
      const prevEl = document.getElementById(kind + 'ResultPreview');
      if (!srcEl || !prevEl) return;
      const text = srcEl.value || '';
      if (window.marked){
        prevEl.innerHTML = marked.parse(text, { breaks: true });
      } else {
        prevEl.textContent = text;
      }
    }

    function setupResultTabs(kind){
      const tabs = document.querySelectorAll('.result-tab[data-target="' + kind + '"]');
      const editEl = document.getElementById(kind + 'ResultEdit');
      const prevEl = document.getElementById(kind + 'ResultPreview');
      if (!tabs.length || !editEl || !prevEl) return;

      tabs.forEach(tab => {
        tab.onclick = () => {
          const mode = tab.getAttribute('data-mode');
          tabs.forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          if (mode === 'preview'){
            editEl.style.display = 'none';
            prevEl.style.display = 'block';
            updatePreview(kind);
          } else {
            editEl.style.display = 'block';
            prevEl.style.display = 'none';
          }
        };
      });

      // live preview updates
      editEl.addEventListener('input', () => {
        const activeTab = document.querySelector('.result-tab[data-target="' + kind + '"].active');
        if (activeTab && activeTab.getAttribute('data-mode') === 'preview'){
          updatePreview(kind);
        }
      });
    }

    ['submission','checklist','review','note','noteAgent'].forEach(setupResultTabs);

    // Copy & Download helpers
    function getResultText(kind){
      const el = document.getElementById(kind + 'ResultEdit');
      if (!el) return '';
      return el.value || el.textContent || '';
    }

    window.copyResult = async function(kind){
      const text = getResultText(kind);
      if (!text){
        setStatus('Nothing to copy for ' + kind, 'error');
        return;
      }
      try{
        if (navigator.clipboard && navigator.clipboard.writeText){
          await navigator.clipboard.writeText(text);
        } else {
          // Fallback for some environments
          const ta = document.createElement('textarea');
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        }
        setStatus('Copied ' + kind + ' result to clipboard', 'ok');
      }catch(e){
        setStatus('Copy failed for ' + kind, 'error');
      }
    };

    window.downloadResult = function(kind, ext){
      const text = getResultText(kind);
      if (!text){
        setStatus('Nothing to download for ' + kind, 'error');
        return;
      }
      const blob = new Blob([text], {type: ext === 'md' ? 'text/markdown' : 'text/plain'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = kind + '_result.' + ext;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setStatus('Downloaded ' + kind + ' result as .' + ext, 'ok');
    };

    // Populate model selects & test model select
    (function(){
      const ids = [
        'modelSel','modelSel2','modelSel3',
        'testModelSel','noteModelSel','noteFollowupModelSel','agentModelSel'
      ];
      ids.forEach(id => {
        const select = document.getElementById(id);
        if (!select) return;
        models.forEach(m => {
          const o = document.createElement('option');
          o.value = m; o.textContent = m;
          select.appendChild(o);
        });
      });
    })();

    // Populate agents UI
    (function(){
      const sel = document.getElementById('agentSel');
      const descEl = document.getElementById('agentDescription');
      const promptEl = document.getElementById('agentPrompt');
      const modelSel = document.getElementById('agentModelSel');
      const maxTokEl = document.getElementById('agentMaxTokens');
      if (!sel || !agents || !agents.length) return;

      agents.forEach(a => {
        const o = document.createElement('option');
        o.value = a.id;
        o.textContent = a.name;
        sel.appendChild(o);
      });

      function applyAgent(agent){
        if (!agent) return;
        if (descEl) descEl.textContent = agent.description || '';
        if (promptEl) promptEl.value = agent.prompt || '';
        if (modelSel){
          const hasOption = Array.from(modelSel.options).some(opt => opt.value === agent.default_model);
          if (hasOption){
            modelSel.value = agent.default_model;
          }
        }
        if (maxTokEl){
          maxTokEl.value = agent.max_tokens || 2000;
        }
      }

      sel.onchange = () => {
        const id = sel.value;
        const agent = agents.find(a => a.id === id);
        applyAgent(agent);
      };

      // Initialize with first agent
      if (agents.length > 0){
        sel.value = agents[0].id;
        applyAgent(agents[0]);
      }
    })();

    // Theme/lang
    document.getElementById('themeSel').onchange = function(){
      document.body.setAttribute('data-theme', this.value);
    };
    document.getElementById('langSel').onchange = function(){
      alert('Language switcher placeholder – UI text will adapt in a future update.');
    };

    // Transform Submission
    document.getElementById('transformSub').onclick = async () => {
      const model = document.getElementById('modelSel').value;
      setStatus('Transforming submission with ' + model + ' …', 'busy');
      try{
        const text = document.getElementById('submissionText').value;
        const file = document.getElementById('submissionFile').files[0];
        const prompt = document.getElementById('subPrompt').value || '';
        const maxTokens = document.getElementById('subMaxTokens').value || '12000';

        const form = new FormData();
        form.append('pasted', text);
        form.append('model', model);
        form.append('user_prompt', prompt);
        form.append('max_tokens', maxTokens);
        if (file) form.append('file', file);

        const r = await postFormData('/transform_submission', form);
        const out = r.result || r.error || '';
        document.getElementById('submissionResultEdit').value = out;
        updatePreview('submission');

        if (r.error){
          setStatus('Error: ' + r.error, 'error');
        }else{
          setStatus('Done (submission transformed)', 'ok');
        }
      }catch(e){
        setStatus('Error during submission transform', 'error');
      }
    };

    // Transform Checklist
    document.getElementById('transformChecklist').onclick = async () => {
      const model = document.getElementById('modelSel2').value;
      setStatus('Transforming checklist with ' + model + ' …', 'busy');
      try{
        const text = document.getElementById('checklistText').value;
        const file = document.getElementById('checklistFile').files[0];
        const prompt = document.getElementById('chkPrompt').value || '';
        const maxTokens = document.getElementById('chkMaxTokens').value || '12000';

        const form = new FormData();
        form.append('pasted', text);
        form.append('model', model);
        form.append('user_prompt', prompt);
        form.append('max_tokens', maxTokens);
        if (file) form.append('file', file);

        const r = await postFormData('/transform_checklist', form);
        const out = r.result || r.error || '';
        document.getElementById('checklistResultEdit').value = out;
        updatePreview('checklist');

        if (r.error){
          setStatus('Error: ' + r.error, 'error');
        }else{
          setStatus('Done (checklist transformed)', 'ok');
        }
      }catch(e){
        setStatus('Error during checklist transform', 'error');
      }
    };

    // Run Review
    document.getElementById('runReview').onclick = async () => {
      const model = document.getElementById('modelSel3').value;
      setStatus('Running review with ' + model + ' …', 'busy');
      try{
        const submission = document.getElementById('reviewSubmission').value
          || document.getElementById('submissionResultEdit').value;
        const checklist = document.getElementById('reviewChecklist').value
          || document.getElementById('checklistResultEdit').value;
        const prompt = document.getElementById('revPrompt').value || '';
        const maxTokens = document.getElementById('revMaxTokens').value || '12000';

        const form = new FormData();
        form.append('submission', submission);
        form.append('checklist', checklist);
        form.append('model', model);
        form.append('user_prompt', prompt);
        form.append('max_tokens', maxTokens);

        const r = await postFormData('/run_review', form);
        const out = r.result || r.error || '';
        document.getElementById('reviewResultEdit').value = out;
        updatePreview('review');

        if (r.error){
          setStatus('Error: ' + r.error, 'error');
        }else{
          setStatus('Done (review completed)', 'ok');
        }
      }catch(e){
        setStatus('Error during review run', 'error');
      }
    };

    // Note Keeper: organize note
    document.getElementById('transformNote').onclick = async () => {
      const model = document.getElementById('noteModelSel').value;
      setStatus('Organizing note with ' + model + ' …', 'busy');
      try{
        const text = document.getElementById('noteInput').value;
        const prompt = document.getElementById('notePrompt').value || '';
        const maxTokens = document.getElementById('noteMaxTokens').value || '4000';

        const form = new FormData();
        form.append('note', text);
        form.append('model', model);
        form.append('user_prompt', prompt);
        form.append('max_tokens', maxTokens);

        const r = await postFormData('/transform_note', form);
        const out = r.result || r.error || '';
        document.getElementById('noteResultEdit').value = out;
        updatePreview('note');

        if (r.error){
          setStatus('Error: ' + r.error, 'error');
        }else{
          setStatus('Done (note organized)', 'ok');
        }
      }catch(e){
        setStatus('Error during note organization', 'error');
      }
    };

    // Note Keeper: run custom prompt on note
    document.getElementById('runNotePrompt').onclick = async () => {
      const model = document.getElementById('noteFollowupModelSel').value;
      setStatus('Running custom prompt on note with ' + model + ' …', 'busy');
      try{
        const note = document.getElementById('noteResultEdit').value
          || document.getElementById('noteInput').value;
        const prompt = document.getElementById('noteFollowupPrompt').value || '';
        const maxTokens = document.getElementById('noteFollowupMaxTokens').value || '2000';

        const form = new FormData();
        form.append('note', note);
        form.append('model', model);
        form.append('user_prompt', prompt);
        form.append('max_tokens', maxTokens);

        const r = await postFormData('/run_note_prompt', form);
        const out = r.result || r.error || '';
        // Update the main note with new content so the prompt is effectively "kept" on the note
        document.getElementById('noteResultEdit').value = out;
        updatePreview('note');

        if (r.error){
          setStatus('Error: ' + r.error, 'error');
        }else{
          setStatus('Done (custom prompt applied to note)', 'ok');
        }
      }catch(e){
        setStatus('Error while running prompt on note', 'error');
      }
    };

    // Agents: run agent on note
    const runAgentBtn = document.getElementById('runAgent');
    if (runAgentBtn){
      runAgentBtn.onclick = async () => {
        const model = document.getElementById('agentModelSel').value;
        const agentId = document.getElementById('agentSel').value;
        setStatus('Running agent ' + agentId + ' with ' + model + ' …', 'busy');
        try{
          const note = document.getElementById('noteResultEdit').value
            || document.getElementById('noteInput').value;
          const prompt = document.getElementById('agentPrompt').value || '';
          const maxTokens = document.getElementById('agentMaxTokens').value || '2000';

          const form = new FormData();
          form.append('note', note);
          form.append('model', model);
          form.append('agent_id', agentId);
          form.append('user_prompt', prompt);
          form.append('max_tokens', maxTokens);

          const r = await postFormData('/run_note_agent', form);
          const out = r.result || r.error || '';
          document.getElementById('noteAgentResultEdit').value = out;
          updatePreview('noteAgent');

          if (r.error){
            setStatus('Error: ' + r.error, 'error');
          }else{
            setStatus('Done (agent executed on note)', 'ok');
          }
        }catch(e){
          setStatus('Error while running agent on note', 'error');
        }
      };
    }

    // Test LLM Call
    document.getElementById('testLLM').onclick = async () => {
      const model = document.getElementById('testModelSel').value;
      const prompt = document.getElementById('testPrompt').value || 'Say OK if you received this.';
      setStatus('Testing LLM model ' + model + ' …', 'busy');
      try{
        const form = new FormData();
        form.append('model', model);
        form.append('prompt', prompt);
        const r = await postFormData('/test_llm', form);
        if (r.status === 'ok'){
          setStatus('LLM test OK for ' + model, 'ok');
          alert('LLM test succeeded. Model replied: ' + (r.preview || 'OK'));
        } else {
          setStatus('LLM test failed: ' + (r.error || 'unknown error'), 'error');
          alert('LLM test failed: ' + (r.error || 'unknown error'));
        }
      }catch(e){
        setStatus('LLM test error: ' + e, 'error');
      }
    };
  </script>
</body>
</html>
"""


def extract_text_from_pdf_stream(stream):
    """Extract text from a PDF file-like object using PyMuPDF."""
    if fitz is None:
        return ""
    doc = fitz.open(stream=stream.read(), filetype="pdf")
    pages = [p.get_text() for p in doc]
    return "\n\n".join(pages)


def call_llm(model: str, prompt: str, max_tokens: int = 12000, temperature: float = 0.2) -> dict:
    """
    Generic LLM caller.
    - OpenAI: uses new-style client if available, falls back to ChatCompletion.
    - Gemini: uses newer google-genai Client with models.generate_content.
    """
    provider = "openai" if model.startswith("gpt") else ("gemini" if model.startswith("gemini") else "openai")

    # OPENAI
    if provider == "openai":
        if openai is None:
            return {"error": "openai package not installed on server. Install the openai package."}
        key = API_KEYS.get("openai") or os.getenv("OPENAI_API_KEY")
        if not key:
            return {"error": "OpenAI API key not set."}
        os.environ["OPENAI_API_KEY"] = key

        try:
            # New-style OpenAI client
            if hasattr(openai, "OpenAI"):
                try:
                    client = openai.OpenAI(api_key=key)
                except Exception:
                    client = openai.OpenAI()

                # Chat completions (preferred)
                if hasattr(client, "chat") and hasattr(client.chat, "completions") and hasattr(
                    client.chat.completions, "create"
                ):
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    try:
                        msg = resp.choices[0].message
                        if isinstance(msg, dict):
                            text = msg.get("content")
                        else:
                            text = getattr(msg, "content", None)
                    except Exception:
                        text = getattr(resp.choices[0], "text", None)
                    if not text:
                        text = getattr(resp, "output_text", None) or str(resp)
                    return {"text": text}

                # Responses API fallback
                if hasattr(client, "responses") and hasattr(client.responses, "create"):
                    resp = client.responses.create(
                        model=model,
                        input=prompt,
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                    )
                    text = getattr(resp, "output_text", None)
                    if not text:
                        parts = []
                        try:
                            for item in getattr(resp, "output", []) or []:
                                content = getattr(item, "content", None) or (
                                    item.get("content") if isinstance(item, dict) else None
                                )
                                if isinstance(content, list):
                                    for c in content:
                                        if isinstance(c, dict) and "text" in c:
                                            parts.append(c["text"])
                                        elif hasattr(c, "text"):
                                            parts.append(c.text)
                                elif isinstance(content, str):
                                    parts.append(content)
                        except Exception:
                            pass
                        if parts:
                            text = "\n".join(parts)
                    if not text:
                        text = str(resp)
                    return {"text": text}

            # Legacy ChatCompletion API
            if hasattr(openai, "ChatCompletion"):
                openai.api_key = key
                resp = openai.ChatCompletion.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                choice = resp.choices[0]
                if hasattr(choice, "message"):
                    return {"text": choice.message["content"]}
                return {"text": getattr(choice, "text", "")}

            return {
                "error": (
                    "Installed openai package does not expose a supported API. "
                    "Consider running `OPENAI migrate` or aligning SDK version."
                )
            }
        except Exception as e:
            msg = str(e)
            if "ChatCompletion" in msg or "chat" in msg.lower():
                msg += " — If you recently upgraded the OpenAI SDK, try: OPENAI migrate"
            return {"error": msg}

    # GEMINI (google-genai)
    if provider == "gemini":
        if genai is None:
            return {
                "error": (
                    "google-genai (google.genai) not installed. "
                    "Install with: pip install google-genai"
                )
            }
        key = API_KEYS.get("gemini") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            return {"error": "Gemini API key not set."}

        # Newer practice: explicit Client with API key, using models.generate_content
        try:
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "temperature": float(temperature),
                    "max_output_tokens": int(max_tokens),
                },
            )

            text = getattr(resp, "text", None)
            if not text:
                text = getattr(resp, "output_text", None)
            if not text:
                text = str(resp)
            return {"text": text}

        except Exception as e:
            return {"error": f"Gemini call failed: {e}"}

    return {"error": "Unsupported model/provider."}


@app.route("/")
def index():
    # Available models (extend as needed)
    model_opts = ["gpt-4o-mini", "gpt-4.1-mini", "gemini-2.5-flash", "gemini-3-flash-preview"]

    has_openai_env = bool(os.getenv("OPENAI_API_KEY"))
    has_gemini_env = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    return render_template_string(
        INDEX_HTML,
        painters_json=json.dumps(PAINTERS),
        models_json=json.dumps(model_opts),
        agents_json=json.dumps(AGENTS),
        agents=AGENTS,
        has_openai_env=has_openai_env,
        has_gemini_env=has_gemini_env,
        sub_prompt_default=SUBMISSION_PROMPT_DEFAULT,
        checklist_prompt_default=CHECKLIST_PROMPT_DEFAULT,
        review_prompt_default=REVIEW_PROMPT_DEFAULT,
        note_prompt_default=NOTE_PROMPT_DEFAULT,
    )


@app.route("/set_api_keys", methods=["POST"])
def set_api_keys():
    data = request.get_json() or {}
    if "openai" in data and data["openai"]:
        API_KEYS["openai"] = data["openai"]
    if "gemini" in data and data["gemini"]:
        API_KEYS["gemini"] = data["gemini"]
    return jsonify({"status": "saved"})


@app.route("/transform_submission", methods=["POST"])
def transform_submission():
    pasted = request.form.get("pasted", "")
    model = request.form.get("model") or "gpt-4o-mini"
    max_tokens = int(request.form.get("max_tokens") or 12000)
    user_prompt = (request.form.get("user_prompt") or "").strip() or SUBMISSION_PROMPT_DEFAULT

    f = request.files.get("file")
    text = pasted
    if f:
        fname = f.filename.lower()
        if fname.endswith(".pdf"):
            text = extract_text_from_pdf_stream(f.stream)
        else:
            try:
                text = f.stream.read().decode("utf-8")
            except Exception:
                text = ""

    prompt = user_prompt + "\n\nSource:\n" + text[:3000]

    res = call_llm(model, prompt, max_tokens=max_tokens)
    if "text" in res:
        return jsonify({"result": res["text"]})
    return jsonify({"error": res.get("error", "unknown")}), 500


@app.route("/transform_checklist", methods=["POST"])
def transform_checklist():
    pasted = request.form.get("pasted", "")
    model = request.form.get("model") or "gpt-4o-mini"
    max_tokens = int(request.form.get("max_tokens") or 12000)
    user_prompt = (request.form.get("user_prompt") or "").strip() or CHECKLIST_PROMPT_DEFAULT

    f = request.files.get("file")
    text = pasted
    if f:
        try:
            text = f.stream.read().decode("utf-8")
        except Exception:
            text = ""

    prompt = user_prompt + "\n\nSource:\n" + text[:3000]

    res = call_llm(model, prompt, max_tokens=max_tokens)
    if "text" in res:
        return jsonify({"result": res["text"]})
    return jsonify({"error": res.get("error", "unknown")}), 500


@app.route("/run_review", methods=["POST"])
def run_review():
    submission = request.form.get("submission", "")
    checklist = request.form.get("checklist", "")
    model = request.form.get("model") or "gpt-4o-mini"
    max_tokens = int(request.form.get("max_tokens") or 12000)
    user_prompt = (request.form.get("user_prompt") or "").strip() or REVIEW_PROMPT_DEFAULT

    prompt = (
        user_prompt
        + "\n\nCHECKLIST:\n"
        + checklist[:2000]
        + "\n\nSUBMISSION:\n"
        + submission[:8000]
    )

    res = call_llm(model, prompt, max_tokens=max_tokens)
    if "text" in res:
        return jsonify({"result": res["text"]})
    return jsonify({"error": res.get("error", "unknown")}), 500


@app.route("/transform_note", methods=["POST"])
def transform_note():
    note = request.form.get("note", "")
    model = request.form.get("model") or "gpt-4o-mini"
    max_tokens = int(request.form.get("max_tokens") or 4000)
    user_prompt = (request.form.get("user_prompt") or "").strip() or NOTE_PROMPT_DEFAULT

    prompt = user_prompt + "\n\nRAW NOTE:\n" + note[:4000]

    res = call_llm(model, prompt, max_tokens=max_tokens)
    if "text" in res:
        return jsonify({"result": res["text"]})
    return jsonify({"error": res.get("error", "unknown")}), 500


@app.route("/run_note_prompt", methods=["POST"])
def run_note_prompt():
    note = request.form.get("note", "")
    model = request.form.get("model") or "gpt-4o-mini"
    max_tokens = int(request.form.get("max_tokens") or 2000)
    user_prompt = (request.form.get("user_prompt") or "").strip()
    if not user_prompt:
        return jsonify({"error": "Custom prompt on note is empty."}), 400

    prompt = user_prompt + "\n\nNOTE CONTENT:\n" + note[:6000]

    res = call_llm(model, prompt, max_tokens=max_tokens)
    if "text" in res:
        return jsonify({"result": res["text"]})
    return jsonify({"error": res.get("error", "unknown")}), 500


@app.route("/run_note_agent", methods=["POST"])
def run_note_agent():
    note = request.form.get("note", "")
    model = request.form.get("model") or "gpt-4o-mini"
    max_tokens = int(request.form.get("max_tokens") or 2000)
    agent_id = request.form.get("agent_id") or ""
    user_prompt = (request.form.get("user_prompt") or "").strip()

    agent = next((a for a in AGENTS if str(a["id"]) == str(agent_id)), None)
    if not agent:
        return jsonify({"error": f"Agent {agent_id} not found."}), 400

    base_prompt = agent.get("prompt", "")
    combined_prompt = base_prompt
    if user_prompt:
        combined_prompt += "\n\nAdditional instructions:\n" + user_prompt

    prompt = combined_prompt + "\n\nNOTE CONTENT:\n" + note[:6000]

    res = call_llm(model, prompt, max_tokens=max_tokens)
    if "text" in res:
        return jsonify({"result": res["text"]})
    return jsonify({"error": res.get("error", "unknown")}), 500


@app.route("/test_llm", methods=["POST"])
def test_llm():
    model = request.form.get("model") or "gpt-4o-mini"
    prompt = request.form.get("prompt") or "Say OK if you received this."
    test_prompt = f"Connection test. {prompt}"
    res = call_llm(model, test_prompt, max_tokens=32, temperature=0.0)
    if "text" in res:
        text = res["text"] or ""
        preview = text.strip().splitlines()[0] if text.strip() else ""
        return jsonify({"status": "ok", "preview": preview})
    return jsonify({"status": "error", "error": res.get("error", "unknown")}), 500


if __name__ == "__main__":
    # For local debugging; in production use a proper WSGI server
    app.run(host="0.0.0.0", port=5000, debug=True)
