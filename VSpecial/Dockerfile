# ## Executive summary (read this first)
# A local research image. Submission metadata and an upload archive are intentionally absent.
FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
COPY qfbench2_track_forecasting /opt/qfbench2_track_forecasting
COPY v11_new /opt/v11_new
COPY vnext /opt/vnext
ENV PYTHONPATH=/opt
RUN printf '#!/bin/sh\nexec python3 -m vnext.cli "$@"\n' > /usr/local/bin/forecast && chmod +x /usr/local/bin/forecast \
    && useradd --create-home --uid 1000 runner
USER runner
WORKDIR /work
CMD ["forecast","--help"]
