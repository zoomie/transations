FROM python:3.6

WORKDIR /usr/src/workspace
RUN apt-get update \
 && apt-get -y install ripgrep vim
COPY . .
RUN pip install pipenv
RUN pipenv install --system --deploy --ignore-pipfile
#CMD [ "python", "./sample_script.py" ]