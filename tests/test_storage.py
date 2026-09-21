import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage import SQLiteStorage


TEST_SCHEMA = """
CREATE TABLE tutor_versions (
    tutor_version TEXT PRIMARY KEY,
    prompt_text TEXT,
    model_name TEXT,
    created_at TEXT
);
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    created_at TEXT
);
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    title TEXT,
    workspace TEXT,
    homework_id TEXT,
    problem_id TEXT,
    activity_id TEXT,
    tutor_version TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    sequence_number INTEGER,
    role TEXT,
    content TEXT,
    created_at TEXT,
    UNIQUE(conversation_id, sequence_number)
);
CREATE TABLE usage_events (
    usage_id TEXT PRIMARY KEY,
    student_id TEXT,
    conversation_id TEXT,
    request_kind TEXT,
    model_name TEXT,
    input_tokens INTEGER,
    cached_input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost_usd REAL,
    created_at TEXT
);
CREATE TABLE feedback (
    feedback_id TEXT PRIMARY KEY,
    student_id TEXT,
    conversation_id TEXT,
    helpfulness INTEGER,
    frustration INTEGER,
    too_much INTEGER,
    unnecessary_work INTEGER,
    comments TEXT,
    created_at TEXT
);
"""


class StorageOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        schema_path = root / "schema.sql"
        schema_path.write_text(TEST_SCHEMA, encoding="utf-8")
        self.storage = SQLiteStorage(root / "test.db", schema_path)
        self.storage.initialize("v1", "prompt", "model", "2026-01-01T00:00:00+00:00")
        self.storage.ensure_student("alice", "2026-01-01T00:00:00+00:00")
        self.storage.ensure_student("bob", "2026-01-01T00:00:00+00:00")
        self.storage.create_conversation(
            conversation_id="alice-conversation",
            student_id="alice",
            title="Alice's work",
            workspace="activity",
            homework_id=None,
            problem_id=None,
            activity_id="activity-1",
            tutor_version="v1",
            created_at="2026-01-01T00:00:00+00:00",
        )
        self.storage.save_message(
            message_id="alice-message",
            conversation_id="alice-conversation",
            student_id="alice",
            role="student",
            content="Alice's private attempt",
            created_at="2026-01-01T00:01:00+00:00",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_owner_can_read_conversation_and_messages(self):
        conversation = self.storage.get_conversation("alice-conversation", "alice")
        self.assertEqual(conversation["title"], "Alice's work")
        messages = self.storage.load_messages("alice-conversation", "alice")
        self.assertEqual([m["content"] for m in messages], ["Alice's private attempt"])

    def test_other_student_cannot_read_conversation_or_messages(self):
        self.assertIsNone(
            self.storage.get_conversation("alice-conversation", "bob")
        )
        self.assertEqual(
            self.storage.load_messages("alice-conversation", "bob"), []
        )
        self.assertEqual(
            self.storage.student_message_count("alice-conversation", "bob"), 0
        )

    def test_other_student_cannot_append_message(self):
        with self.assertRaises(PermissionError):
            self.storage.save_message(
                message_id="intruding-message",
                conversation_id="alice-conversation",
                student_id="bob",
                role="student",
                content="Intrusion",
                created_at="2026-01-01T00:02:00+00:00",
            )
        messages = self.storage.load_messages("alice-conversation", "alice")
        self.assertEqual(len(messages), 1)

    def test_other_student_cannot_delete_message(self):
        self.storage.delete_last_student_message(
            "alice-conversation", "bob", "2026-01-01T00:02:00+00:00"
        )
        messages = self.storage.load_messages("alice-conversation", "alice")
        self.assertEqual(len(messages), 1)

    def test_activity_lookup_is_scoped_to_owner(self):
        self.assertIsNotNone(
            self.storage.latest_activity_conversation("alice", "activity-1")
        )
        self.assertIsNone(
            self.storage.latest_activity_conversation("bob", "activity-1")
        )

    def test_other_student_cannot_attach_usage_to_conversation(self):
        with self.assertRaises(PermissionError):
            self.storage.record_usage(
                usage_id="intruding-usage",
                student_id="bob",
                conversation_id="alice-conversation",
                request_kind="dialogue",
                model_name="model",
                input_tokens=1,
                cached_input_tokens=0,
                output_tokens=1,
                estimated_cost_usd=0.01,
                created_at="2026-01-01T00:02:00+00:00",
            )

    def test_other_student_cannot_attach_feedback_to_conversation(self):
        with self.assertRaises(PermissionError):
            self.storage.save_feedback(
                feedback_id="intruding-feedback",
                student_id="bob",
                conversation_id="alice-conversation",
                helpfulness=1,
                frustration=1,
                too_much=1,
                unnecessary_work=1,
                comments="Intrusion",
                created_at="2026-01-01T00:02:00+00:00",
            )


if __name__ == "__main__":
    unittest.main()
