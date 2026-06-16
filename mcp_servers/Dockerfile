FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./mcp_servers

ENV SERVER_MODULE=mcp_servers.linkedin.server
ENV PORT=8001

CMD ["sh", "-c", "python -m ${SERVER_MODULE}"]
