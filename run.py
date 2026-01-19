# run.py
import threading
import webview
from app import app

def start_flask():
    app.run(host="127.0.0.1", port=5000, debug=False)

if __name__ == "__main__":
    # Run Flask in a separate thread
    t = threading.Thread(target=start_flask)
    t.daemon = True
    t.start()

    # Open PyWebView window pointing to Flask app
    webview.create_window("My Flask App", "http://127.0.0.1:5000")
    webview.start()
