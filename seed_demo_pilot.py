"""
seed_demo_pilot.py
------------------
Seeds a realistic, local pilot demonstration dataset for the
B.E. Final Year Examination Platform.

Dataset contents:
- 1 Admin account (Prof. Amit Kulkarni)
- 3 Fictional B.E. Final Year students (Rahul Sharma, Priya Patil, Sneha Deshmukh)
- 1 Draft Exam (Cloud Architecture & Security)
- 1 Published Exam (Distributed Systems & Consensus V1)
- 1 Completed Attempt (Rahul Sharma scored 3/3, sealed into SHA-256 block)
- 1 Closed Exam (Operating Systems & Virtualization)

Usage:
    python seed_demo_pilot.py

Safety:
    By default this populates local SQLite (exam_system.db).
    It will never execute against Neon PostgreSQL unless explicitly permitted.
"""

import os
import sys
import time
from datetime import datetime, timedelta

# Safety guard: Force local SQLite for pilot demonstration seeding to guarantee production safety
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(BASE_DIR, "exam_system.db")
os.environ["DATABASE_URL"] = f"sqlite:///{SQLITE_DB}"

from app import app
from models import db, User, Exam, Question, Attempt, Block
import database
import blockchain


def seed_demo():
    with app.app_context():
        db.create_all()

        print("=" * 60)
        print("SEEDING B.E. FINAL YEAR V1 PILOT DEMO DATA")
        print("=" * 60)

        # 1. Admin Account
        admin = database.get_user_by_identifier("admin_demo")
        if not admin:
            admin = database.create_user(
                name="Prof. Amit Kulkarni",
                identifier="admin_demo",
                username="admin_demo",
                email="amit.kulkarni@demo.edu",
                password="AdminDemoPass123!",
                role="admin",
            )
            print("[+] Created Admin Account: admin_demo (Password: AdminDemoPass123!)")
        else:
            print("[*] Admin Account already exists: admin_demo")

        # 2. Three Fictional B.E. Final Year Students
        students_data = [
            ("Rahul Sharma", "BE2026CS001", "rahul.sharma@demo.edu", "StudentPass123!"),
            ("Priya Patil", "BE2026CS002", "priya.patil@demo.edu", "StudentPass123!"),
            ("Sneha Deshmukh", "BE2026CS003", "sneha.deshmukh@demo.edu", "StudentPass123!"),
        ]

        students = []
        for name, prn, email, pwd in students_data:
            s = database.get_user_by_identifier(prn)
            if not s:
                s = database.create_user(
                    name=name,
                    identifier=prn,
                    email=email,
                    password=pwd,
                    role="user",
                    username=None,
                )
                print(f"[+] Created Student Account: {name} | PRN: {prn} (Password: {pwd})")
            else:
                print(f"[*] Student Account already exists: {name} ({prn})")
            students.append(s)

        now = datetime.now()

        # 3. Draft Exam
        draft_exam = Exam.query.filter_by(title="Cloud Architecture & Security (Draft)").first()
        if not draft_exam:
            draft_exam = database.create_exam(
                title="Cloud Architecture & Security (Draft)",
                created_by=admin.id,
                start_time=now + timedelta(days=2),
                end_time=now + timedelta(days=3),
                duration_minutes=30,
                questions=[
                    {
                        "question": "Which cloud computing model offers virtualization of computing resources over the internet?",
                        "options": ["IaaS", "SaaS", "PaaS", "FaaS"],
                        "correct_index": 0,
                    },
                    {
                        "question": "What is the primary role of a Load Balancer in distributed systems?",
                        "options": ["Encrypt disk storage", "Distribute incoming network traffic across multiple servers", "Compile application code", "Backup database logs"],
                        "correct_index": 1,
                    },
                ],
                status="draft",
            )
            print(f"[+] Created Draft Exam: {draft_exam.title} (ID: {draft_exam.id})")
        else:
            print(f"[*] Draft Exam already exists: {draft_exam.title}")

        # 4. Published Exam
        pub_exam = Exam.query.filter_by(title="Distributed Systems & Consensus V1").first()
        if not pub_exam:
            pub_exam = database.create_exam(
                title="Distributed Systems & Consensus V1",
                created_by=admin.id,
                start_time=now - timedelta(hours=1),
                end_time=now + timedelta(hours=48),
                duration_minutes=45,
                questions=[
                    {
                        "question": "What fundamental problem does the Byzantine Generals Problem address?",
                        "options": ["Reaching consensus among nodes in the presence of faulty or malicious participants", "Sorting arrays in linear time", "Allocating RAM to threads", "Generating cryptographic public keys"],
                        "correct_index": 0,
                    },
                    {
                        "question": "Which cryptographic hash function produces a 256-bit fixed-length output?",
                        "options": ["MD5", "SHA-1", "SHA-256", "CRC32"],
                        "correct_index": 2,
                    },
                    {
                        "question": "In a hash-linked blockchain, what link protects block integrity against historical modification?",
                        "options": ["The server IP address", "The previous block's SHA-256 hash pointer", "The client browser user-agent", "The DNS record"],
                        "correct_index": 1,
                    },
                ],
                status="published",
            )
            print(f"[+] Created Published Exam: {pub_exam.title} (ID: {pub_exam.id})")
        else:
            print(f"[*] Published Exam already exists: {pub_exam.title}")

        # 5. Completed Attempt for Rahul Sharma (BE2026CS001)
        rahul = students[0]
        attempt = database.get_attempt(pub_exam.id, rahul.id)
        if not attempt:
            attempt = database.start_attempt(pub_exam.id, rahul.id, len(pub_exam.questions))
            answers_payload = [
                {"question": pub_exam.questions[0].question_text, "options": pub_exam.questions[0].options, "selected_index": 0, "correct_index": 0, "is_correct": True, "status": "correct"},
                {"question": pub_exam.questions[1].question_text, "options": pub_exam.questions[1].options, "selected_index": 2, "correct_index": 2, "is_correct": True, "status": "correct"},
                {"question": pub_exam.questions[2].question_text, "options": pub_exam.questions[2].options, "selected_index": 1, "correct_index": 1, "is_correct": True, "status": "correct"},
            ]
            score = 3
            total = 3
            percentage = 100.0

            # Seal into private SHA-256 blockchain
            block_data = {
                "type": "exam_result",
                "student_name": rahul.name,
                "roll_no": rahul.identifier,
                "prn": rahul.identifier,
                "exam_id": pub_exam.id,
                "exam_title": pub_exam.title,
                "answers": answers_payload,
                "score": score,
                "total": total,
                "percentage": percentage,
                "correct_count": 3,
                "incorrect_count": 0,
                "unanswered_count": 0,
                "started_at": attempt.started_at.strftime("%d %b %Y, %I:%M:%S %p"),
                "submitted_at": now.strftime("%d %b %Y, %I:%M:%S %p"),
                "time_used_seconds": 862,
                "time_used_display": "14m 22s",
                "is_timeout": False,
            }
            chain = blockchain.Blockchain()
            block_view = chain.add_block(block_data)

            database.finalize_attempt(
                attempt,
                score=score,
                total_questions=total,
                block_id=block_view.index,
                submitted_at=now,
            )
            print(f"[+] Created Completed Attempt: Rahul Sharma | Score: {score}/{total} (100.0%) | Sealed Block #{block_view.index}")
            print(f"    SHA-256 Hash: {block_view.hash}")
        else:
            print(f"[*] Completed Attempt already exists for student {rahul.name}")

        # 6. Closed Exam
        closed_exam = Exam.query.filter_by(title="Operating Systems & Virtualization (Completed Semester)").first()
        if not closed_exam:
            closed_exam = database.create_exam(
                title="Operating Systems & Virtualization (Completed Semester)",
                created_by=admin.id,
                start_time=now - timedelta(days=7),
                end_time=now - timedelta(days=6),
                duration_minutes=60,
                questions=[
                    {
                        "question": "Which system call creates a new process in Unix?",
                        "options": ["fork()", "exec()", "wait()", "exit()"],
                        "correct_index": 0,
                    },
                    {
                        "question": "What is the primary condition for a deadlock known as circular wait?",
                        "options": ["Processes share single core", "A closed chain of processes exists where each holds a resource needed by the next", "Virtual memory is full", "Page fault rate exceeds threshold"],
                        "correct_index": 1,
                    },
                ],
                status="closed",
            )
            print(f"[+] Created Closed Exam: {closed_exam.title} (ID: {closed_exam.id})")
        else:
            print(f"[*] Closed Exam already exists: {closed_exam.title}")

        print("=" * 60)
        print("DEMO PILOT DATA SEEDING COMPLETE")
        print("=" * 60)
        print("\nDemo Login Credentials:")
        print("-----------------------")
        print("Admin Portal:")
        print("  Identifier: admin_demo")
        print("  Password:   AdminDemoPass123!")
        print("\nStudent Portal:")
        print("  Student 1 (Completed attempt): PRN: BE2026CS001 | Password: StudentPass123!")
        print("  Student 2 (Ready to take):     PRN: BE2026CS002 | Password: StudentPass123!")
        print("  Student 3 (Ready to take):     PRN: BE2026CS003 | Password: StudentPass123!")
        print("-----------------------\n")


if __name__ == "__main__":
    seed_demo()
