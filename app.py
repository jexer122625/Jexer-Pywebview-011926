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
      width:320px;
      padding:16px;
      border-right:1px solid var(--border-soft);
      box-sizing:border-box;
      background:linear-gradient(to bottom,rgba(15,23,42,0.04),transparent);
    }
    .main{flex:1;padding:18px 24px;box-sizing:border-box}
    h1{margin:4px 0 6px;font-size:1.4rem}
    h3{margin:0;font-size:1rem}
    label{display:block;margin-top:8px;font-weight:600;font-size:0.9rem}
    textarea{
      width:100%;
      min-height:120px;
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
      margin-top:8px;
      border:1px solid var(--border-soft);
      font-size:0.88rem;
      max-height:420px;
      overflow:auto;
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
    .status-bar.active .status-dot{
      background:#f97316;
      animation:pulse 1.1s infinite;
    }
    .status-label{font-size:0.8rem}
    @keyframes pulse{
      0%{box-shadow:0 0 0 0 rgba(248,150,73,0.55);}
      70%{box-shadow:0 0 0 8px rgba(248,150,73,0);}
      100%{box-shadow:0 0 0 0 rgba(248,150,73,0);}
    }
    .advanced-row label{font-weight:500;font-size:0.8rem;margin-top:4px}
  </style>
</head>
<body data-theme="light">
  <div class="app">
    <div class="sidebar">
      <div class="flex-between">
        <h3>WOW Control Deck</h3>
        <div class="wow-header-meta">
          <span class="pill">v1.0 • LLM</span>
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
        <!-- Hidden field so JS can still reference; no key value shown -->
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

      <div id="statusBar" class="muted small status-bar">
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

      <div>
        <label>Paste Submission (text/markdown) or upload PDF</label>
        <textarea id="submissionText" placeholder="Paste submission here..."></textarea>
        <input type="file" id="submissionFile">

        <div class="row advanced-row">
          <div style="flex:1;min-width:150px">
            <label for="subPrompt" class="small">Extra instructions (optional)</label>
            <input id="subPrompt" type="text" placeholder="e.g. Emphasize safety & risk sections">
          </div>
          <div style="width:120px">
            <label for="subMaxTokens" class="small">Max tokens</label>
            <input id="subMaxTokens" type="number" min="256" max="32000" value="12000">
          </div>
        </div>

        <div class="row">
          <select id="modelSel"></select>
          <button class="btn" id="transformSub">Transform Submission</button>
        </div>
        <div id="submissionResult" class="result"></div>
      </div>

      <hr>

      <div>
        <label>Paste Checklist or upload CSV</label>
        <textarea id="checklistText" placeholder="Paste checklist here..."></textarea>
        <input type="file" id="checklistFile">

        <div class="row advanced-row">
          <div style="flex:1;min-width:150px">
            <label for="chkPrompt" class="small">Extra instructions (optional)</label>
            <input id="chkPrompt" type="text" placeholder="e.g. Group items by risk level">
          </div>
          <div style="width:120px">
            <label for="chkMaxTokens" class="small">Max tokens</label>
            <input id="chkMaxTokens" type="number" min="256" max="32000" value="12000">
          </div>
        </div>

        <div class="row">
          <select id="modelSel2"></select>
          <button class="btn" id="transformChecklist">Transform Checklist</button>
        </div>
        <div id="checklistResult" class="result"></div>
      </div>

      <hr>

      <div>
        <label>Run Review</label>
        <textarea id="reviewSubmission" placeholder="Paste organized submission markdown (or leave blank to reuse above)"></textarea>
        <textarea id="reviewChecklist" placeholder="Paste organized checklist markdown (or leave blank to reuse above)"></textarea>

        <div class="row advanced-row">
          <div style="flex:1;min-width:150px">
            <label for="revPrompt" class="small">Extra instructions (optional)</label>
            <input id="revPrompt" type="text" placeholder="e.g. Focus on clinical evidence gaps">
          </div>
          <div style="width:120px">
            <label for="revMaxTokens" class="small">Max tokens</label>
            <input id="revMaxTokens" type="number" min="256" max="32000" value="12000">
          </div>
        </div>

        <div class="row">
          <select id="modelSel3"></select>
          <button class="btn" id="runReview">Run Review</button>
        </div>
        <div id="reviewResult" class="result"></div>
      </div>
    </div>
  </div>

  <script>
    const painters = {{ painters_json|safe }};
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

    function setStatus(text, isActive=false){
      const label = document.getElementById('statusText');
      const bar = document.getElementById('statusBar');
      if (label) label.textContent = text;
      if (!bar) return;
      if (isActive){
        bar.classList.add('active');
      } else {
        bar.classList.remove('active');
      }
    }

    document.getElementById('saveKeys').onclick = async () => {
      try{
        setStatus('Saving API keys…', true);
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
        setStatus(data.status || 'Saved', false);
      } catch(e){
        setStatus('Error saving keys', false);
      }
    };

    const toggleShowBtn = document.getElementById('toggleShow');
    if (toggleShowBtn){
      toggleShowBtn.onclick = () => {
        const a = document.getElementById('openaiKey');
        const b = document.getElementById('geminiKey');
        if (!a && !b) return;
        const current = (a && a.type === 'password') || (b && b.type === 'password');
        const newType = current ? 'text' : 'password';
        if (a && a.type !== 'hidden') a.type = newType;
        if (b && b.type !== 'hidden') b.type = newType;
      };
    }

    async function postFormData(url, form){
      const res = await fetch(url,{method:'POST', body:form});
      return res.json();
    }

    document.getElementById('transformSub').onclick = async () => {
      const model = document.getElementById('modelSel').value;
      setStatus('Transforming submission with ' + model + ' …', true);
      try{
        const text = document.getElementById('submissionText').value;
        const file = document.getElementById('submissionFile').files[0];
        const extra = document.getElementById('subPrompt').value || '';
        const maxTokens = document.getElementById('subMaxTokens').value || '12000';

        const form = new FormData();
        form.append('pasted', text);
        form.append('model', model);
        form.append('extra_prompt', extra);
        form.append('max_tokens', maxTokens);
        if (file) form.append('file', file);

        const r = await postFormData('/transform_submission', form);
        document.getElementById('submissionResult').textContent = r.result || r.error || '';
        if (r.error){
          setStatus('Error: ' + r.error, false);
        }else{
          setStatus('Done (submission transformed)', false);
        }
      }catch(e){
        setStatus('Error during submission transform', false);
      }
    };

    document.getElementById('transformChecklist').onclick = async () => {
      const model = document.getElementById('modelSel2').value;
      setStatus('Transforming checklist with ' + model + ' …', true);
      try{
        const text = document.getElementById('checklistText').value;
        const file = document.getElementById('checklistFile').files[0];
        const extra = document.getElementById('chkPrompt').value || '';
        const maxTokens = document.getElementById('chkMaxTokens').value || '12000';

        const form = new FormData();
        form.append('pasted', text);
        form.append('model', model);
        form.append('extra_prompt', extra);
        form.append('max_tokens', maxTokens);
        if (file) form.append('file', file);

        const r = await postFormData('/transform_checklist', form);
        document.getElementById('checklistResult').textContent = r.result || r.error || '';
        if (r.error){
          setStatus('Error: ' + r.error, false);
        }else{
          setStatus('Done (checklist transformed)', false);
        }
      }catch(e){
        setStatus('Error during checklist transform', false);
      }
    };

    document.getElementById('runReview').onclick = async () => {
      const model = document.getElementById('modelSel3').value;
      setStatus('Running review with ' + model + ' …', true);
      try{
        const submission = document.getElementById('reviewSubmission').value
          || document.getElementById('submissionResult').textContent;
        const checklist = document.getElementById('reviewChecklist').value
          || document.getElementById('checklistResult').textContent;
        const extra = document.getElementById('revPrompt').value || '';
        const maxTokens = document.getElementById('revMaxTokens').value || '12000';

        const form = new FormData();
        form.append('submission', submission);
        form.append('checklist', checklist);
        form.append('model', model);
        form.append('extra_prompt', extra);
        form.append('max_tokens', maxTokens);

        const r = await postFormData('/run_review', form);
        document.getElementById('reviewResult').textContent = r.result || r.error || '';
        if (r.error){
          setStatus('Error: ' + r.error, false);
        }else{
          setStatus('Done (review completed)', false);
        }
      }catch(e){
        setStatus('Error during review run', false);
      }
    };

    // populate model selects from backend list
    (function(){
      const opts  = document.getElementById('modelSel');
      const opts2 = document.getElementById('modelSel2');
      const opts3 = document.getElementById('modelSel3');
      const models = {{ models_json|safe }};
      models.forEach(m => {
        const o1 = document.createElement('option');
        o1.value = m; o1.textContent = m;
        const o2 = o1.cloneNode(true);
        const o3 = o1.cloneNode(true);
        opts.appendChild(o1);
        opts2.appendChild(o2);
        opts3.appendChild(o3);
      });
    })();

    // theme/lang selectors
    document.getElementById('themeSel').onchange = function(){
      document.body.setAttribute('data-theme', this.value);
    };
    document.getElementById('langSel').onchange = function(){
      alert('Language switcher placeholder – UI text will adapt in a future update.');
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
        has_openai_env=has_openai_env,
        has_gemini_env=has_gemini_env,
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
    extra_prompt = request.form.get("extra_prompt", "") or ""

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

    base_prompt = (
        "Organize the following 510(k) submission into structured markdown with "
        "headings, summary, and checklist."
    )
    if extra_prompt:
        base_prompt += f"\n\nAdditional reviewer instructions:\n{extra_prompt}"

    prompt = base_prompt + "\n\nSource:\n" + text[:3000]

    res = call_llm(model, prompt, max_tokens=max_tokens)
    if "text" in res:
        return jsonify({"result": res["text"]})
    return jsonify({"error": res.get("error", "unknown")}), 500


@app.route("/transform_checklist", methods=["POST"])
def transform_checklist():
    pasted = request.form.get("pasted", "")
    model = request.form.get("model") or "gpt-4o-mini"
    max_tokens = int(request.form.get("max_tokens") or 12000)
    extra_prompt = request.form.get("extra_prompt", "") or ""

    f = request.files.get("file")
    text = pasted
    if f:
        try:
            text = f.stream.read().decode("utf-8")
        except Exception:
            text = ""

    base_prompt = (
        "Organize the following checklist into a clear markdown checklist grouped by sections."
    )
    if extra_prompt:
        base_prompt += f"\n\nAdditional reviewer instructions:\n{extra_prompt}"

    prompt = base_prompt + "\n\nSource:\n" + text[:3000]

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
    extra_prompt = request.form.get("extra_prompt", "") or ""

    base_prompt = (
        "Using the checklist below, evaluate the submission and produce a structured review "
        "report with findings, recommended actions, and missing documents."
    )
    if extra_prompt:
        base_prompt += f"\n\nAdditional reviewer instructions:\n{extra_prompt}"

    prompt = (
        base_prompt
        + "\n\nCHECKLIST:\n"
        + checklist[:2000]
        + "\n\nSUBMISSION:\n"
        + submission[:8000]
    )

    res = call_llm(model, prompt, max_tokens=max_tokens)
    if "text" in res:
        return jsonify({"result": res["text"]})
    return jsonify({"error": res.get("error", "unknown")}), 500


if __name__ == "__main__":
    # For local debugging; in production use a proper WSGI server
    app.run(host="0.0.0.0", port=5000, debug=True)
