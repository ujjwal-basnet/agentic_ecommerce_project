FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Disable DNS rebinding protection in the mcp package to allow public VPS hosting
RUN python -c "import re, mcp.server.transport_security as ts; path = ts.__file__; content = open(path).read(); content = re.sub(r'(async def validate_request\(self.*?\) -> Response \| None:)', r'\1\n        return None', content); open(path, 'w').write(content)" \
    && find /usr/local/lib/python3.11/site-packages/mcp -name 'transport_security*.pyc' -delete

COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips=*"]

