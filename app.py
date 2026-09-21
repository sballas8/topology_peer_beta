from pathlib import Path
import json, os, re, time, uuid
from datetime import datetime, timezone, timedelta

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from storage import SQLiteStorage

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
APP_NAME = "Anna"
MAX_OUTPUT_TOKENS = setting("MAX_OUTPUT_TOKENS", 1000, int)
MAX_DAILY_CALLS = setting("MAX_DAILY_CALLS", 50, int)
MAX_CONVERSATION_STUDENT_MESSAGES = setting("MAX_CONVERSATION_STUDENT_MESSAGES", 30, int)
MAX_CALLS_PER_MINUTE = setting("MAX_CALLS_PER_MINUTE", 8, int)
MAX_STUDENT_MESSAGE_CHARS = setting("MAX_STUDENT_MESSAGE_CHARS", 8000, int)
MAX_CONVERSATION_CHARS = setting("MAX_CONVERSATION_CHARS", 60000, int)
OPENAI_TIMEOUT_SECONDS = setting("OPENAI_TIMEOUT_SECONDS", 45.0, float)
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
client = OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS)

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

storage = SQLiteStorage(DB, SCHEMA)
storage.initialize(course["tutor_version"], tutor_prompt, MODEL, now())

st.set_page_config(page_title=f"{APP_NAME} Beta", layout="wide")

st.markdown("""
<style>
:root {
    --fsu-garnet: #782F40;
    --fsu-garnet-dark: #4F1F2A;
    --fsu-gold: #CEB888;
    --fsu-pale-gold: #F5F0E7;
    --fsu-paper: #FCFAF6;
    --fsu-ink: #2F292B;
    --fsu-muted: #6D6467;
}

/* Warm paper-like page rather than a completely white application shell */
.stApp {
    background:
        linear-gradient(180deg, #F7F2E9 0px, #FCFAF6 150px, #FFFFFF 430px);
    color: var(--fsu-ink);
}

/* Stronger university-color band, still intentionally narrow */
.stApp::before {
    content: "";
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 9px;
    background: linear-gradient(90deg,
        var(--fsu-garnet) 0%,
        var(--fsu-garnet) 82%,
        var(--fsu-gold) 82%,
        var(--fsu-gold) 100%);
    z-index: 999999;
}

.block-container {
    padding-top: 2.5rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

/* Typography */
h1, h2, h3 {
    color: var(--fsu-garnet);
    letter-spacing: -0.015em;
}
h4, h5, h6 {
    color: var(--fsu-garnet-dark);
}

/* The left control column reads as a coherent course panel */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #DDD2C1;
}

/* Selects and text fields */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
textarea {
    border-radius: 7px !important;
}
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"]:focus-within,
textarea:focus {
    border-color: var(--fsu-garnet) !important;
    box-shadow: 0 0 0 1px var(--fsu-garnet) !important;
}

/* Buttons */
.stButton > button[kind="primary"] {
    background-color: var(--fsu-garnet);
    border-color: var(--fsu-garnet);
    color: white;
    font-weight: 600;
}
.stButton > button[kind="primary"]:hover {
    background-color: var(--fsu-garnet-dark);
    border-color: var(--fsu-garnet-dark);
}
.stButton > button:not([kind="primary"]) {
    border: 1px solid #BCA9AE;
    border-radius: 7px;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: var(--fsu-garnet);
    color: var(--fsu-garnet);
}

/* Problem / activity material gets a warmer course-handout feel */
div[data-testid="stExpander"] {
    background: rgba(255,255,255,.68);
    border: 1px solid #DDD0BC;
    border-radius: 9px;
}
div[data-testid="stExpander"] summary:hover {
    color: var(--fsu-garnet);
}

/* Dialogue pane */
div[data-testid="stChatMessage"] {
    border-radius: 12px;
    border: 1px solid #E3DCD2;
    padding-top: .35rem;
    padding-bottom: .35rem;
    box-shadow: 0 1px 2px rgba(55,35,40,.035);
}

/* Assistant turns feel like Anna; user turns stay neutral */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: var(--fsu-pale-gold);
    border-left: 4px solid var(--fsu-garnet);
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #FFFFFF;
    border-left: 4px solid var(--fsu-gold);
}

/* Chat input anchors the dialogue in the palette */
div[data-testid="stChatInput"] {
    border: 1px solid #D7C8B1;
    border-top: 3px solid var(--fsu-garnet);
    border-radius: 10px;
    background: #FFFFFF;
}

/* Settings button */
button[aria-label*="Settings"] {
    color: var(--fsu-garnet);
}

/* Sliders */
div[data-testid="stSlider"] [role="slider"] {
    background-color: var(--fsu-garnet);
}

/* Links */
a {
    color: var(--fsu-garnet);
    text-decoration-color: var(--fsu-gold);
}

/* Captions */
.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--fsu-muted);
}

/* Gentle divider treatment */
hr {
    border-color: #D9C8AD;
}
</style>
""", unsafe_allow_html=True)

