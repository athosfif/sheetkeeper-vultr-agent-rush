# Resolve and record the image digest on the deployment host before release.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin worker
USER 10001:10001
WORKDIR /work
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "--version"]
