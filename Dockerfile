# syntax=docker/dockerfile:1
FROM debian:bookworm-slim AS engine
ARG OPENJK_REF=bc89f618fdd1c5ffe67289468b6ca7beede4f86a
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git cmake build-essential gcc-multilib g++-multilib \
    libjpeg-dev:i386 libpng-dev:i386 zlib1g-dev:i386 curl && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/clone-army/OpenJK /src/OpenJK && git -C /src/OpenJK checkout "$OPENJK_REF"
RUN curl -fsSL https://github.com/gsl-lite/gsl-lite/archive/refs/tags/v0.41.0.tar.gz \
    | tar xz --strip-components=1 -C /src/OpenJK/lib/gsl-lite
RUN cmake -S /src/OpenJK -B /src/OpenJK/build \
    -DBuildMPDed=ON -DBuildMPEngine=OFF -DBuildMPRdVanilla=OFF -DBuildMPCGame=OFF -DBuildMPUI=OFF \
    -DBuildSPEngine=OFF -DBuildSPGame=OFF -DBuildSPRdVanilla=OFF \
    -DCMAKE_TOOLCHAIN_FILE=/src/OpenJK/cmake/Toolchains/linux-i686.cmake \
    && cmake --build /src/OpenJK/build -j2

FROM debian:bookworm-slim AS runtime
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv ca-certificates git screen psmisc procps supervisor tini curl unzip rsync \
    libc6:i386 libstdc++6:i386 libgcc-s1:i386 zlib1g:i386 libjpeg62-turbo:i386 libpng16-16:i386 libcurl4:i386 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements.lock /app/
RUN python3 -m venv /opt/openjk/venv && /opt/openjk/venv/bin/pip install --no-cache-dir -r requirements.lock
COPY . /app
RUN cp mbiiez.conf.example mbiiez.conf && mkdir -p /var/lib/mbiiez /opt/openjk/base /opt/openjk/MBII \
    && printf '#!/bin/sh\nexec /opt/openjk/venv/bin/python3 /app/mbii.py "$@"\n' > /usr/local/bin/mbii \
    && chmod +x /usr/local/bin/mbii /app/deploy/container-entrypoint.sh \
    && install -m755 /app/mbiided.i386 /usr/bin/mbiided.i386
ARG MBIIEZ_REVISION=unknown
ENV MBIIEZ_REVISION=$MBIIEZ_REVISION
ENV MBIIEZ_STATE_DIR=/var/lib/mbiiez MBIIEZ_CONTAINER=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/container-entrypoint.sh"]

FROM runtime AS web
ENV MBIIEZ_COMPONENT=web
EXPOSE 8080
CMD ["/opt/openjk/venv/bin/python3", "/app/deploy/serve-web.py"]

FROM runtime AS node
COPY --from=engine /src/OpenJK/build/mbiided.i386 /usr/bin/caded.i386
COPY deploy/supervisord.conf /etc/supervisor/conf.d/mbiiez.conf
ENV MBIIEZ_COMPONENT=node
EXPOSE 8081 29072/udp
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/mbiiez.conf"]
