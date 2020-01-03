FROM python:3.7-slim

COPY . /app
WORKDIR /app
RUN apt-get update -y && \
    apt-get install -y python-pip python-dev && \
    pip install -r requirements.txt && \
    pip install gunicorn && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "gunicorn" ]
CMD [ "--bind=0.0.0.0:5002", "--workers=2", "--preload", "wsgi" ]
