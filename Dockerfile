FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py groups.json templates.json autorotate.json .env.example ./
CMD ["python3", "bot.py"]
