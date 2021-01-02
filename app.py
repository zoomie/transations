import os
import time
import urllib
import csv
from io import StringIO

from flask import Flask, redirect, request, url_for
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response
from werkzeug.wsgi import FileWrapper
import requests

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
TOKEN = {}


app = Flask(__name__)


@app.route('/', methods=['GET'])
def index():
    return 'Hello'


@app.route('/signin', methods=['GET'])
def sign_in():
    query = urllib.parse.urlencode({
        'response_type': 'code',
        'response_mode': 'form_post',
        'client_id': CLIENT_ID,
        'scope': 'accounts balance transactions offline_access',
        'nonce': int(time.time()),
        'redirect_uri': REDIRECT_URI,
        'enable_mock': 'true',
    })
    auth_uri = f'https://auth.truelayer-sandbox.com/?{query}'
    return f'Please sign in <a href="{auth_uri}" target="_blank">here.</a>'


@app.route('/callback', methods=['POST', 'GET'])
def callback():
    access_code = request.form['code']
    body = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': access_code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI,
    }
    res = requests.post('https://auth.truelayer-sandbox.com/connect/token', data=body)
    TOKEN['value'] = res.json()['access_token']
    return redirect(url_for('download_transactions'))


def generator(file_obj, buffer_size=8192):
    file_obj.seek(0)
    while True:
        data = file_obj.read(buffer_size)
        if data:
            yield data
        else:
            break


@app.route('/download_transactions', methods=['GET'])
def download_transactions():
    token = TOKEN['value']
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


# app.run(debug=True)
