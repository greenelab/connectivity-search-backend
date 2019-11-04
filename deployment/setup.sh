#!/bin/bash

# This script should be run as user "ubuntu" only.
if [ `whoami` != 'ubuntu' ]; then
    echo "Error: only the user 'ubuntu' is allowed to run this script."
    exit 1
fi

# Make sure Django secrets file (secrets.yml) is available
if [ -z $DJ_SECRETS_FILE ]; then
    echo "Type in the location of Django secrets file, followed by [ENTER]:"
    read DJ_SECRETS_FILE
fi

if ! [ -f "$DJ_SECRETS_FILE" ]; then
    echo "Error: invalid Django secrets file."
    exit 2
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
sudo cp consearch-api.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/consearch-api.conf /etc/nginx/sites-enabled/

# Use supervisord to take care of Gunicorn daemon
sudo apt install supervisor --yes
sudo cp gunicorn.conf /etc/supervisor/conf.d/

# Miniconda environment setup
sudo apt install git wget python3 python3-pip gcc --yes
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh --output-document ~/miniconda.sh
bash ~/miniconda.sh -b -p ~/miniconda
echo "source ~/miniconda/etc/profile.d/conda.sh" >> ~/.bashrc

rm -rf ~/connectivity-search-backend
git clone https://github.com/greenelab/connectivity-search-backend.git ~/connectivity-search-backend
source ~/miniconda/etc/profile.d/conda.sh
conda env create --quiet --file ~/connectivity-search-backend/environment.yml
conda activate consearch-backend

# Copy $DJ_SECRETS_FILE as ~/connectivity-search-backend/dj_consearch/secrets.yml
if ! [ -f ~/connectivity-search-backend/dj_consearch/secrets.yml ]; then
    cp $DJ_SECRETS_FILE ~/connectivity-search-backend/dj_consearch/secrets.yml
fi

# Create and populate "static" directory (for API view in HTML format)
mkdir -p ~/www/static/
chmod 755 ~/www/ ~/www/static/
cd ~/connectivity-search-backend
python manage.py collectstatic --clear --no-input

# Restart Gunicorn and Nginx
sudo /etc/init.d/supervisor restart
sudo /etc/init.d/nginx restart
