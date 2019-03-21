#!/bin/bash

cd ~ubuntu/hetmech-backend
git checkout master; git pull
sudo /etc/init.d/supervisor restart
