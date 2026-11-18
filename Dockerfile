FROM python:3.12-slim
RUN useradd --create-home app && mkdir /data && chown app /data
WORKDIR /app
COPY notifier.py .
USER app
CMD ["python", "-u", "notifier.py"]
