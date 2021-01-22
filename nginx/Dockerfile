FROM nginx:latest

RUN apt-get update
RUN apt install -y certbot python3-certbot-nginx
# EXPOSE 80
# EXPOSE 443
RUN rm /etc/nginx/conf.d/default.conf
COPY app.conf /etc/nginx/conf.d