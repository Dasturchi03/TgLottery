FROM python:3.12

RUN apt-get update && \
    apt-get install -y locales
RUN sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen ru_RU.UTF-8
ENV LANGUAGE ru_RU:ru
ENV LANG ru_RU.UTF-8
ENV LC_ALL ru_RU.UTF-8

ENV PYTHONUNBUFFERED 1
ENV V Docerfile
ENV TZ=Europe/Moscow

RUN mkdir /code
WORKDIR /code
COPY . /code

RUN pip install -U pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn && \
    pip install --no-cache-dir uvicorn


# CMD ["python","main.py"]
# CMD ["uvicorn", "coll:app"]