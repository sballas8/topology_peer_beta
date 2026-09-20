from pathlib import Path
import sqlite3
import uuid
import random
import argparse
from datetime import datetime, timedelta, timezone
from collections import Counter

ROOT = Path(__file__).resolve().parent
DB = ROOT / "course" / "conversations" / "conversations.db"
FAKE_PREFIX = "synthetic_"

TOPICS = {
    ("hw01", "p1", "Homework 1, Problem 1"): [
        ("I am trying to check the topology axioms. I think arbitrary unions are the easy part.", "Good. Which axiom needs the most care in your example, and what feature of your collection handles it?"),
        ("I forgot that the empty set has to be included.", "Right. Rather than just adding it mechanically, check why both the empty set and the whole space are required by the definition."),
    ],
    ("hw01", "p2", "Homework 1, Problem 2"): [
        ("I think the bounded metric and usual metric give the same topology.", "Compare sufficiently small balls first. What happens when the radius is less than 1?"),
        ("The small balls are identical, so locally the metrics see the same neighborhoods.", "Exactly. Now turn that local observation into a statement about open sets in both directions."),
    ],
    ("hw01", "p3", "Homework 1, Problem 3"): [
        ("I can prove continuity with epsilon delta but I do not see the open set version.", "Start with an open interval in the codomain and compute its inverse image under the affine map."),
        ("The inverse image of an interval is another interval.", "Good. Now explain why that reflects the same local control that appears in the epsilon-delta proof."),
    ],
    ("hw02", "p1", "Homework 2, Problem 1"): [
        ("A union of basis elements should be open, but I still need the topology axioms.", "Yes. For finite intersections, take a point in the intersection and use the basis intersection property near that point."),
        ("I am stuck on intersections of two huge unions.", "Do not manipulate the whole unions at once. Fix one point in their intersection and ask which two basis elements contain it."),
    ],
    ("hw02", "p2", "Homework 2, Problem 2"): [
        ("I think rational endpoint intervals form a basis because rationals are dense.", "Density is the key ingredient. Can you use it to fit a rational-endpoint interval around a point inside an arbitrary open interval?"),
        ("If x is in (a,b), I can choose rationals r and s with a<r<x<s<b.", "Exactly. That produces the required basis element locally around x."),
    ],
    ("hw02", "p3", "Homework 2, Problem 3"): [
        ("I got the inclusion backwards for the identity map.", "Use the codomain topology to decide which open sets continuity asks you to pull back."),
        ("If U is T2-open then its inverse image is U, so U must be T1-open.", "Right. That gives T2 contained in T1."),
    ],
    ("hw02", "p4", "Homework 2, Problem 4"): [
        ("Why is it enough to check inverse images of basis elements?", "Because every open set is a union of basis elements and inverse images commute with arbitrary unions. Can you assemble those two facts?"),
        ("So f inverse of a union is the union of the inverse images.", "Yes. If each basis-element inverse image is open, what follows for the inverse image of an arbitrary open set?"),
    ],
}

FREEFORM = [
    ("Compactness", [
        ("Why is compactness useful beyond the definition with open covers?", "A recurring theme is that compactness converts local information into finite global information. Where might finiteness help in an argument?"),
        ("Maybe I can take a maximum over finitely many choices.", "Exactly. That mechanism underlies many uniformity arguments on compact spaces."),
    ]),
    ("Connectedness", [
        ("Is connectedness the same as path connectedness?", "Path connectedness is stronger. A path gives an explicit continuous route; connectedness only rules out a separation."),
        ("So connected does not necessarily give me paths.", "Correct. Later it is useful to have examples that make that distinction concrete."),
    ]),
    ("Closure", [
        ("I keep mixing up closure points and limit points.", "Try comparing the definitions at a point that is isolated but belongs to the set. What happens there?"),
        ("An isolated point is in the closure but need not be a limit point.", "Good. That example isolates the distinction cleanly."),
    ]),
    ("Product topology", [
        ("Why do basic open sets in a product only restrict finitely many coordinates?", "That finite-support feature is what makes coordinate projections continuous without making the topology unnecessarily fine."),
        ("So infinitely many simultaneous restrictions would usually make a smaller neighborhood.", "Yes, and allowing those as basic opens generally produces a finer topology."),
    ]),
]

def now_iso(dt):
    return dt.astimezone(timezone.utc).isoformat()

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c

