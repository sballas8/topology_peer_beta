from pathlib import Path
import json, os, re, sqlite3, time, uuid
from datetime import datetime, timezone, timedelta

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
COURSE = ROOT / "course"
DB = COURSE / "conversations" / "beta_conversations.db"
SCHEMA = COURSE / "conversations" / "schema.sql"

# Local development still uses ~/.config/topology-peer/.env. Hosted deployments can
# provide the same values as environment variables or Streamlit secrets.
load_dotenv(Path.home() / ".config" / "topology-peer" / ".env")

def setting(name, default=None, cast=str):
    value = os.getenv(name)
    if value is None:
        try:
            value = st.secrets.get(name, None)
        except Exception:
            value = None
    if value is None:
        return default
    return cast(value)

MODEL = setting("TOPOLOGY_PEER_MODEL", "gpt-5.6")
MAX_OUTPUT_TOKENS = setting("MAX_OUTPUT_TOKENS", 1000, int)
MAX_DAILY_CALLS = setting("MAX_DAILY_CALLS", 50, int)
MAX_CONVERSATION_STUDENT_MESSAGES = setting("MAX_CONVERSATION_STUDENT_MESSAGES", 30, int)
MAX_CALLS_PER_MINUTE = setting("MAX_CALLS_PER_MINUTE", 8, int)
BETA_BUDGET_USD = setting("BETA_BUDGET_USD", 25.0, float)
# Current regular GPT-5.6 Sol promotional rates; configurable so pricing changes do not
# require an application edit.
INPUT_USD_PER_M = setting("INPUT_USD_PER_M", 4.0, float)
CACHED_INPUT_USD_PER_M = setting("CACHED_INPUT_USD_PER_M", 0.40, float)
OUTPUT_USD_PER_M = setting("OUTPUT_USD_PER_M", 20.0, float)

raw_codes = setting("BETA_TESTER_CODES", "") or ""
ALLOWED_TESTER_CODES = {x.strip() for x in raw_codes.split(",") if x.strip()}

api_key = setting("OPENAI_API_KEY")
if not api_key:
    st.error("The beta server is missing its OpenAI API key.")
    st.stop()
client = OpenAI(api_key=api_key)

def now():
    return datetime.now(timezone.utc).isoformat()

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

course = load_json(COURSE / "course.json")
tutor_prompt = (COURSE / "prompts" / "tutor_prompt.txt").read_text(encoding="utf-8")
homeworks = [load_json(p) for p in sorted((COURSE / "homework").glob("*.json"))]
homeworks = [h for h in homeworks if h.get("available", True)]
activity_files = [load_json(p) for p in sorted((COURSE / "activities").glob("*.json"))]
activities = [item for week in activity_files for item in week.get("items", [])]

def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c

def initialize_db():
    with db() as c:
        c.executescript(SCHEMA.read_text(encoding="utf-8"))
        c.execute("INSERT OR IGNORE INTO tutor_versions(tutor_version,prompt_text,model_name,created_at) VALUES (?,?,?,?)",
                  (course["tutor_version"], tutor_prompt, MODEL, now()))

initialize_db()

st.set_page_config(page_title=f"{course['peer_name']} Beta", layout="wide")

st.markdown("""
<style>
:root {
    --fsu-garnet: #782F40;
    --fsu-gold: #CEB888;
    --fsu-pale-gold: #F3EDE1;
    --fsu-ink: #2F2A2B;
}

/* Overall page */
.stApp {
    background: #FFFFFF;
    color: var(--fsu-ink);
}

/* A restrained FSU accent bar */
.stApp::before {
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: var(--fsu-garnet);
    z-index: 999999;
}

/* Main title and headings */
h1, h2, h3 {
    color: var(--fsu-garnet);
}
h4, h5, h6 {
    color: #5B2430;
}

/* Primary buttons */
.stButton > button[kind="primary"] {
    background-color: var(--fsu-garnet);
    border-color: var(--fsu-garnet);
    color: white;
}
.stButton > button[kind="primary"]:hover {
    background-color: #642735;
    border-color: #642735;
}

/* Regular buttons: understated garnet outline */
.stButton > button:not([kind="primary"]) {
    border-color: #B08A94;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: var(--fsu-garnet);
    color: var(--fsu-garnet);
}

/* Inputs and selectors */
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"]:focus-within,
textarea:focus {
    border-color: var(--fsu-garnet) !important;
    box-shadow: 0 0 0 1px var(--fsu-garnet) !important;
}

/* Expanders and left-side content get a light academic-paper feel */
div[data-testid="stExpander"] {
    border-color: #D9CCB6;
    border-radius: 8px;
}

/* Chat messages: keep conversation readable, with subtle role separation */
div[data-testid="stChatMessage"] {
    border-radius: 10px;
    border: 1px solid #E6E0D7;
}
div[data-testid="stChatMessage"]:nth-of-type(even) {
    background: #FBF8F2;
}

/* Chat input */
div[data-testid="stChatInput"] {
    border-top: 2px solid var(--fsu-gold);
}

/* Sliders */
div[data-testid="stSlider"] [role="slider"] {
    background-color: var(--fsu-garnet);
}

/* Links */
a {
    color: var(--fsu-garnet);
}

/* Captions stay quiet rather than school-colored */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #686064;
}

/* Give the page a little more breathing room */
.block-container {
    padding-top: 2.6rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}
</style>
""", unsafe_allow_html=True)

