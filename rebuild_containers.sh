#!/bin/bash

docker compose --profile proxy stop
echo 'pulling the enable-aws-ec2-deployment branch'
git pull
echo
echo '~~~'
echo 'git log:'
git log --oneline -4
echo
echo '~~~'
echo 'git status:'
git status
echo
echo '~~~'
echo 'rebuild containers:'
docker build -t cosypolyamory-web .
docker tag cosypolyamory-web cosypolyamory-reminders
echo
echo '~~~'
echo 'tls certificate:'
# nginx-proxy serves /etc/nginx/certs/<hostname>.crt|.key, bind-mounted from
# ./certs. Generate a self-signed pair the first time so HTTPS works without
# manual setup; anything already there is left alone, so a real certificate
# (or one issued by acme-companion) survives a rebuild.
CERT_DIR=certs
VHOST=$(sed -n 's/^VIRTUAL_HOST=//p' .env 2>/dev/null | tail -1 | tr -d "\"'" | cut -d, -f1)
VHOST=${VHOST:-cosypolyamory.org}

mkdir -p "$CERT_DIR"
if [ -s "$CERT_DIR/$VHOST.crt" ] && [ -s "$CERT_DIR/$VHOST.key" ]; then
    echo "certificate for $VHOST already present, leaving it alone"
elif [ ! -w "$CERT_DIR" ]; then
    echo "ERROR: $CERT_DIR is not writable (Docker creates it root-owned)."
    echo "Run this once, then re-run this script:"
    echo "  sudo chown -R \"$USER\" $CERT_DIR"
    exit 1
else
    echo "generating self-signed certificate for $VHOST"
    openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
        -keyout "$CERT_DIR/$VHOST.key" \
        -out "$CERT_DIR/$VHOST.crt" \
        -subj "/CN=$VHOST" \
        -addext "subjectAltName=DNS:$VHOST" || exit 1
    chmod 600 "$CERT_DIR/$VHOST.key"
fi
echo
echo 'start containers:'
docker compose --profile proxy up -d --no-build --force-recreate
docker ps --format "table {{.Names}}\t{{.Status}}"