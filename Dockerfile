FROM python:3.12-slim
RUN pip install --no-cache-dir aiosmtpd
WORKDIR /app
COPY server.py .
EXPOSE 25
VOLUME /output
CMD ["python", "server.py"]
