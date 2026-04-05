FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir mcp[cli] requests uvicorn

# Copy server code
COPY mcp_server.py .
COPY aigen/ ./aigen/

# Smithery injects PORT env var
ENV PORT=8080

EXPOSE 8080

CMD ["python", "mcp_server.py"]
