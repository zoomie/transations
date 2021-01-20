FROM tiangolo/uwsgi-nginx-flask:python3.8
ENV STATIC_PATH /app/frontend/build/static

COPY ./app /app
RUN apt-get update && apt-get -y install npm && npm install yarn
RUN cd /app/frontend && npm run build

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
