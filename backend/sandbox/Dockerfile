# PolyPilot execution sandbox image.
# Build (from WSL or any Docker host):
#   docker build -t polypilot-sandbox:latest backend/sandbox
# Pinned by digest (alpine 3.20.10). Update deliberately: docker pull alpine:3.20 && docker image inspect.
FROM alpine:3.20.10@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc

RUN apk add --no-cache g++ libstdc++ python3

# Unprivileged execution user. UID 10001 deliberately does not match a typical
# host/WSL login user (1000).
RUN adduser -D -H -u 10001 -s /sbin/nologin sandbox && mkdir -p /workspace /opt/polypilot

# Official testlib.h on the system include path (read-only, root-owned)
COPY testlib.h /usr/local/include/testlib.h
COPY harness.py /opt/polypilot/harness.py
RUN chmod 0444 /usr/local/include/testlib.h && chmod 0555 /opt/polypilot/harness.py

USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["python3", "-I", "-B", "/opt/polypilot/harness.py"]
