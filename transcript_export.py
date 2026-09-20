from pathlib import Path
import argparse
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
DB = ROOT / "course" / "conversations" / "conversations.db"
EXPORTS = ROOT / "exports"


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")


def copy_database(source: Path, destination: Path):
    """Make a consistent SQLite snapshot even if the app is open."""
    src = sqlite3.connect(source)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def export(include_synthetic=False):
    if not DB.exists():
        raise SystemExit(f"Conversation database not found: {DB}")

    EXPORTS.mkdir(exist_ok=True)
    stamp = utc_stamp()
    work = EXPORTS / f"topology-peer-transcripts-{stamp}"
    work.mkdir()

    db_copy = work / "conversations.db"
    copy_database(DB, db_copy)

    con = sqlite3.connect(db_copy)
    con.row_factory = sqlite3.Row

    where = "" if include_synthetic else "WHERE c.conversation_id NOT LIKE 'synthetic_%'"
    conversations = con.execute(f"""
        SELECT c.* FROM conversations c
        {where}
        ORDER BY c.created_at, c.conversation_id
    """).fetchall()

    tutor_versions = {
        r["tutor_version"]: dict(r)
        for r in con.execute("SELECT * FROM tutor_versions ORDER BY created_at").fetchall()
    }

    jsonl_path = work / "transcripts.jsonl"
    txt_path = work / "transcripts.txt"

    with jsonl_path.open("w", encoding="utf-8") as jf, txt_path.open("w", encoding="utf-8") as tf:
        for c in conversations:
            messages = [dict(r) for r in con.execute(
                "SELECT sequence_number,role,content,created_at FROM messages WHERE conversation_id=? ORDER BY sequence_number",
                (c["conversation_id"],),
            ).fetchall()]
            record = dict(c)
            record["messages"] = messages
            record["tutor"] = tutor_versions.get(c["tutor_version"])
            jf.write(json.dumps(record, ensure_ascii=False) + "\n")

            tf.write("=" * 78 + "\n")
            tf.write(f"{c['title']}\n")
            tf.write(f"conversation_id: {c['conversation_id']}\n")
            tf.write(f"student_id: {c['student_id']}\n")
            tf.write(f"workspace: {c['workspace']}\n")
            if c["homework_id"]:
                tf.write(f"homework_id: {c['homework_id']}\n")
            if c["problem_id"]:
                tf.write(f"problem_id: {c['problem_id']}\n")
            if "activity_id" in c.keys() and c["activity_id"]:
                tf.write(f"activity_id: {c['activity_id']}\n")
            tf.write(f"tutor_version: {c['tutor_version']}\n")
            tf.write(f"created_at: {c['created_at']}\n\n")
            for m in messages:
                speaker = "STUDENT" if m["role"] == "student" else "TOPOLOGY PEER"
                tf.write(f"[{speaker}]\n{m['content']}\n\n")

    manifest = {
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "conversation_count": len(conversations),
        "include_synthetic": include_synthetic,
        "files": {
            "conversations.db": "Consistent SQLite snapshot for systematic querying.",
            "transcripts.jsonl": "One JSON object per conversation, including ordered messages and tutor-version metadata.",
            "transcripts.txt": "Human-readable rendering of the same conversations.",
        },
        "privacy_note": "Student IDs are whatever pseudonymous IDs are stored by the app. Message text is not automatically redacted and may contain information typed by students.",
    }
    (work / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    con.close()

    zip_path = EXPORTS / f"topology-peer-transcripts-{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(work.iterdir()):
            z.write(p, arcname=p.name)
    shutil.rmtree(work)

    print(zip_path.relative_to(ROOT))
    print(f"Exported {len(conversations)} conversations.")
    if not include_synthetic:
        print("Synthetic archive-harness conversations were excluded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Topology Peer transcripts for review.")
    parser.add_argument("command", choices=["export"])
    parser.add_argument("--include-synthetic", action="store_true",
                        help="Include archive-harness synthetic conversations.")
    args = parser.parse_args()
    if args.command == "export":
        export(include_synthetic=args.include_synthetic)
