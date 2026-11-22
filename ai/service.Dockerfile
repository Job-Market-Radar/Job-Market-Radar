FROM python:3.12-slim

# Don't write .pyc files; print logs straight away (so CloudWatch gets them).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Packages first: this layer is reused as long as requirements.txt doesn't change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then the code and prompts only.
COPY *.py ./
COPY prompts/ prompts/

# Run as a normal user, not root.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Secrets (DATABASE_URL, GEMINI_API_KEY) come from environment variables at run time.
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]
