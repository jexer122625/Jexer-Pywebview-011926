Here’s a beginner‑friendly, step‑by‑step guide to set up a fresh virtual environment on another local machine and run your Flask + PyWebView app (app.py + run.py).

I’ll cover Windows, macOS, and Linux.

1. Make sure Python is installed
On the new machine:

Open a terminal:

Windows:
Press Win key, type cmd (Command Prompt) or PowerShell, open it.
macOS:
Open Terminal (Applications → Utilities → Terminal).
Linux:
Open your usual terminal.
Check Python version:

Windows:
python --version
macOS / Linux:
python3 --version
You want Python 3.9 or newer, e.g. Python 3.10.12.

If Python is not installed or is too old:

Go to https://www.python.org/downloads/
Download and install the latest Python 3.x
On Windows installer:
Check the box: “Add Python to PATH”
After installing, re‑open the terminal and check the version again.
2. Copy your project folder to the new machine
You should have a project folder on your original machine that contains at least:

app.py – your Flask web app
run.py – starts Flask + PyWebView
requirements.txt
(optional) pyproject.toml
(optional) agents.yaml
(optional) README.md or other files
On the new machine:

Create a folder for the project, for example:

Windows:
mkdir C:\Projects\wow-510k
cd C:\Projects\wow-510k
macOS / Linux:
mkdir -p ~/projects/wow-510k
cd ~/projects/wow-510k
Copy your files into this folder:

You can:
Zip the project on your original machine, copy via USB or network, unzip into this folder.
Or use Git (if your project is on GitHub/GitLab) and git clone into this folder.
After copying, your folder on the new machine should look something like:

wow-510k/
  app.py
  run.py
  requirements.txt
  pyproject.toml    (optional)
  agents.yaml       (optional)
  ...
3. Create a virtual environment
A virtual environment keeps this project’s Python packages separate from the rest of the system.

From inside your project folder (wow-510k):

Windows
python -m venv venv
This will create a folder called venv/ inside your project.

macOS / Linux
python3 -m venv venv
If you get an error like No module named venv, install the python3-venv package (Linux) or reinstall Python with venv support.

4. Activate the virtual environment
You must activate the venv every time you start work in a new terminal.

From the project folder:

Windows (Command Prompt)
venv\Scripts\activate
Windows (PowerShell)
venv\Scripts\Activate.ps1
macOS / Linux
source venv/bin/activate
If activation succeeds, your prompt will show something like:

(venv) C:\Projects\wow-510k>
or

(venv) user@machine:~/projects/wow-510k$
The (venv) prefix is important; it tells you that the virtual environment is active.

5. Install the project dependencies
With the virtual environment activated and you inside the project folder:

pip install -r requirements.txt
This will install:

Flask
pywebview
openai
google-genai
PyMuPDF (for PDFs)
PyYAML (for agents.yaml)
If pip is not recognized, use:

Windows:
python -m pip install -r requirements.txt
macOS / Linux:
python3 -m pip install -r requirements.txt
Wait until the installation finishes without errors.

6. Set API keys on the new machine (optional but usually needed)
Your app calls OpenAI and Gemini APIs. You need API keys for each provider you want to use.

You have two options:

Option A – Set environment variables (preferred)
6.1. OpenAI key
Get a key from:
https://platform.openai.com/api-keys

Then set:

Windows (PowerShell):

setx OPENAI_API_KEY "your-openai-key-here"
Close and reopen the terminal after using setx.

macOS / Linux (temporary for this terminal only):

export OPENAI_API_KEY="your-openai-key-here"
To make it permanent on macOS/Linux, you can add the export line to ~/.bashrc or ~/.zshrc.

6.2. Gemini (Google) key
Get a key from:
https://aistudio.google.com/app/apikey

Then set one of:

GEMINI_API_KEY or GOOGLE_API_KEY
Examples:

Windows (PowerShell):

setx GEMINI_API_KEY "your-gemini-key-here"
macOS / Linux (temporary):

export GEMINI_API_KEY="your-gemini-key-here"
When these environment variables are present, the app will hide the key inputs and just use them automatically.

Option B – Enter keys in the UI
If you prefer not to set environment variables:

Start the app (next section).
In the sidebar under API Keys, paste your OpenAI and Gemini keys and click Save Keys.
These are stored only in memory while the app is running.
7. Run the app with PyWebView (run.py)
With the virtual environment still active and in the project folder:

Windows
python run.py
macOS / Linux
python3 run.py
What happens:

run.py starts the Flask server in a background thread on http://127.0.0.1:5000.
PyWebView opens a native window named “My Flask App” and loads that URL.
You should see the WOW 510(k) Assistant UI with:
Settings on the left (theme, language, API keys, LLM test)
Main panels on the right (Submission, Checklist, Review, AI Note Keeper, Agents, etc.)
To stop the app:

Close the PyWebView window.
In the terminal, press Ctrl + C if the script is still running.
8. Quick test of everything
Once the PyWebView window is open:

Check UI appears – if it’s blank, see troubleshooting below.
If you set env vars, the sidebar should say:
“OpenAI key detected in environment…”
“Gemini key detected in environment…”
Use LLM Connectivity Test:
Choose a model in the dropdown (e.g. gpt-4o-mini).
Click Test LLM Call.
You should see a pop‑up with the model’s reply, and status shows “LLM test OK…”.
If this works, your environment is correctly set up and LLM keys are valid.

9. Common troubleshooting on a new machine
9.1. ModuleNotFoundError: No module named 'flask' (or others)
Likely causes:

The virtual environment is not activated.
You ran pip install without the venv active.
Fix:

In the project folder:
# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
Reinstall:
pip install -r requirements.txt
Run:
python run.py
9.2. PyMuPDF / fitz import errors
Ensure PyMuPDF installed:
pip install PyMuPDF
9.3. Port already in use (5000)
If something else is using port 5000:

Open run.py and change:

def start_flask():
    app.run(host="127.0.0.1", port=5000, debug=False)
to something like:

def start_flask():
    app.run(host="127.0.0.1", port=5001, debug=False)
Also change:

webview.create_window("My Flask App", "http://127.0.0.1:5000")
to:

webview.create_window("My Flask App", "http://127.0.0.1:5001")
Then run python run.py again.

9.4. LLM errors about API keys
Check the env vars (OPENAI_API_KEY, GEMINI_API_KEY / GOOGLE_API_KEY).
Or enter the keys in the UI under API Keys and click Save Keys.
Use Test LLM Call to confirm.
10. Summary checklist for a new machine
Install Python 3.9+
Copy the project folder (app.py, run.py, requirements.txt, etc.)
In the project folder, create venv: python -m venv venv
Activate venv:
Windows: venv\Scripts\activate
macOS/Linux: source venv/bin/activate
Install dependencies: pip install -r requirements.txt
Set OPENAI_API_KEY and GEMINI_API_KEY (or use UI fields).
Run: python run.py
Use the app in the PyWebView window.
