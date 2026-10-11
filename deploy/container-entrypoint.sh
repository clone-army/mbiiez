#!/bin/sh
set -eu
umask 077
mkdir -p /var/lib/mbiiez/configs /var/lib/mbiiez/homepaths /var/lib/mbiiez/pids
# Keep runtime state in volumes while code and config templates stay in the image.
cp -n /app/configs/server.template /var/lib/mbiiez/configs/server.template
cp -n /app/configs/demo.json.example /var/lib/mbiiez/configs/demo.json.example
if [ ! -L /app/configs ]; then
    mv /app/configs /app/configs.dist
    ln -s /var/lib/mbiiez/configs /app/configs
fi
if [ ! -L /app/homepaths ]; then
    if [ -d /app/homepaths ]; then mv /app/homepaths /app/homepaths.dist; fi
    ln -s /var/lib/mbiiez/homepaths /app/homepaths
fi
if [ ! -L /app/pids ]; then
    if [ -d /app/pids ]; then mv /app/pids /app/pids.dist; fi
    ln -s /var/lib/mbiiez/pids /app/pids
fi
exec "$@"
