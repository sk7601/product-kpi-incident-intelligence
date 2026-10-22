FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8502
CMD ["sh", "-c", "alembic upgrade head && python -m product.pipeline && streamlit run app/dashboard.py --server.address=0.0.0.0 --server.port=8502"]
