FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY telegram_promo.py .
CMD ["python", "-u", "telegram_promo.py"]
