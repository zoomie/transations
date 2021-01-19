FROM tiangolo/uwsgi-nginx-flask:python3.8

COPY ./app /app

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