# ---------- Closed-beta identity ----------
# Testers receive random codes (e.g. T7K4Q2). No name/email is requested or stored.
if "student_id" not in st.session_state:
    st.title(f"{APP_NAME} — Beta")
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
    storage.ensure_student(st.session_state.student_id, now())

ensure_student()

def create_conversation(workspace, title, homework_id=None, problem_id=None, activity_id=None):
    cid = "conv_" + uuid.uuid4().hex
    t = now()
    storage.create_conversation(
        conversation_id=cid,
        student_id=st.session_state.student_id,
        title=title,
        workspace=workspace,
        homework_id=homework_id,
        problem_id=problem_id,
        activity_id=activity_id,
        tutor_version=course["tutor_version"],
        created_at=t,
    )
    return cid

def load_messages(cid):
    return storage.load_messages(cid, st.session_state.student_id)

def display_timestamp(value):
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return str(value)

def transcript_filename(conv):
    safe_title = re.sub(r"[^A-Za-z0-9]+", "-", conv["title"]).strip("-").lower()
    date = str(conv["created_at"])[:10]
    return f"anna-transcript-{date}-{safe_title or 'conversation'}.md"

def render_transcript(conv, messages):
    """Create the student-facing record without internal prompts or identifiers."""
    workspace_labels = {
        "homework": "Homework",
        "activity": "Assigned conversation",
        "freeform": "Freeform discussion",
    }
    lines = [
        "# Anna Conversation Transcript",
        "",
        f"**Course:** {course['course_name']}",
        f"**Context:** {workspace_labels.get(conv['workspace'], conv['workspace'])}",
        f"**Topic:** {conv['title']}",
        f"**Started:** {display_timestamp(conv['created_at'])}",
        f"**Last updated:** {display_timestamp(conv['updated_at'])}",
        f"**Tutor version:** {conv['tutor_version']}",
        "",
        "---",
        "",
    ]
    for message in messages:
        speaker = "Student" if message["role"] == "student" else APP_NAME
        timestamp = display_timestamp(message["created_at"])
        lines.extend([
            f"## {speaker}" + (f" — {timestamp}" if timestamp else ""),
            "",
            message["content"].strip(),
            "",
            "---",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"

def get_conversation(cid):
    if not cid:
        return None
    return storage.get_conversation(cid, st.session_state.student_id)

def save_message(cid, role, content):
    storage.save_message(
        message_id="msg_" + uuid.uuid4().hex,
        conversation_id=cid,
        student_id=st.session_state.student_id,
        role=role,
        content=content,
        created_at=now(),
    )


def delete_last_student_message(cid):
    """Remove the just-submitted student turn when no tutor request was successfully completed.

    This keeps a failed billing/network request from becoming part of future tutor context.
    The student's earlier conversation remains untouched.
    """
    storage.delete_last_student_message(cid, st.session_state.student_id, now())

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
    return storage.usage_summary(
        student_id=student_id,
        since=since.isoformat() if since else None,
    )

def student_message_count(cid):
    return storage.student_message_count(cid, st.session_state.student_id)

def check_message_size(cid, user_text):
    if len(user_text) > MAX_STUDENT_MESSAGE_CHARS:
        return False, (
            f"That message is too long for the beta. Please shorten it to "
            f"{MAX_STUDENT_MESSAGE_CHARS:,} characters or fewer."
        )
    existing_chars = sum(len(message["content"]) for message in load_messages(cid))
    if existing_chars + len(user_text) > MAX_CONVERSATION_CHARS:
        return False, (
            "This thread has reached the beta's overall length limit. "
            "Download the transcript and start a new conversation to continue."
        )
    return True, None

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
    storage.record_usage(
        usage_id="usage_" + uuid.uuid4().hex,
        student_id=st.session_state.student_id,
        conversation_id=cid,
        request_kind=request_kind,
        model_name=MODEL,
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        output_tokens=output_tokens,
        estimated_cost_usd=cost,
        created_at=now(),
    )

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
            # Conversation history is stored only in the course database.
            # Do not create persistent application state in the OpenAI API.
            store=False,
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
                f"{APP_NAME} is temporarily unavailable because the beta's API usage allowance "
                "has been exhausted. Your conversation is saved; please try again after the "
                "instructor restores the allowance."
            )
        return None, f"{APP_NAME} could not complete that request. Please try again."
    record_usage(response, cid, request_kind)
    return response.output_text, None

def submit_student_message(cid, conv, user_text):
    """Validate, send, and persist one student turn without leaving partial state."""
    limit_ok, limit_message = check_usage_limits(cid)
    if not limit_ok:
        return False, limit_message
    size_ok, size_message = check_message_size(cid, user_text)
    if not size_ok:
        return False, size_message

    save_message(cid, "student", user_text)
    messages = load_messages(cid)
    api_messages = [
        {
            "role": "user" if message["role"] == "student" else "assistant",
            "content": message["content"],
        }
        for message in messages
    ]
    with st.spinner(f"{APP_NAME} is thinking..."):
        answer, error = call_tutor(
            cid=cid,
            instructions=instructions_for(conv),
            input_value=api_messages,
            request_kind="dialogue",
        )
    if answer:
        save_message(cid, "assistant", answer)
        st.session_state.pop("beta_failed_message", None)
        st.session_state.pop("beta_failed_conversation", None)
        return True, None

    # Anna did not process this turn successfully. Remove it from the permanent
    # transcript but retain a session-only copy so the student can retry.
    delete_last_student_message(cid)
    st.session_state["beta_failed_message"] = user_text
    st.session_state["beta_failed_conversation"] = cid
    return False, error or f"{APP_NAME} could not complete that request."

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
    <div style="
        background: linear-gradient(105deg, #782F40 0%, #672736 72%, #54202C 100%);
        border-bottom: 5px solid #CEB888;
        border-radius: 10px;
        padding: 1.15rem 1.4rem 1.05rem 1.4rem;
        margin: 0 0 1.25rem 0;
        box-shadow: 0 3px 10px rgba(70,30,40,.10);
    ">
        <div style="
            font-size: 2.25rem;
            font-weight: 720;
            color: white;
            line-height: 1.08;
            letter-spacing: -0.025em;
        ">
            {APP_NAME}
        </div>
        <div style="
            font-size: 1rem;
            color: #F1E5D2;
            margin-top: 0.42rem;
            letter-spacing: 0.01em;
        ">
            Undergraduate Topology
            <span style="color:#CEB888; padding:0 .45rem;">◆</span>
            Florida State University
            <span style="opacity:.78;"> · Beta</span>
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
        st.markdown("<div style=\"border-left:4px solid #782F40; padding-left:.65rem; margin-top:1rem;\"><strong style=\"color:#782F40;\">Question</strong></div>", unsafe_allow_html=True)
        st.markdown(selected_problem["statement"])
    elif mode == "Conversations":
        conversation_options = {a["title"]: a for a in activities}
        conversation_name = st.selectbox("Conversation", list(conversation_options))
        selected_activity = conversation_options[conversation_name]
        st.markdown("<div style=\"border-left:4px solid #782F40; padding-left:.65rem; margin-top:1rem;\"><strong style=\"color:#782F40;\">Conversation prompt</strong></div>", unsafe_allow_html=True)
        st.markdown(selected_activity["statement"])
        if selected_activity.get("deliverable"):
            st.markdown("<div style=\"border-left:4px solid #CEB888; padding-left:.65rem; margin-top:1rem;\"><strong style=\"color:#5B2430;\">Deliverable</strong></div>", unsafe_allow_html=True)
            st.markdown(selected_activity["deliverable"])
    else:
        st.caption("Start a discussion about anything from the course.")

    with st.expander("How to use Anna"):
        st.write("Use Anna naturally, as you would use office hours for the course. For assigned work, you are responsible for writing the final proof or exposition yourself. This is a beta: please report moments that feel especially helpful, frustrating, too easy, or overly guided.")

    with st.expander("Beta feedback"):
        st.caption("Feedback is linked only to your pseudonymous tester code.")
        helpfulness = st.slider("How helpful was Anna?", 1, 5, 3)
        frustration = st.slider("How frustrating was the interaction?", 1, 5, 1)
        too_much = st.slider("How often did it give too much away?", 1, 5, 1)
        unnecessary = st.slider("How often did it make you do unnecessary work after you understood?", 1, 5, 1)
        comments = st.text_area("Anything else?", placeholder="A particular moment, suggestion, or problem...")
        if st.button("Submit feedback"):
            storage.save_feedback(
                feedback_id="feedback_" + uuid.uuid4().hex,
                student_id=st.session_state.student_id,
                conversation_id=st.session_state.get("active_conversation"),
                helpfulness=helpfulness,
                frustration=frustration,
                too_much=too_much,
                unnecessary_work=unnecessary,
                comments=comments,
                created_at=now(),
            )
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
            prior = storage.latest_activity_conversation(
                st.session_state.student_id, selected_activity["id"]
            )
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
        else:
            # An assigned conversation may have just received its opening message.
            # Refresh metadata so the exported last-updated time is accurate.
            conv = get_conversation(cid)
        messages = load_messages(cid)
        st.download_button(
            "⬇ Download transcript",
            data=render_transcript(conv, messages),
            file_name=transcript_filename(conv),
            mime="text/markdown",
            help="Download this conversation for your records or assignment submission.",
        )
        for m in messages:
            with st.chat_message("user" if m["role"] == "student" else "assistant"):
                st.markdown(m["content"])

        failed_message = (
            st.session_state.get("beta_failed_message")
            if st.session_state.get("beta_failed_conversation") == cid
            else None
        )
        if failed_message:
            st.warning("Your last message was not sent. You can retry it without retyping it.")
            with st.expander("Show unsent message"):
                st.markdown(failed_message)
            retry_col, discard_col = st.columns(2)
            if retry_col.button("Retry last message", use_container_width=True):
                sent, error = submit_student_message(cid, conv, failed_message)
                if error:
                    st.session_state["beta_last_error"] = error
                st.rerun()
            if discard_col.button("Discard unsent message", use_container_width=True):
                st.session_state.pop("beta_failed_message", None)
                st.session_state.pop("beta_failed_conversation", None)
                st.rerun()

        limit_ok, limit_message = check_usage_limits(cid)
        if not limit_ok:
            st.warning(limit_message)
        user_text = st.chat_input(f"Message {APP_NAME}", disabled=not limit_ok)
        if user_text:
            sent, error = submit_student_message(cid, conv, user_text)
            if error:
                st.session_state["beta_last_error"] = error
            st.rerun()
    else:
        st.info("Choose a homework problem, open a saved conversation, or start a freeform discussion.")
