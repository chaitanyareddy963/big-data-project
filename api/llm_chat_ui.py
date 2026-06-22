"""Tiny browser chat UI for the Gemini operations assistant."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlparse

from api.llm_ops_assistant import DEFAULT_MODEL, answer_question, load_dotenv


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Aviation LLM Operations Assistant</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #08111f; color: #e8eefc; }
    header { padding: 22px 28px; background: linear-gradient(120deg, #10213f, #153b61); border-bottom: 1px solid #24476d; }
    h1 { margin: 0 0 6px; font-size: 24px; }
    p { margin: 0; color: #b9c7db; }
    main { max-width: 1080px; margin: 0 auto; padding: 24px; }
    .grid { display: grid; grid-template-columns: 1fr 320px; gap: 18px; }
    .panel { background: #0f1d33; border: 1px solid #24476d; border-radius: 14px; box-shadow: 0 12px 30px #0008; }
    #chat { height: 520px; overflow-y: auto; padding: 18px; }
    .message { margin: 0 0 14px; padding: 13px 15px; border-radius: 12px; line-height: 1.45; }
    .message p { margin: 0 0 10px; }
    .message p:last-child { margin-bottom: 0; }
    .message ul, .message ol { margin: 8px 0 10px 20px; padding: 0; }
    .message li { margin: 4px 0; }
    .message h3 { margin: 12px 0 8px; font-size: 16px; color: #f1f6ff; }
    .message code { background: #071324; border: 1px solid #27496f; border-radius: 5px; padding: 1px 5px; color: #d5ebff; }
    .message pre { background: #071324; border: 1px solid #27496f; border-radius: 10px; padding: 10px; overflow-x: auto; white-space: pre; }
    .message pre code { border: 0; padding: 0; background: transparent; }
    .user { background: #214f82; margin-left: 10%; }
    .assistant { background: #132943; margin-right: 10%; border: 1px solid #2b5a88; }
    .meta { font-size: 12px; color: #94a8c0; margin-bottom: 6px; }
    form { display: flex; gap: 10px; padding: 14px; border-top: 1px solid #24476d; }
    input { flex: 1; background: #08111f; color: #e8eefc; border: 1px solid #345f8d; border-radius: 10px; padding: 12px; font-size: 15px; }
    button { background: #4aa3ff; color: #06101f; border: 0; border-radius: 10px; padding: 0 18px; font-weight: 700; cursor: pointer; }
    button:disabled { opacity: .55; cursor: wait; }
    aside { padding: 16px; }
    aside h2 { margin: 0 0 12px; font-size: 17px; }
    .quick { display: block; width: 100%; text-align: left; margin: 8px 0; padding: 10px; border: 1px solid #345f8d; border-radius: 10px; background: #10233a; color: #dceaff; }
    .status { margin-top: 16px; padding: 12px; border-radius: 10px; background: #091629; color: #b9c7db; font-size: 13px; }
    a { color: #7fc0ff; }
    @media (max-width: 850px) { .grid { grid-template-columns: 1fr; } #chat { height: 440px; } }
  </style>
</head>
<body>
  <header>
    <h1>Aviation LLM Operations Assistant</h1>
    <p>Ask questions about the codebase, docs, notebooks, MLflow, Airflow, Kafka, MinIO, Spark, Grafana dashboards, service logs, replay evidence, API predictions, and demo limitations.</p>
  </header>
  <main class="grid">
    <section class="panel">
      <div id="chat">
        <div class="message assistant">
          <div class="meta">assistant</div>
          Ask me what is happening in the aviation disruption platform right now.
        </div>
      </div>
      <form id="form">
        <input id="question" autocomplete="off" placeholder="Example: Which files implement the dataset replay and API scoring path?" />
        <button id="send" type="submit">Ask</button>
      </form>
    </section>
    <aside class="panel">
      <h2>Demo Questions</h2>
      <button class="quick">Summarize what is happening right now.</button>
      <button class="quick">Which files implement the dataset replay and API scoring path?</button>
      <button class="quick">How does the dataset streaming replay work?</button>
      <button class="quick">What is the current status of MLflow, Kafka, MinIO, Spark, and Grafana?</button>
      <button class="quick">Are there recent warnings or errors in the service logs?</button>
      <button class="quick">Which downloaded datasets are used by the model?</button>
      <button class="quick">What should I show in Grafana for final presentation?</button>
      <button class="quick">Explain the current risk prediction and limitations.</button>
      <div class="status" id="status">Checking assistant status...</div>
    </aside>
  </main>
  <script>
    const chat = document.getElementById('chat');
    const form = document.getElementById('form');
    const input = document.getElementById('question');
    const send = document.getElementById('send');
    const statusBox = document.getElementById('status');

    function escapeHtml(text) {
      return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    }

    function renderInlineMarkdown(text) {
      return text
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>')
        .replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
    }

    function renderMarkdown(text) {
      const escaped = escapeHtml(text);
      const lines = escaped.split('\\n');
      const blocks = [];
      let paragraph = [];
      let listItems = [];
      let inCode = false;
      let codeLines = [];

      function flushParagraph() {
        if (paragraph.length) {
          blocks.push('<p>' + renderInlineMarkdown(paragraph.join(' ')) + '</p>');
          paragraph = [];
        }
      }
      function flushList() {
        if (listItems.length) {
          blocks.push('<ul>' + listItems.map(item => '<li>' + renderInlineMarkdown(item) + '</li>').join('') + '</ul>');
          listItems = [];
        }
      }

      for (const line of lines) {
        if (line.trim().startsWith('```')) {
          if (inCode) {
            blocks.push('<pre><code>' + codeLines.join('\\n') + '</code></pre>');
            codeLines = [];
            inCode = false;
          } else {
            flushParagraph();
            flushList();
            inCode = true;
          }
          continue;
        }
        if (inCode) {
          codeLines.push(line);
          continue;
        }

        const trimmed = line.trim();
        if (!trimmed) {
          flushParagraph();
          flushList();
          continue;
        }
        if (trimmed.startsWith('### ')) {
          flushParagraph();
          flushList();
          blocks.push('<h3>' + renderInlineMarkdown(trimmed.slice(4)) + '</h3>');
          continue;
        }
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          flushParagraph();
          listItems.push(trimmed.slice(2));
          continue;
        }
        const numbered = trimmed.match(/^\\d+\\.\\s+(.+)$/);
        if (numbered) {
          flushParagraph();
          listItems.push(numbered[1]);
          continue;
        }
        flushList();
        paragraph.push(trimmed);
      }
      flushParagraph();
      flushList();
      if (inCode) blocks.push('<pre><code>' + codeLines.join('\\n') + '</code></pre>');
      return blocks.join('');
    }

    function addMessage(role, text, render = false) {
      const div = document.createElement('div');
      div.className = 'message ' + role;
      div.innerHTML = '<div class="meta">' + role + '</div>' + (render ? renderMarkdown(text) : '<p>' + escapeHtml(text) + '</p>');
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    async function ask(question) {
      addMessage('user', question);
      send.disabled = true;
      input.value = '';
      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({question})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Request failed');
        addMessage('assistant', data.answer + '\\n\\n[source: ' + data.provider + ', model: ' + data.model + ']', true);
      } catch (error) {
        addMessage('assistant', 'Error: ' + error.message, true);
      } finally {
        send.disabled = false;
        input.focus();
      }
    }

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const question = input.value.trim();
      if (question) ask(question);
    });
    document.querySelectorAll('.quick').forEach((button) => {
      button.addEventListener('click', () => ask(button.textContent));
    });
    fetch('/api/health').then(r => r.json()).then(data => {
      statusBox.textContent = 'Provider: ' + data.provider + ' | Model: ' + data.model + ' | Gemini key configured: ' + data.gemini_key_configured;
    }).catch(error => {
      statusBox.textContent = 'Health check failed: ' + error.message;
    });
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--prometheus-url", default="http://prometheus:9090")
    parser.add_argument("--repo-root", default="/workspace")
    parser.add_argument("--mlflow-url", default="http://mlflow:5000")
    parser.add_argument("--airflow-url", default="http://airflow:8080")
    parser.add_argument("--kafka-bootstrap", default="kafka:9092")
    parser.add_argument("--minio-url", default="http://minio:9000")
    parser.add_argument("--spark-master-url", default="http://spark-master:8080")
    parser.add_argument("--docker-socket", default="/var/run/docker.sock")
    parser.add_argument("--simulation-jsonl", default="/workspace/data/local_cache/streaming_predictions/notebook_gold_simulation.jsonl")
    return parser.parse_args()


def make_assistant_args(server_args: argparse.Namespace, question: str) -> SimpleNamespace:
    return SimpleNamespace(
        question=question,
        model=DEFAULT_MODEL,
        api_key=None,
        prometheus_url=server_args.prometheus_url,
        repo_root=server_args.repo_root,
        mlflow_url=server_args.mlflow_url,
        airflow_url=server_args.airflow_url,
        kafka_bootstrap=server_args.kafka_bootstrap,
        minio_url=server_args.minio_url,
        spark_master_url=server_args.spark_master_url,
        docker_socket=server_args.docker_socket,
        simulation_jsonl=server_args.simulation_jsonl,
        max_events=3,
        max_file_chars=1600,
        max_context_files=25,
        log_tail=40,
        temperature=0.2,
        max_tokens=1800,
    )


class ChatHandler(BaseHTTPRequestHandler):
    server_args: argparse.Namespace

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            import os

            self.send_json(
                {
                    "ok": True,
                    "provider": "gemini" if os.getenv("GEMINI_API_KEY") else "local_fallback",
                    "model": os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
                    "gemini_key_configured": bool(os.getenv("GEMINI_API_KEY")),
                    "scope": [
                        "repo source/docs/notebooks",
                        "MLflow REST",
                        "Airflow REST",
                        "Kafka topics/messages",
                        "MinIO bucket/object samples",
                        "Spark UI REST",
                        "Grafana dashboard JSON",
                        "Docker service log tails",
                        "Prometheus metrics",
                        "streaming replay JSONL",
                    ],
                }
            )
            return
        if path == "/" or path == "/index.html":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/chat":
            self.send_json({"error": "not found"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = str(payload.get("question") or "").strip()
            if not question:
                self.send_json({"error": "question is required"}, status=400)
                return
            result = answer_question(make_assistant_args(self.server_args, question))
            self.send_json(
                {
                    "provider": result["provider"],
                    "model": result["model"],
                    "question": result["question"],
                    "answer": result["answer"],
                }
            )
        except Exception as error:
            self.send_json({"error": str(error)}, status=500)


def main() -> None:
    load_dotenv()
    args = parse_args()
    ChatHandler.server_args = args
    server = ThreadingHTTPServer((args.host, args.port), ChatHandler)
    print(f"LLM chat UI listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
