from flask import Flask, request, jsonify, abort
import threading
import uuid
from datetime import datetime, timezone

from linebot.v3.webhook import WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from mentor_agent import get_response_from_agent

app = Flask(__name__)

# ── LINE credentials ── replace with real values ──────────────────────────────
CHANNEL_ACCESS_TOKEN = "TobskshErd4xjtvjO/eMwJ/twpRtTuuEOl9OFwaBMMBVqHVxowRAhJrTH13eHU5soYQ/kBjud5WZv+mk0BDJ3Fm6XDWf3b3e1nYeW7hWFolrmFuo5AEfBkhUiVBPiyMwYXsYQkbWRF7HpO02D3TxxgdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET       = "bccb6b4002087fdcd5dd481ac2383cfc"
DEFAULT_USER_ID      = "U192772f59a4321d51d8b084fde86748d"
# ──────────────────────────────────────────────────────────────────────────────

config      = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
api_client  = ApiClient(config)
line_bot_api = MessagingApi(api_client)
handler     = WebhookHandler(CHANNEL_SECRET)

# In-memory job tracker (reset on restart; swap for Redis/DB in production)
JOB_STATUS: dict = {}


# ══════════════════════════════════════════════════════════════
#  Health check
# ══════════════════════════════════════════════════════════════

@app.get("/")
def health():
    return "Mentor Agent OK", 200


# ══════════════════════════════════════════════════════════════
#  LINE Webhook
# ══════════════════════════════════════════════════════════════

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text   = event.message.text
    reply_token = event.reply_token

    # Acknowledge immediately to avoid LINE timeout
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="Thinking... give me a moment.")],
        )
    )

    def process():
        try:
            reply = get_response_from_agent(user_text)
            if not reply:
                reply = "Sorry, I couldn't generate a response."
        except Exception as e:
            reply = f"Error: {str(e)}"

        line_bot_api.push_message(
            PushMessageRequest(
                to=event.source.user_id,
                messages=[TextMessage(text=reply)],
            )
        )

    threading.Thread(target=process, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  REST  /prompt  (for testing or external triggers)
# ══════════════════════════════════════════════════════════════

def _send_to_user(message: str, user_id: str = DEFAULT_USER_ID) -> None:
    line_bot_api.push_message(
        PushMessageRequest(
            to=user_id,
            messages=[TextMessage(text=message)],
        )
    )


def _run_prompt_job(job_id: str, prompt: str, user_id: str) -> None:
    JOB_STATUS[job_id] = {
        "status":     "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "prompt":     prompt,
    }
    try:
        response = get_response_from_agent(prompt)
        _send_to_user(response, user_id=user_id)
        JOB_STATUS[job_id].update({
            "status":      "done",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "response":    response,
        })
    except Exception as e:
        JOB_STATUS[job_id].update({
            "status":      "error",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error":       str(e),
        })


@app.route("/prompt", methods=["GET"])
def get_prompt():
    """Quick GET test: /prompt?prompt=Hello"""
    prompt = request.args.get("prompt")
    if not prompt:
        return jsonify({"error": "Missing 'prompt' query parameter"}), 400
    response = get_response_from_agent(prompt)
    return jsonify({"prompt": prompt, "response": response})


@app.route("/prompt", methods=["POST"])
def post_prompt():
    """
    POST /prompt
    Body: { "prompt": "...", "user_id": "optional" }
    Returns immediately with a job_id; sends reply via LINE push when done.
    """
    data   = request.get_json(silent=True) or {}
    prompt = data.get("prompt")
    if not prompt:
        return jsonify({"error": "Missing 'prompt' in request body"}), 400

    user_id = data.get("user_id", DEFAULT_USER_ID)
    job_id  = uuid.uuid4().hex
    JOB_STATUS[job_id] = {"status": "queued"}

    t = threading.Thread(
        target=_run_prompt_job,
        args=(job_id, prompt, user_id),
        daemon=True,
    )
    t.start()

    return jsonify({"status": "queued", "job_id": job_id}), 202


@app.get("/jobs/<job_id>")
def get_job(job_id: str):
    job = JOB_STATUS.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job), 200


# ══════════════════════════════════════════════════════════════
#  Direct REST endpoints (no LINE, useful for web/mobile clients)
# ══════════════════════════════════════════════════════════════

@app.route("/reflect", methods=["POST"])
def reflect():
    """POST /reflect  { "content": "...", "tags": "mindset,trading" }"""
    from mongodb_mentor import save_reflection
    data    = request.get_json(silent=True) or {}
    content = data.get("content")
    if not content:
        return jsonify({"error": "Missing 'content'"}), 400
    tags = [t.strip() for t in data.get("tags", "").split(",") if t.strip()]
    result = save_reflection(content, tags)
    return jsonify(result)


@app.route("/remind", methods=["POST"])
def remind():
    """POST /remind  { "content": "...", "priority": "high" }"""
    from mongodb_mentor import save_reminder
    data     = request.get_json(silent=True) or {}
    content  = data.get("content")
    priority = data.get("priority", "medium")
    if not content:
        return jsonify({"error": "Missing 'content'"}), 400
    result = save_reminder(content, priority)
    return jsonify(result)


@app.route("/weekly", methods=["GET"])
def weekly():
    """GET /weekly?year=2025&week=14  (omit params for current week)"""
    from mongodb_mentor import get_weekly_summary
    year = request.args.get("year", 0, type=int)
    week = request.args.get("week", 0, type=int)
    return jsonify(get_weekly_summary(year or None, week or None))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)