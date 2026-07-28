# Sandbox image for the render worker (ADR-0002).
# Ships exactly the Supported Packages (ADR-0001) + ffmpeg (ADR-0003).
# Build from the repo root:  docker build -t artwall-worker -f worker/Dockerfile .
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# The Supported Packages list — keep identical to artwall/config.py and the
# Pyodide preview on the submission page.
RUN pip install --no-cache-dir \
    numpy matplotlib Pillow pandas shapely scipy \
    colour trimesh svgpathtools

ENV MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpl HOME=/tmp

# Warm matplotlib's font cache at build time, not per job
RUN python -c "import matplotlib.pyplot"

COPY samples/preview.py /app/preview.py
COPY worker/render_job.py /app/render_job.py

WORKDIR /tmp
