FROM public.ecr.aws/docker/library/python@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics MPLCONFIGDIR=/tmp/matplotlib \
    OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
WORKDIR /opt/vision
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    && pip check
RUN groupadd --gid 10001 vision && useradd --uid 10001 --gid vision --no-create-home vision \
    && mkdir /var/lib/vision && chown vision:vision /var/lib/vision
COPY client.py outbox.py tracking.py worker.py verify.py verify_playback.py ./
USER 10001:10001
ENTRYPOINT ["python", "worker.py"]
