FROM python:3
RUN apt-get update &&\
    apt-get -y install npm &&\
    npm install --global yarn

ENV APP /app
RUN mkdir $APP
WORKDIR $APP
EXPOSE 5000
COPY requirements.txt .
RUN pip install --upgrade pip &&\
    pip install -r requirements.txt

COPY . .
RUN cd /app/frontend &&\
    yarn install &&\
    yarn build &&\
    cd ${APP}

CMD [ "uwsgi", "--ini", "app.ini" ]