# ---------- Closed-beta identity ----------
# Testers receive random codes (e.g. T7K4Q2). No name/email is requested or stored.
if "student_id" not in st.session_state:
    st.title(f"{course['peer_name']} — Beta")
    st.caption("Private usability test • Undergraduate Topology")
    if not ALLOWED_TESTER_CODES:
        st.error("No beta tester codes are configured on this deployment.")
        st.stop()
    code = st.text_input("Tester code", type="password", help="Use the code supplied by the instructor.")
    if st.button("Enter beta", type="primary"):
        code = code.strip()
        if code not in ALLOWED_TESTER_CODES:
            st.error("That tester code is not valid.")
        else:
            safe = re.sub(r"[^A-Za-z0-9_-]", "", code)
            st.session_state.student_id = "beta_" + safe
            st.rerun()
    st.stop()

def ensure_student():
    with db() as c:
        c.execute("INSERT OR IGNORE INTO students(student_id,created_at) VALUES (?,?)",
                  (st.session_state.student_id, now()))

ensure_student()

def create_conversation(workspace, title, homework_id=None, problem_id=None, activity_id=None):
    cid = "conv_" + uuid.uuid4().hex
    t = now()
    with db() as c:
        c.execute("""INSERT INTO conversations
            (conversation_id,student_id,title,workspace,homework_id,problem_id,activity_id,tutor_version,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (cid, st.session_state.student_id, title, workspace, homework_id, problem_id, activity_id,
             course["tutor_version"], t, t))
    return cid

def load_messages(cid):
    with db() as c:
        return c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY sequence_number", (cid,)).fetchall()

def get_conversation(cid):
    if not cid:
        return None
    with db() as c:
        return c.execute("SELECT * FROM conversations WHERE conversation_id=? AND student_id=?",
                         (cid, st.session_state.student_id)).fetchone()

def save_message(cid, role, content):
    with db() as c:
        n = c.execute("SELECT COALESCE(MAX(sequence_number),0)+1 FROM messages WHERE conversation_id=?",
                      (cid,)).fetchone()[0]
        c.execute("INSERT INTO messages(message_id,conversation_id,sequence_number,role,content,created_at) VALUES (?,?,?,?,?,?)",
                  ("msg_" + uuid.uuid4().hex, cid, n, role, content, now()))
        c.execute("UPDATE conversations SET updated_at=? WHERE conversation_id=?", (now(), cid))


def delete_last_student_message(cid):
    """Remove the just-submitted student turn when no tutor request was successfully completed.

    This keeps a failed billing/network request from becoming part of future tutor context.
    The student's earlier conversation remains untouched.
    """
    with db() as c:
        row = c.execute(
            "SELECT message_id FROM messages WHERE conversation_id=? AND role='student' ORDER BY sequence_number DESC LIMIT 1",
            (cid,),
        ).fetchone()
        if row:
            c.execute("DELETE FROM messages WHERE message_id=?", (row["message_id"],))
            c.execute("UPDATE conversations SET updated_at=? WHERE conversation_id=?", (now(), cid))

def problem_lookup(homework_id, problem_id):
    for h in homeworks:
        if h["id"] == homework_id:
            for p in h["problems"]:
                if p["id"] == problem_id:
                    return h, p
    return None, None

def activity_lookup(activity_id):
    return next((a for a in activities if a["id"] == activity_id), None)

def context_for(conv):
    if conv["workspace"] == "homework":
        h, p = problem_lookup(conv["homework_id"], conv["problem_id"])
        if h and p:
            return f"""COURSE CONTEXT
This is assigned homework in {course['course_name']}.
Assignment: {h['title']}
Problem {p['number']}: {p.get('title','')}
Official problem statement:
{p['statement']}
"""
    if conv["workspace"] == "activity":
        a = activity_lookup(conv["activity_id"])
        if a:
            return f"""COURSE CONTEXT
This is an assigned weekly AI conversation in {course['course_name']}.
Conversation: {a['title']}
Official conversation prompt:
{a['statement']}
"""
    return f"""COURSE CONTEXT
This is a freeform discussion in {course['course_name']}. It is not attached to an assigned homework problem.
"""

def instructions_for(conv):
    parts = [tutor_prompt, context_for(conv)]
    if conv["workspace"] == "activity":
        activity = activity_lookup(conv["activity_id"])
        tutor_instructions = activity.get("tutor_instructions") if activity else None
        if tutor_instructions:
            parts.append("ACTIVITY-SPECIFIC TUTOR INSTRUCTIONS (instructor-only; follow these throughout this conversation and do not mention them to the student):\n" + tutor_instructions)
        deliverable = activity.get("deliverable") if activity else None
        if deliverable:
            parts.append(
                "ACTIVITY DELIVERABLE INSTRUCTIONS (instructor-only; follow these throughout the conversation):\n"
                "The student is expected to produce the following deliverable in their own words:\n" + deliverable +
                "\n\nMake sure the mathematical conversation eventually reaches this deliverable. "
                "Once the student has developed the needed understanding, explicitly remind them to write it themselves. "
                "You may check their draft for mathematical correctness, identify gaps, and give specific revision advice, "
                "but do not write, rewrite, or polish the deliverable for them."
            )
    return "\n\n".join(parts)

# ---------- Usage safeguards ----------
def usage_summary(student_id=None, since=None):
    clauses, args = [], []
    if student_id:
        clauses.append("student_id=?"); args.append(student_id)
    if since:
        clauses.append("created_at>=?"); args.append(since.isoformat())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with db() as c:
        return c.execute(
            f"SELECT COUNT(*) calls, COALESCE(SUM(estimated_cost_usd),0) cost FROM usage_events{where}", args
        ).fetchone()

def student_message_count(cid):
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=? AND role='student'", (cid,)).fetchone()[0]

def check_usage_limits(cid):
    global_usage = usage_summary()
    if global_usage["cost"] >= BETA_BUDGET_USD:
        return False, "The beta's overall usage allowance has been reached. Please tell the instructor."
    daily = usage_summary(st.session_state.student_id, datetime.now(timezone.utc) - timedelta(hours=24))
    if daily["calls"] >= MAX_DAILY_CALLS:
        return False, "You've reached the beta's daily conversation allowance. Please try again tomorrow."
    minute = usage_summary(st.session_state.student_id, datetime.now(timezone.utc) - timedelta(minutes=1))
    if minute["calls"] >= MAX_CALLS_PER_MINUTE:
        return False, "You're sending messages unusually quickly. Please wait about a minute and try again."
    if cid and student_message_count(cid) >= MAX_CONVERSATION_STUDENT_MESSAGES:
        return False, "This thread has reached the beta length limit. Start a new conversation from Settings to continue."
    return True, None

def record_usage(response, cid, request_kind):
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    details = getattr(usage, "input_tokens_details", None)
    cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
    uncached = max(0, input_tokens - cached)
    cost = (uncached * INPUT_USD_PER_M + cached * CACHED_INPUT_USD_PER_M + output_tokens * OUTPUT_USD_PER_M) / 1_000_000
    with db() as c:
        c.execute("""INSERT INTO usage_events
            (usage_id,student_id,conversation_id,request_kind,model_name,input_tokens,cached_input_tokens,output_tokens,estimated_cost_usd,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("usage_" + uuid.uuid4().hex, st.session_state.student_id, cid, request_kind, MODEL,
             input_tokens, cached, output_tokens, cost, now()))

BILLING_ERROR_CODES = {
    "credit_balance_exhausted",
    "project_spend_limit_exceeded",
    "organization_spend_limit_exceeded",
    "billing_hard_limit_reached",
    "insufficient_quota",
}

def openai_error_code(exc):
    """Best-effort extraction of an OpenAI API error code without depending on one SDK exception class."""
    candidates = []
    for attr in ("code", "type"):
        value = getattr(exc, attr, None)
        if value:
            candidates.append(str(value))
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            for key in ("code", "type"):
                if err.get(key):
                    candidates.append(str(err[key]))
    text = " ".join(candidates + [str(exc)]).lower()
    for code in BILLING_ERROR_CODES:
        if code in text:
            return code
    # Some quota/billing failures are returned with prose rather than a stable code.
    if any(phrase in text for phrase in (
        "exceeded your current quota",
        "billing hard limit",
        "insufficient quota",
        "credit balance",
        "spend limit",
    )):
        return "billing_or_quota_exhausted"
    return None

def call_tutor(*, cid, instructions, input_value, request_kind):
    allowed, message = check_usage_limits(cid)
    if not allowed:
        return None, message
    try:
        response = client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=input_value,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:
        # Keep the student-facing message generic, but log the real exception for diagnosis.
        import traceback
        print(
            f"TOPOLOGY_PEER_OPENAI_ERROR kind={request_kind} "
            f"type={type(exc).__name__} code={openai_error_code(exc)} "
            f"message={exc!s}",
            flush=True,
        )
        traceback.print_exc()
        if openai_error_code(exc):
            return None, (
                "Topology Peer is temporarily unavailable because the beta's API usage allowance "
                "has been exhausted. Your conversation is saved; please try again after the "
                "instructor restores the allowance."
            )
        return None, "Topology Peer could not complete that request. Please try again."
    record_usage(response, cid, request_kind)
    return response.output_text, None

def launch_activity_if_needed(cid):
    conv = get_conversation(cid)
    if not conv or conv["workspace"] != "activity" or load_messages(cid):
        return None
    activity = activity_lookup(conv["activity_id"])
    initial_prompt = activity.get("initial_prompt") if activity else None
    if not initial_prompt:
        return None
    answer, error = call_tutor(
        cid=cid,
        instructions=(instructions_for(conv) + "\n\nACTIVITY LAUNCH INSTRUCTION (instructor-only; this applies only to the opening message; do not mention it to the student):\n" + initial_prompt),
        input_value="Begin this assigned conversation now with the student-facing opening message.",
        request_kind="activity_launch",
    )
    if answer:
        save_message(cid, "assistant", answer)
    return error

# ---------- Main beta UI ----------
st.markdown(
    f"""
    <div style="border-bottom: 3px solid #CEB888; padding: 0.15rem 0 0.8rem 0; margin-bottom: 1.2rem;">
        <div style="font-size: 2.15rem; font-weight: 700; color: #782F40; line-height: 1.15;">
            {course['peer_name']}
        </div>
        <div style="font-size: 0.98rem; color: #554D50; margin-top: 0.25rem;">
            Undergraduate Topology · Florida State University
            <span style="color: #8A7D81;"> · Beta</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Private usability test • Your conversations are saved under a pseudonymous tester code.")

left, right = st.columns([1, 3], gap="large")

with left:
    mode = st.selectbox("Mode", ["Homework", "Conversations", "Freeform discussion"])
    workspace = mode
    selected_hw = selected_problem = selected_activity = None

    if mode == "Homework":
        assignment_options = {h["title"]: h for h in homeworks}
        assignment_name = st.selectbox("Assignment", list(assignment_options))
        selected_hw = assignment_options[assignment_name]
        question_options = {f"Question {p['number']}: {p.get('title','')}": p for p in selected_hw["problems"]}
        question_name = st.selectbox("Question", list(question_options))
        selected_problem = question_options[question_name]
        st.markdown("#### Question")
        st.markdown(selected_problem["statement"])
    elif mode == "Conversations":
        conversation_options = {a["title"]: a for a in activities}
        conversation_name = st.selectbox("Conversation", list(conversation_options))
        selected_activity = conversation_options[conversation_name]
        st.markdown("#### Conversation prompt")
        st.markdown(selected_activity["statement"])
        if selected_activity.get("deliverable"):
            st.markdown("#### Deliverable")
            st.markdown(selected_activity["deliverable"])
    else:
        st.caption("Start a discussion about anything from the course.")

    with st.expander("How to use Topology Peer"):
        st.write("Use it naturally, as you would if you were taking the course. For assigned work, you are responsible for writing the final proof or exposition yourself. This is a beta: please report moments that feel especially helpful, frustrating, too easy, or overly guided.")

    with st.expander("Beta feedback"):
        st.caption("Feedback is linked only to your pseudonymous tester code.")
        helpfulness = st.slider("How helpful was the tutor?", 1, 5, 3)
        frustration = st.slider("How frustrating was the interaction?", 1, 5, 1)
        too_much = st.slider("How often did it give too much away?", 1, 5, 1)
        unnecessary = st.slider("How often did it make you do unnecessary work after you understood?", 1, 5, 1)
        comments = st.text_area("Anything else?", placeholder="A particular moment, suggestion, or problem...")
        if st.button("Submit feedback"):
            with db() as c:
                c.execute("""INSERT INTO feedback(feedback_id,student_id,conversation_id,helpfulness,frustration,too_much,unnecessary_work,comments,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    ("feedback_" + uuid.uuid4().hex, st.session_state.student_id,
                     st.session_state.get("active_conversation"), helpfulness, frustration, too_much, unnecessary, comments, now()))
            st.success("Feedback saved. Thank you.")

with right:
    c1, c2 = st.columns([8, 2])
    with c1:
        st.subheader("Dialogue")
    with c2:
        with st.popover("⚙ Settings"):
            if st.button("New conversation", use_container_width=True):
                if workspace == "Conversations" and selected_activity:
                    st.session_state.active_conversation = create_conversation("activity", selected_activity["title"], activity_id=selected_activity["id"])
                elif workspace == "Homework" and selected_hw and selected_problem:
                    st.session_state.active_conversation = create_conversation(
                        "homework", f"{selected_hw['title']}, Problem {selected_problem['number']}", selected_hw["id"], selected_problem["id"])
                else:
                    st.session_state.pop("active_conversation", None)
                st.rerun()
            if st.button("Leave beta", use_container_width=True):
                for key in ["student_id", "active_conversation"]:
                    st.session_state.pop(key, None)
                st.rerun()

    if workspace == "Homework" and selected_hw and selected_problem:
        desired_key = ("homework", selected_hw["id"], selected_problem["id"])
        active = st.session_state.get("active_conversation")
        active_row = get_conversation(active) if active else None
        active_key = (active_row["workspace"], active_row["homework_id"], active_row["problem_id"]) if active_row else None
        if active_key != desired_key:
            st.session_state.active_conversation = create_conversation(
                "homework", f"{selected_hw['title']}, Problem {selected_problem['number']}", selected_hw["id"], selected_problem["id"])
    elif workspace == "Conversations" and selected_activity:
        desired_key = ("activity", selected_activity["id"])
        active = st.session_state.get("active_conversation")
        active_row = get_conversation(active) if active else None
        active_key = (active_row["workspace"], active_row["activity_id"]) if active_row else None
        if active_key != desired_key:
            with db() as c:
                prior = c.execute("SELECT conversation_id FROM conversations WHERE student_id=? AND workspace='activity' AND activity_id=? ORDER BY updated_at DESC LIMIT 1",
                                  (st.session_state.student_id, selected_activity["id"])).fetchone()
            st.session_state.active_conversation = prior["conversation_id"] if prior else create_conversation("activity", selected_activity["title"], activity_id=selected_activity["id"])
    elif workspace == "Freeform discussion":
        active = st.session_state.get("active_conversation")
        active_row = get_conversation(active) if active else None
        if not active_row or active_row["workspace"] != "freeform":
            st.session_state.active_conversation = create_conversation("freeform", "Freeform discussion")

    cid = st.session_state.get("active_conversation")
    conv = get_conversation(cid) if cid else None
    if conv:
        last_error = st.session_state.pop("beta_last_error", None)
        if last_error:
            st.warning(last_error)
        launch_error = launch_activity_if_needed(cid)
        if launch_error:
            st.warning(launch_error)
        messages = load_messages(cid)
        for m in messages:
            with st.chat_message("user" if m["role"] == "student" else "assistant"):
                st.markdown(m["content"])

        limit_ok, limit_message = check_usage_limits(cid)
        if not limit_ok:
            st.warning(limit_message)
        user_text = st.chat_input("Message Topology Peer", disabled=not limit_ok)
        if user_text:
            # Check again immediately before spending tokens. Save only if the request can run.
            limit_ok, limit_message = check_usage_limits(cid)
            if not limit_ok:
                st.warning(limit_message)
            else:
                save_message(cid, "student", user_text)
                messages = load_messages(cid)
                api_messages = [{"role": "user" if m["role"] == "student" else "assistant", "content": m["content"]} for m in messages]
                with st.spinner("Topology Peer is thinking..."):
                    answer, error = call_tutor(
                        cid=cid, instructions=instructions_for(conv), input_value=api_messages, request_kind="dialogue"
                    )
                if answer:
                    save_message(cid, "assistant", answer)
                else:
                    # The tutor never processed this turn successfully. Remove it so the student
                    # can retry after a billing/quota/network problem without corrupting context.
                    delete_last_student_message(cid)
                    if error:
                        st.warning(error)
                    st.session_state["beta_last_error"] = error or "Topology Peer could not complete that request."
                st.rerun()
    else:
        st.info("Choose a homework problem, open a saved conversation, or start a freeform discussion.")
