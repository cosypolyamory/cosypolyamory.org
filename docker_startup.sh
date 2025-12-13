#!/bin/bash

chown -R www-data:www-data /data
uwsgi --gid=www-data --uid=www-data --http-socket :3031 \
      --vhost --module=cosypolyamory.app --callable=app --chdir=/code/cosypolyamory.org \
      --enable-threads --processes=15
