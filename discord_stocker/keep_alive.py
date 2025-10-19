import os
from threading import Thread

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return "I'm alive"


@app.route("/healthz")
def health():
    return jsonify({"status": "ok"})


def _run():
    # RenderはPORT環境変数が渡される
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)


def start_server():
    t = Thread(target=_run, daemon=True)
    t.start()
