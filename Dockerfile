# ============================================
# Stage 1 – Frontend build (SvelteKit + Tailwind)
# ============================================
FROM node:20-bookworm-slim AS frontend-build
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend .
RUN npm run build


# ============================================
# Stage 2 – Backend runtime (FastAPI)
# ============================================
FROM python:3.11-slim AS backend

WORKDIR /app

# Install backend deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend .

# Copy compiled frontend into backend's static dir
COPY --from=frontend-build /app/frontend/build ./static

# Set default port
ENV PORT=8688
EXPOSE ${PORT}

# Start FastAPI (serving API + static files)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
