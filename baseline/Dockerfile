# andcode compatibility build baseline (DESIGN §3)
# Baseline: Ubuntu 24.04 LTS arm64 · glibc 2.39 · GCC 13
# Usage (native arm64 or a qemu-user-static binfmt environment):
#   docker buildx build --platform linux/arm64 -t andcode/baseline - < baseline/Dockerfile
#   docker run --platform linux/arm64 andcode/baseline <cmd>
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git curl ca-certificates xz-utils zstd \
        file binutils patchelf pax-utils \
        debootstrap qemu-user-static \
        nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Bun (used to build opencode / run TS tools within the baseline)
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -sf "$HOME/.bun/bin/bun" /usr/local/bin/bun

# Baseline hard limits (NAMING §2 / DESIGN §3.1):
#  - All artifact glibc symbol versions must be ≤ 2.39 (enforced by check-compat.sh in CI)
#  - The arm64 toolchain defaults to -z max-page-size=65536, satisfying 16K-page devices (DESIGN §1.2.8)
ENV MAX_GLIBC=2.39
WORKDIR /work
