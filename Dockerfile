# Base image provides PyRIT + Python.
# MIGRATION: swap this for your org's UBI-Python image with the org PyRIT package.
ARG BASE_IMAGE=ghcr.io/vamshikadumuri/pyrit:0.14.0-v1
FROM ${BASE_IMAGE}

# Today's base ships `uv` (no pip) with its venv at /opt/venv.
# MIGRATION (UBI-Python): drop the PATH line below and change the RUN to:
#   RUN pip install --no-cache-dir -r /tmp/requirements.txt
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/workspace
WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN uv pip install --python /opt/venv/bin/python --no-cache -r /tmp/requirements.txt

CMD ["python", "scripts/serve.py"]
