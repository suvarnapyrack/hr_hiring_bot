#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL to be ready..."
# Wait for postgres to accept connections before running init
for i in $(seq 1 30); do
  if python -c "
import psycopg2
try:
    conn = psycopg2.connect('$DATABASE_URL')
    conn.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
    echo "✅ PostgreSQL is ready!"
    break
  fi
  echo "⏳ Waiting for DB... attempt $i/30"
  sleep 2
done

echo "🔧 Running Database Initializations..."
python app/init_db.py

echo "🚀 Starting Streamlit App..."
exec streamlit run main.py --server.port=8501 --server.address=0.0.0.0
