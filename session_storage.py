"""Per-browser-session storage. No SQLite, files, or shared process cache."""
import streamlit as st

class SessionStorage:
    def _state(self):
        if "anna_data" not in st.session_state:
            st.session_state.anna_data = {"conversations": {}, "messages": {}, "usage": []}
        return st.session_state.anna_data

    def ensure_student(self, student_id, created_at):
        self._state()

    def create_conversation(self, *, conversation_id, student_id, title, workspace,
                            homework_id, problem_id, activity_id, tutor_version, created_at):
        d = self._state()
        d["conversations"][conversation_id] = dict(conversation_id=conversation_id,
            student_id=student_id, title=title, workspace=workspace, homework_id=homework_id,
            problem_id=problem_id, activity_id=activity_id, tutor_version=tutor_version,
            created_at=created_at, updated_at=created_at)
        d["messages"][conversation_id] = []

    def get_conversation(self, conversation_id, student_id):
        c = self._state()["conversations"].get(conversation_id)
        return dict(c) if c and c["student_id"] == student_id else None

    def latest_activity_conversation(self, student_id, activity_id):
        cs = [c for c in self._state()["conversations"].values()
              if c["student_id"] == student_id and c["workspace"] == "activity" and c["activity_id"] == activity_id]
        return dict(max(cs, key=lambda c: c["updated_at"])) if cs else None

    def load_messages(self, conversation_id, student_id):
        if not self.get_conversation(conversation_id, student_id):
            return []
        return [dict(m) for m in self._state()["messages"][conversation_id]]

    def save_message(self, *, message_id, conversation_id, student_id, role, content, created_at):
        c = self.get_conversation(conversation_id, student_id)
        if not c:
            raise PermissionError("Conversation does not belong to the active session")
        d = self._state()
        d["messages"][conversation_id].append(dict(message_id=message_id, role=role,
            content=content, created_at=created_at))
        d["conversations"][conversation_id]["updated_at"] = created_at

    def delete_last_student_message(self, conversation_id, student_id, updated_at):
        if not self.get_conversation(conversation_id, student_id):
            return
        d = self._state()
        ms = d["messages"][conversation_id]
        for i in range(len(ms)-1, -1, -1):
            if ms[i]["role"] == "student":
                ms.pop(i)
                break
        d["conversations"][conversation_id]["updated_at"] = updated_at

    def student_message_count(self, conversation_id, student_id):
        return sum(m["role"] == "student" for m in self.load_messages(conversation_id, student_id))

    def record_usage(self, **kwargs):
        self._state()["usage"].append(kwargs)

    def usage_summary(self, student_id=None, since=None):
        events = self._state()["usage"]
        events = [e for e in events if (not student_id or e["student_id"] == student_id)
                  and (not since or e["created_at"] >= since)]
        return {"calls": len(events), "cost": sum(e["estimated_cost_usd"] for e in events)}
