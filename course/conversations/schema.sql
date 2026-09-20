PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tutor_versions (tutor_version TEXT PRIMARY KEY, prompt_text TEXT NOT NULL, model_name TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
 conversation_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, title TEXT NOT NULL,
 workspace TEXT NOT NULL CHECK (workspace IN ('homework','activity','freeform')),
 homework_id TEXT, problem_id TEXT, activity_id TEXT, tutor_version TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(student_id) REFERENCES students(student_id), FOREIGN KEY(tutor_version) REFERENCES tutor_versions(tutor_version));
CREATE TABLE IF NOT EXISTS messages (message_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, sequence_number INTEGER NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','assistant')), content TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(conversation_id,sequence_number), FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id));
CREATE TABLE IF NOT EXISTS usage_events (
 usage_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, conversation_id TEXT,
 request_kind TEXT NOT NULL, model_name TEXT NOT NULL,
 input_tokens INTEGER NOT NULL DEFAULT 0, cached_input_tokens INTEGER NOT NULL DEFAULT 0,
 output_tokens INTEGER NOT NULL DEFAULT 0, estimated_cost_usd REAL NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,
 FOREIGN KEY(student_id) REFERENCES students(student_id));
CREATE TABLE IF NOT EXISTS feedback (
 feedback_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, conversation_id TEXT,
 helpfulness INTEGER, frustration INTEGER, too_much INTEGER, unnecessary_work INTEGER,
 comments TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(student_id) REFERENCES students(student_id));
CREATE INDEX IF NOT EXISTS idx_conversations_student ON conversations(student_id);
CREATE INDEX IF NOT EXISTS idx_conversations_homework_problem ON conversations(homework_id,problem_id);
CREATE INDEX IF NOT EXISTS idx_conversations_activity ON conversations(activity_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_sequence ON messages(conversation_id,sequence_number);
CREATE INDEX IF NOT EXISTS idx_usage_student_created ON usage_events(student_id,created_at);
CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_events(created_at);
