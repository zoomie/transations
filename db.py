import sqlite3
import json
from pathlib import Path
from flask_login import UserMixin
from flask import current_app

DB_PATH = str(Path().home().joinpath('db.sql'))


def setup_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        with current_app.open_resource("schema.sql") as f:
            conn.executescript(f.read().decode("utf8"))
            conn.commit()
    except sqlite3.OperationalError:
        pass


class User(UserMixin):
    def __init__(self, id_, name, email, transactions=None):
        self.id = id_
        self.name: str = name
        self.email: str = email
        self.transactions: list = transactions

    @staticmethod
    def get(user_id) -> 'User':
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, transactions FROM user WHERE id = ?", (user_id,))
        user = cur.fetchone()
        if not user:
            return None
        if user[3] is not None:
            transactions = json.loads(user[3])
        else:
            transactions = None
        return User(id_=user[0], name=user[1], email=user[2], transactions=transactions)

    @staticmethod
    def create(id_, name, email) -> None:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user (id, name, email)"
            " VALUES (?, ?, ?)",
            (id_, name, email),
        )
        conn.commit()

    @staticmethod
    def set_transactions(id_, transactions: list) -> None:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            '''UPDATE user SET transactions = ? WHERE id = ?''',
            (json.dumps(transactions), id_),
        )
        conn.commit()


def get_or_create_user(id_, name, email) -> User:
    user = User(id_, name, email)
    if not User.get(id_):
        User.create(id_, name, email)
    return user


def create_test_user() -> User:
    id_ = '1'
    name = 'test'
    email = 'test.test@test.com'
    user = get_or_create_user(id_, name, email)
    with current_app.open_resource('mock_data.json') as f:
        data = f.read().decode()
        conn = sqlite3.connect(DB_PATH)
        curs = conn.cursor()
        curs.execute('delete from user')
        curs.execute('''insert into user (id, name, email, transactions)
                        values(?, ?, ?, ?)''', (id_, name, email, data))
        conn.commit()
    return user
