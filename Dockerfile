FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y build-essential poppler-utils
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
