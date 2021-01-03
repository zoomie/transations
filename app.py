import os
import time
import urllib
import csv
from io import StringIO
import sqlite3
import json
from pathlib import Path
from urllib.parse import urljoin

from decouple import config
from flask import Flask, redirect, request, url_for, current_app
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response
import requests
from flask_login import LoginManager, current_user, login_required, login_user,\
    logout_user, UserMixin
from oauthlib.oauth2 import WebApplicationClient

TRUELAYER_CLIENT_ID = config('TRUELAYER_CLIENT_ID')
TRUELAYER_CLIENT_SECRET = config('TRUELAYER_CLIENT_SECRET')

GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET')
GOOGLE_OIDC_CONFIG = requests.get("https://accounts.google.com/.well-known/openid-configuration").json()
APP_URL = config('APP_URL', default='https://localhost:5000')

DB_PATH = str(Path().home().joinpath('db.sql'))

app = Flask(__name__)
app.secret_key = config("FLASK_SECRET_KEY", default=os.urandom(16))

login_manager = LoginManager()
login_manager.init_app(app)

client = WebApplicationClient(GOOGLE_CLIENT_ID)


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
    def __init__(self, id_, name, email, token=None):
        self.id = id_
        self.name = name
        self.email = email
        self.token = token

    @staticmethod
    def get(user_id):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, token FROM user WHERE id = ?", (user_id,))
        user = cur.fetchone()
        if not user:
            return None
        return User(id_=user[0], name=user[1], email=user[2], token=user[3])

    @staticmethod
    def create(id_, name, email):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user (id, name, email)"
            " VALUES (?, ?, ?)",
            (id_, name, email),
        )
        conn.commit()

    @staticmethod
    def set_token(id_, token):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            '''UPDATE user SET token = ? WHERE id = ?''',
            (token, id_),
        )
        conn.commit()


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route("/")
def index():
    if current_user.is_authenticated:
        return f"<p>You're logged in {current_user.name}</p>"
    else:
        return redirect(url_for('login'))


@app.route("/login")
def login():
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

    user = User(id_=unique_id, name=users_name, email=users_email, token=None)
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email)

    login_user(user)
    return redirect(url_for("truelayer_signin"))


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
    auth_uri = f'https://auth.truelayer-sandbox.com/?{query}'
    return redirect(auth_uri)
    # return f'<a class="button" href="{auth_uri}">Truelayer Login</a>'


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
    res = requests.post('https://auth.truelayer-sandbox.com/connect/token', data=body)
    token = res.json().get('access_token')
    if token:
        User.set_token(id_=current_user.id, token=token)
        return redirect(url_for('download_transactions'))
    else:
        return 'hello'


def generator(file_obj, buffer_size=8192):
    file_obj.seek(0)
    while True:
        data = file_obj.read(buffer_size)
        if data:
            yield data
        else:
            break


@app.route('/download_transactions', methods=['GET'])
@login_required
def download_transactions():
    token = current_user.token
    auth_header = {'Authorization': f'Bearer {token}'}
    res = requests.get('https://api.truelayer-sandbox.com/data/v1/accounts', headers=auth_header)
    csv_data = StringIO(newline='')
    writer = csv.writer(csv_data)
    column_names = ['timestamp', 'description', 'transaction_category', 'amount']
    writer.writerow(column_names)
    for account in res.json()['results']:
        account_id = account['account_id']
        url = f'https://api.truelayer-sandbox.com/data/v1/accounts/{account_id}/transactions'
        res = requests.get(url, headers=auth_header)
        for transaction in res.json()['results']:
            writer.writerow([transaction[key] for key in column_names])

    headers = Headers()
    headers.set('Content-Disposition', 'attachment', filename='transactions.csv')
    return Response(generator(csv_data), mimetype='text/csv', headers=headers)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# app.run(ssl_context="adhoc")