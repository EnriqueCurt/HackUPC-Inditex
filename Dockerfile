FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends g++ build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN g++ cpp/main.cpp cpp/dualCycleShuttle.cpp cpp/paletManager.cpp cpp/silo.cpp -O2 -o simulador
EXPOSE 8501
CMD sh -c "streamlit run frontend/app_streamlit.py --server.address 0.0.0.0 --server.port ${PORT:-8501}"