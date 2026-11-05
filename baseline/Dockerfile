# andcode 兼容性构建基线(DESIGN §3)
# 基线: Ubuntu 24.04 LTS arm64 · glibc 2.39 · GCC 13
# 用法(arm64 原生或 qemu-user-static binfmt 环境):
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

# Bun(基线内构建 opencode / 运行 TS 工具时使用)
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -sf "$HOME/.bun/bin/bun" /usr/local/bin/bun

# 基线红线(NAMING §2 / DESIGN §3.1):
#  - 一切产物 glibc 符号版本 ≤ 2.39(CI 由 check-compat.sh 强制)
#  - arm64 工具链默认 -z max-page-size=65536,天然满足 16K 页设备(DESIGN §1.2.8)
ENV MAX_GLIBC=2.39
WORKDIR /work
