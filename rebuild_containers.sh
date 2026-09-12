#!/bin/bash

docker compose stop web reminders
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
echo 'start containers:'
docker compose up -d --no-build --force-recreate web reminders
docker ps --format "table {{.Names}}\t{{.Status}}"