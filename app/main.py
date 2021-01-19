import os
import time
import urllib
import csv
from io import StringIO
import sqlite3
from pathlib import Path
import json
from urllib.parse import urljoin
from dotenv import load_dotenv

from flask import Flask, redirect, request, url_for, jsonify
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response
import requests
from flask_login import LoginManager, current_user, login_required, login_user,\
    logout_user, UserMixin
from oauthlib.oauth2 import WebApplicationClient


load_dotenv()
TRUELAYER_CLIENT_ID = os.environ['TRUELAYER_CLIENT_ID']
TRUELAYER_CLIENT_SECRET = os.environ['TRUELAYER_CLIENT_SECRET']
IS_SANDBOX = os.getenv('IS_SANDBOX', False)
IS_SANDBOX = True if IS_SANDBOX in [True, 'True', 'true'] else False
if IS_SANDBOX:
    TRUELAYER_AUTH_URL = 'https://auth.truelayer-sandbox.com'
    TRUELAYER_API_URL = 'https://api.truelayer-sandbox.com'
else:
    TRUELAYER_AUTH_URL = 'https://auth.truelayer.com'
    TRUELAYER_API_URL = 'https://api.truelayer.com'

GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
GOOGLE_OIDC_CONFIG = requests.get("https://accounts.google.com/.well-known/openid-configuration").json()
APP_URL = os.environ['APP_URL']

DEBUG = os.getenv('DEBUG', False)
DEBUG = True if DEBUG in [True, 'True', 'true'] else False

app = Flask(__name__, static_folder='frontend/build', static_url_path='/')
app.secret_key = os.environ['FLASK_SECRET_KEY']

login_manager = LoginManager()
login_manager.login_view = '/login'
login_manager.init_app(app)


client = WebApplicationClient(GOOGLE_CLIENT_ID)
DB_PATH = str(Path().home().joinpath('db.sql'))


def setup_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        with app.open_resource("schema.sql") as f:
            conn.executescript(f.read().decode("utf8"))
            conn.commit()
    except sqlite3.OperationalError:
        pass


setup_db()


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
    with app.open_resource('mock_data.json') as f:
        data = f.read().decode()
        conn = sqlite3.connect(DB_PATH)
        curs = conn.cursor()
        curs.execute('delete from user')
        curs.execute('''insert into user (id, name, email, transactions)
                        values(?, ?, ?, ?)''', (id_, name, email, data))
        conn.commit()
    return user




@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route("/")
def index():
    return 'Hello world'
    # return app.send_static_file('index.html')


@app.route("/login")
def login():
    if DEBUG:
        user = create_test_user()
        login_user(user)
        return redirect(url_for('index'))
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    request_uri = client.prepare_request_uri(
        GOOGLE_OIDC_CONFIG["authorization_endpoint"],
        redirect_uri=urljoin(APP_URL, "/google_callback"),
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@app.route("/google_callback")
def google_callback():
    code = request.args.get("code")
    token_url, headers, body = client.prepare_token_request(
        token_url=GOOGLE_OIDC_CONFIG["token_endpoint"],
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        url=token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    client.parse_request_body_response(json.dumps(token_response.json()))
    uri, headers, body = client.add_token(GOOGLE_OIDC_CONFIG["userinfo_endpoint"])
    userinfo_response = requests.get(uri, headers=headers, data=body)
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    user = get_or_create_user(id_=unique_id, name=users_name, email=users_email, token=None)
    login_user(user, remember=True)
    return redirect(url_for('index'))


@app.route('/truelayer_signin', methods=['GET'])
@login_required
def truelayer_signin():
    query = urllib.parse.urlencode({
        'response_type': 'code',
        'response_mode': 'form_post',
        'client_id': TRUELAYER_CLIENT_ID,
        'scope': 'accounts balance transactions offline_access',
        'nonce': int(time.time()),
        'redirect_uri': urljoin(APP_URL, 'truelayer_callback'),
        'enable_mock': 'true',
    })
    auth_uri = f'{TRUELAYER_AUTH_URL}/?{query}'
    print(auth_uri)
    return redirect(auth_uri)


def get_transactions_from_truelayer(token: str) -> list:
    transactions = []
    auth_header = {'Authorization': f'Bearer {token}'}
    res = requests.get(f'{TRUELAYER_API_URL}/data/v1/accounts', headers=auth_header)
    for account in res.json()['results']:
        account_id = account['account_id']
        url = f'{TRUELAYER_API_URL}/data/v1/accounts/{account_id}/transactions'
        res = requests.get(url, headers=auth_header)
        transactions.extend(res.json()['results'])
    return transactions


@app.route('/truelayer_callback', methods=['POST', 'GET'])
@login_required
def truelayer_callback():
    access_code = request.form['code']
    body = {
        'client_id': TRUELAYER_CLIENT_ID,
        'client_secret': TRUELAYER_CLIENT_SECRET,
        'code': access_code,
        'grant_type': 'authorization_code',
        'redirect_uri': urljoin(APP_URL, 'truelayer_callback'),
    }
    res = requests.post(f'{TRUELAYER_AUTH_URL}/connect/token', data=body)
    token = res.json().get('access_token')
    if token:
        transactions = get_transactions_from_truelayer(token)
        User.set_transactions(id_=current_user.id, transactions=transactions)
    return redirect(url_for('index'))


def generator(file_obj, buffer_size=8192):
    file_obj.seek(0)
    while True:
        data = file_obj.read(buffer_size)
        if data:
            yield data
        else:
            break


def create_csv_response(transactions: list) -> Response:
    csv_data = StringIO(newline='')
    writer = csv.writer(csv_data)
    column_names = ['timestamp', 'description', 'transaction_category', 'amount']
    writer.writerow(column_names)
    for transaction in transactions:
        writer.writerow([transaction[key] for key in column_names])
    headers = Headers()
    headers.set('Content-Disposition', 'attachment', filename='transactions.csv')
    return Response(generator(csv_data), mimetype='text/csv', headers=headers)


def format_for_graph(transactions: list) -> list:
    result = []
    for transaction in transactions:
        result.append({
            'timestamp': transaction['timestamp'],
            'amount': transaction['running_balance']['amount']
        })
    return result


@app.route('/api/transactions', methods=['GET'])
@login_required
def download_transactions():
    if current_user.transactions:
        if request.args.get('format') == 'csv':
            return create_csv_response(current_user.transactions)
        else:
            return jsonify({'user_has_data': True,
                            'transactions': format_for_graph(current_user.transactions)})
    return jsonify({'user_has_data': False})


@app.route('/api/transactions/test', methods=['GET'])
def test_api():
    with app.open_resource('mock_data.json') as f:
        data = json.load(f)
        result = {'user_has_data': True, 'transactions': format_for_graph(data)}
        return jsonify(result)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/ping")
def ping():
    return "This is working"


if __name__ == "__main__":
    app.run(host="localhost", debug=True, port=5000)
