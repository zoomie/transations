FROM python:3
RUN apt-get update &&\
    apt-get -y install npm &&\
    npm i npm@latest -g

ENV APP /app
RUN mkdir $APP
WORKDIR $APP
EXPOSE 5000
COPY requirements.txt .
RUN pip install --upgrade pip &&\
    pip install -r requirements.txt

COPY . .
RUN cd /app/frontend &&\
    npm install &&\
    npm run build

CMD [ "uwsgi", "--ini", "app.ini" ]