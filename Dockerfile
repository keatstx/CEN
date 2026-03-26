FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY --from=frontend /app/frontend/dist ./frontend/dist
EXPOSE 10000
CMD ["uvicorn", "cen.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "10000"]
