#!/bin/bash

# This script should be run as user "ubuntu" only.
if [ `whoami` != 'ubuntu' ]; then
    echo "Error: current user is not ubuntu!"
    exit
fi

# Update packages automatically using a daily cron job
sudo apt update
sudo apt purge unattended-upgrades --yes
sudo rm -rf /var/log/unattended-upgrades/
sudo cp upgrade-pkg /etc/cron.daily/
sudo chmod 755 /etc/cron.daily/upgrade-pkg

# Nginx config
sudo apt install nginx --yes
# Install SSL certificates issued by Let's Encrypt
sudo add-apt-repository ppa:certbot/certbot --yes
sudo apt update
sudo apt install certbot python-certbot-nginx --yes
sudo certbot --nginx certonly

sudo rm -f /etc/nginx/sites-enabled/default
sudo cp hetmech-api.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/hetmech-api.conf /etc/nginx/sites-enabled/
sudo /etc/init.d/nginx restart

# Miniconda environment setup
sudo apt install git wget python3 python3-pip --yes
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh --output-document miniconda.sh
bash miniconda.sh -b -p ~/miniconda
cat bashrc_conda >> ~/.bashrc && source ~/.bashrc
apt install gcc --yes  # gcc is required by "pip install git+https://..."

cd && git clone https://github.com/greenelab/hetmech-backend.git
cd hetmech-backend
conda env create --quiet --file environment.yml
python manage.py makemigrations dj_hetmech_app
python manage.py migrate

# "static" directory (used by API view in HTML format)
mkdir -p ~/www/static && chmod -R 755 ~/www/
python manage.py collectstatic

# Use supervisord to take care of Gunicorn daemon
sudo apt install supervisor --yes
sudo cp gunicorn.conf /etc/supervisor/conf.d/
sudo /etc/init.d/supervisor restart