def clear():
    with connect() as con:
        ids = [r[0] for r in con.execute(
            "SELECT conversation_id FROM conversations WHERE conversation_id LIKE ?",
            (FAKE_PREFIX + "%",)
        )]
        for cid in ids:
            con.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
            con.execute("DELETE FROM conversations WHERE conversation_id=?", (cid,))
        con.execute("DELETE FROM students WHERE student_id LIKE ?", (FAKE_PREFIX + "%",))
    print(f"Removed {len(ids)} synthetic conversations.")

def generate(students=20, conversations=120, seed=2027):
    random.seed(seed)
    clear()
    base = datetime.now(timezone.utc) - timedelta(days=90)
    student_ids = [f"{FAKE_PREFIX}student_{i:03d}" for i in range(1, students + 1)]

    with connect() as con:
        for i, sid in enumerate(student_ids):
            con.execute("INSERT OR IGNORE INTO students(student_id,created_at) VALUES (?,?)",
                        (sid, now_iso(base + timedelta(hours=i))))

        for n in range(conversations):
            sid = random.choice(student_ids)
            is_homework = random.random() < 0.78
            cid = f"{FAKE_PREFIX}conv_{uuid.uuid4().hex[:16]}"
            start = base + timedelta(
                days=random.randint(0, 84),
                hours=random.randint(8, 22),
                minutes=random.randint(0, 59)
            )

            if is_homework:
                hw, prob, title = random.choice(list(TOPICS.keys()))
                pairs = TOPICS[(hw, prob, title)]
                workspace = "homework"
            else:
                topic, pairs = random.choice(FREEFORM)
                title = f"Freeform: {topic}"
                hw = prob = None
                workspace = "freeform"

            # 1–3 conceptual exchange pairs, with occasional repeated/rephrased student turns.
            chosen = [random.choice(pairs) for _ in range(random.randint(1, 3))]
            msgs = []
            for student_text, tutor_text in chosen:
                msgs.append(("student", student_text))
                msgs.append(("assistant", tutor_text))
                if random.random() < 0.18:
                    msgs.append(("student", "I am still not seeing the connection. Can you explain that idea another way?"))
                    msgs.append(("assistant", "Yes. Focus on the mathematical object immediately in front of you and say what the definition requires at one point. Then we can rebuild the global statement from that."))

            end = start + timedelta(minutes=2 * len(msgs))
            con.execute("""INSERT INTO conversations
                (conversation_id,student_id,title,workspace,homework_id,problem_id,
                 tutor_version,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (cid, sid, title, workspace, hw, prob, "1.0", now_iso(start), now_iso(end)))

            for seq, (role, content) in enumerate(msgs, 1):
                mt = start + timedelta(minutes=2 * (seq - 1))
                con.execute("""INSERT INTO messages
                    (message_id,conversation_id,sequence_number,role,content,created_at)
                    VALUES (?,?,?,?,?,?)""",
                    (f"{FAKE_PREFIX}msg_{uuid.uuid4().hex[:18]}", cid, seq, role, content, now_iso(mt)))

    print(f"Generated {conversations} synthetic conversations across {students} pseudonymous students.")
    print("Run the 'report' command to see whether the archive is useful.")

def report():
    with connect() as con:
        conv_count = con.execute(
            "SELECT COUNT(*) FROM conversations WHERE conversation_id LIKE ?",
            (FAKE_PREFIX + "%",)).fetchone()[0]
        student_count = con.execute(
            "SELECT COUNT(DISTINCT student_id) FROM conversations WHERE conversation_id LIKE ?",
            (FAKE_PREFIX + "%",)).fetchone()[0]
        msg_count = con.execute(
            """SELECT COUNT(*) FROM messages m JOIN conversations c USING(conversation_id)
               WHERE c.conversation_id LIKE ?""", (FAKE_PREFIX + "%",)).fetchone()[0]
        workspaces = con.execute(
            """SELECT workspace, COUNT(*) n FROM conversations
               WHERE conversation_id LIKE ? GROUP BY workspace""",
            (FAKE_PREFIX + "%",)).fetchall()
        problems = con.execute(
            """SELECT homework_id, problem_id, COUNT(*) n FROM conversations
               WHERE conversation_id LIKE ? AND workspace='homework'
               GROUP BY homework_id,problem_id ORDER BY homework_id,problem_id""",
            (FAKE_PREFIX + "%",)).fetchall()
        versions = con.execute(
            """SELECT tutor_version, COUNT(*) n FROM conversations
               WHERE conversation_id LIKE ? GROUP BY tutor_version""",
            (FAKE_PREFIX + "%",)).fetchall()

        print("\nSYNTHETIC ARCHIVE REPORT")
        print("=" * 72)
        print(f"Pseudonymous students: {student_count}")
        print(f"Conversations:          {conv_count}")
        print(f"Messages:               {msg_count}")
        print("\nBy workspace:")
        for r in workspaces:
            print(f"  {r['workspace']:<12} {r['n']}")
        print("\nHomework/problem coverage:")
        for r in problems:
            print(f"  {r['homework_id']} / {r['problem_id']}: {r['n']} conversations")
        print("\nTutor versions:")
        for r in versions:
            print(f"  {r['tutor_version']}: {r['n']} conversations")

        print("\nEXAMPLE RESEARCH QUERIES")
        print("-" * 72)
        for term in ["compact", "basis", "identity", "stuck"]:
            rows = con.execute(
                """SELECT c.student_id,c.title,m.role,m.content
                   FROM messages m JOIN conversations c USING(conversation_id)
                   WHERE c.conversation_id LIKE ? AND lower(m.content) LIKE ?
                   LIMIT 3""",
                (FAKE_PREFIX + "%", f"%{term}%")).fetchall()
            print(f'\nSearch "{term}" -> {len(rows)} sample hits')
            for r in rows:
                snippet = r["content"].replace("\n", " ")
                print(f"  {r['student_id']} | {r['title']} | {r['role']}: {snippet[:115]}")

        print("\nOne student's longitudinal record:")
        sid_row = con.execute(
            """SELECT student_id, COUNT(*) n FROM conversations
               WHERE conversation_id LIKE ? GROUP BY student_id
               ORDER BY n DESC LIMIT 1""", (FAKE_PREFIX + "%",)).fetchone()
        if sid_row:
            print(f"  {sid_row['student_id']} ({sid_row['n']} conversations)")
            for r in con.execute(
                """SELECT created_at,title,workspace,homework_id,problem_id
                   FROM conversations WHERE student_id=? ORDER BY created_at""",
                (sid_row["student_id"],)):
                print(f"    {r['created_at'][:10]} | {r['title']} | {r['workspace']}")

def test():
    checks = []
    with connect() as con:
        convs = con.execute(
            "SELECT * FROM conversations WHERE conversation_id LIKE ?",
            (FAKE_PREFIX + "%",)).fetchall()
        checks.append(("Synthetic conversations exist", len(convs) > 0))
        checks.append(("Pseudonymous students exist",
                       con.execute("SELECT COUNT(*) FROM students WHERE student_id LIKE ?",
                                   (FAKE_PREFIX + "%",)).fetchone()[0] > 0))
        checks.append(("Homework metadata preserved",
                       any(r["workspace"] == "homework" and r["homework_id"] and r["problem_id"] for r in convs)))
        checks.append(("Freeform metadata preserved",
                       any(r["workspace"] == "freeform" and r["homework_id"] is None for r in convs)))
        checks.append(("Tutor version preserved",
                       all(bool(r["tutor_version"]) for r in convs)))
        bad_order = 0
        for r in convs:
            seq = [x[0] for x in con.execute(
                "SELECT sequence_number FROM messages WHERE conversation_id=? ORDER BY sequence_number",
                (r["conversation_id"],))]
            if seq != list(range(1, len(seq)+1)):
                bad_order += 1
        checks.append(("Message ordering intact", bad_order == 0))
        checks.append(("Searchable text present",
                       con.execute("""SELECT COUNT(*) FROM messages m JOIN conversations c USING(conversation_id)
                                      WHERE c.conversation_id LIKE ? AND lower(m.content) LIKE '%compact%'""",
                                   (FAKE_PREFIX + "%",)).fetchone()[0] > 0))
    print("\nARCHIVE ACCEPTANCE TEST")
    print("=" * 72)
    for label, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + label)
    passed = sum(ok for _, ok in checks)
    print(f"\n{passed}/{len(checks)} tests passed")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate and evaluate synthetic Topology Peer archive data.")
    sub = p.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--students", type=int, default=20)
    g.add_argument("--conversations", type=int, default=120)
    g.add_argument("--seed", type=int, default=2027)
    sub.add_parser("report")
    sub.add_parser("test")
    sub.add_parser("clear")
    args = p.parse_args()

    if args.command == "generate":
        generate(args.students, args.conversations, args.seed)
    elif args.command == "report":
        report()
    elif args.command == "test":
        test()
    elif args.command == "clear":
        clear()
