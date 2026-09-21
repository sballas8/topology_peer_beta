"""Persistence interface for the Topology AI Tutor.

The Streamlit application depends on this class rather than issuing SQL
directly.  A future PostgreSQL implementation can provide the same methods
without changing the user interface or tutoring logic.
"""

from pathlib import Path
import sqlite3


class SQLiteStorage:
    def __init__(self, database_path, schema_path, timeout=30):
        self.database_path = Path(database_path)
        self.schema_path = Path(schema_path)
        self.timeout = timeout

    def _connect(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=self.timeout)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _dict(row):
        return dict(row) if row is not None else None

    def initialize(self, tutor_version, prompt_text, model_name, created_at):
        with self._connect() as connection:
            connection.executescript(self.schema_path.read_text(encoding="utf-8"))
            connection.execute(
                """INSERT OR IGNORE INTO tutor_versions
                   (tutor_version,prompt_text,model_name,created_at)
                   VALUES (?,?,?,?)""",
                (tutor_version, prompt_text, model_name, created_at),
            )

    def ensure_student(self, student_id, created_at):
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO students(student_id,created_at) VALUES (?,?)",
                (student_id, created_at),
            )

    def create_conversation(
        self,
        *,
        conversation_id,
        student_id,
        title,
        workspace,
        homework_id,
        problem_id,
        activity_id,
        tutor_version,
        created_at,
    ):
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO conversations
                   (conversation_id,student_id,title,workspace,homework_id,problem_id,
                    activity_id,tutor_version,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    conversation_id,
                    student_id,
                    title,
                    workspace,
                    homework_id,
                    problem_id,
                    activity_id,
                    tutor_version,
                    created_at,
                    created_at,
                ),
            )

    def get_conversation(self, conversation_id, student_id):
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM conversations
                   WHERE conversation_id=? AND student_id=?""",
                (conversation_id, student_id),
            ).fetchone()
        return self._dict(row)

    def latest_activity_conversation(self, student_id, activity_id):
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM conversations
                   WHERE student_id=? AND workspace='activity' AND activity_id=?
                   ORDER BY updated_at DESC LIMIT 1""",
                (student_id, activity_id),
            ).fetchone()
        return self._dict(row)

    def load_messages(self, conversation_id, student_id):
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT messages.* FROM messages
                   JOIN conversations
                     ON conversations.conversation_id=messages.conversation_id
                   WHERE messages.conversation_id=? AND conversations.student_id=?
                   ORDER BY messages.sequence_number""",
                (conversation_id, student_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_message(
        self,
        *,
        message_id,
        conversation_id,
        student_id,
        role,
        content,
        created_at,
    ):
        with self._connect() as connection:
            # Serialize sequence-number allocation for SQLite.  A PostgreSQL
            # backend can implement this with its own transaction strategy.
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                """SELECT 1 FROM conversations
                   WHERE conversation_id=? AND student_id=?""",
                (conversation_id, student_id),
            ).fetchone()
            if owner is None:
                raise PermissionError("Conversation does not belong to the active student.")
            sequence_number = connection.execute(
                """SELECT COALESCE(MAX(sequence_number),0)+1
                   FROM messages WHERE conversation_id=?""",
                (conversation_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO messages
                   (message_id,conversation_id,sequence_number,role,content,created_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    message_id,
                    conversation_id,
                    sequence_number,
                    role,
                    content,
                    created_at,
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at=? WHERE conversation_id=?",
                (created_at, conversation_id),
            )

    def delete_last_student_message(self, conversation_id, student_id, updated_at):
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT messages.message_id FROM messages
                   JOIN conversations
                     ON conversations.conversation_id=messages.conversation_id
                   WHERE messages.conversation_id=?
                     AND conversations.student_id=?
                     AND messages.role='student'
                   ORDER BY messages.sequence_number DESC LIMIT 1""",
                (conversation_id, student_id),
            ).fetchone()
            if row:
                connection.execute(
                    "DELETE FROM messages WHERE message_id=?", (row["message_id"],)
                )
                connection.execute(
                    "UPDATE conversations SET updated_at=? WHERE conversation_id=?",
                    (updated_at, conversation_id),
                )

    def usage_summary(self, student_id=None, since=None):
        clauses, args = [], []
        if student_id:
            clauses.append("student_id=?")
            args.append(student_id)
        if since:
            clauses.append("created_at>=?")
            args.append(since)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as connection:
            row = connection.execute(
                f"""SELECT COUNT(*) calls,
                           COALESCE(SUM(estimated_cost_usd),0) cost
                    FROM usage_events{where}""",
                args,
            ).fetchone()
        return self._dict(row)

    def student_message_count(self, conversation_id, student_id):
        with self._connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) FROM messages
                   JOIN conversations
                     ON conversations.conversation_id=messages.conversation_id
                   WHERE messages.conversation_id=?
                     AND conversations.student_id=?
                     AND messages.role='student'""",
                (conversation_id, student_id),
            ).fetchone()
        return row[0]

    def record_usage(
        self,
        *,
        usage_id,
        student_id,
        conversation_id,
        request_kind,
        model_name,
        input_tokens,
        cached_input_tokens,
        output_tokens,
        estimated_cost_usd,
        created_at,
    ):
        with self._connect() as connection:
            if conversation_id is not None:
                owner = connection.execute(
                    """SELECT 1 FROM conversations
                       WHERE conversation_id=? AND student_id=?""",
                    (conversation_id, student_id),
                ).fetchone()
                if owner is None:
                    raise PermissionError(
                        "Conversation does not belong to the active student."
                    )
            connection.execute(
                """INSERT INTO usage_events
                   (usage_id,student_id,conversation_id,request_kind,model_name,
                    input_tokens,cached_input_tokens,output_tokens,
                    estimated_cost_usd,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    usage_id,
                    student_id,
                    conversation_id,
                    request_kind,
                    model_name,
                    input_tokens,
                    cached_input_tokens,
                    output_tokens,
                    estimated_cost_usd,
                    created_at,
                ),
            )

    def save_feedback(
        self,
        *,
        feedback_id,
        student_id,
        conversation_id,
        helpfulness,
        frustration,
        too_much,
        unnecessary_work,
        comments,
        created_at,
    ):
        with self._connect() as connection:
            if conversation_id is not None:
                owner = connection.execute(
                    """SELECT 1 FROM conversations
                       WHERE conversation_id=? AND student_id=?""",
                    (conversation_id, student_id),
                ).fetchone()
                if owner is None:
                    raise PermissionError(
                        "Conversation does not belong to the active student."
                    )
            connection.execute(
                """INSERT INTO feedback
                   (feedback_id,student_id,conversation_id,helpfulness,frustration,
                    too_much,unnecessary_work,comments,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    feedback_id,
                    student_id,
                    conversation_id,
                    helpfulness,
                    frustration,
                    too_much,
                    unnecessary_work,
                    comments,
                    created_at,
                ),
            )
