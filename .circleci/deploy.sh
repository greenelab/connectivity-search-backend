#!/bin/bash

cd ~/hetmech-backend
git checkout master

ENV_FILE="environment.yml"
git remote update
ENV_DIFF=`git diff origin $ENV_FILE`
git pull

# Update conda env if needed
if [ -n "$ENV_DIFF" ]; then
    conda update --file $ENV_FILE
fi

# Restart Gunicorn daemon
sudo /etc/init.d/supervisor restart
