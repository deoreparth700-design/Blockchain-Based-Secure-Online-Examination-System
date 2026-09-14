"""
init_db.py
----------
Run this ONCE before starting the app for the first time:

    python init_db.py

It creates all the database tables (in exam_system.db) and walks you
through creating your first teacher account interactively -- nothing
is hardcoded, so there's no default password sitting in the source
code for a student to find on GitHub.

Safe to run again later: it won't recreate tables that already exist,
and it'll let you add another teacher account if you need one.
"""

import getpass

from app import app
from models import db
import database

with app.app_context():
    db.create_all()
    print("Database tables ready (exam_system.db).\n")

    print("Let's create a teacher account.")
    name = input("Teacher's full name: ").strip()
    username = input("Choose a username for login: ").strip()
    password = getpass.getpass("Choose a password: ")

    if database.get_user_by_identifier(username):
        print(f"\nA user with username '{username}' already exists. Skipping creation.")
    else:
        database.create_user(name=name, identifier=username, password=password, role="teacher")
        print(f"\nTeacher account created. Log in at /login with username '{username}'.")
