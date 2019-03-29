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
sudo cp hetmech-api.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/hetmech-api.conf /etc/nginx/sites-enabled/

# Use supervisord to take care of Gunicorn daemon
sudo apt install supervisor --yes
sudo cp gunicorn.conf /etc/supervisor/conf.d/

# Miniconda environment setup
sudo apt install git wget python3 python3-pip gcc --yes
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh --output-document ~/miniconda.sh
bash ~/miniconda.sh -b -p ~/miniconda
echo "source ~/miniconda/etc/profile.d/conda.sh" >> ~/.bashrc

rm -rf ~/hetmech-backend
git clone https://github.com/greenelab/hetmech-backend.git ~/hetmech-backend
source ~/miniconda/etc/profile.d/conda.sh
conda env create --quiet --file ~/hetmech-backend/environment.yml
conda activate hetmech-backend

# Copy $DJ_SECRETS_FILE as ~/hetmech-backend/dj_hetmech/secrets.yml
if ! [ -f ~/hetmech-backend/dj_hetmech/secrets.yml ]; then
    cp $DJ_SECRETS_FILE ~/hetmech-backend/dj_hetmech/secrets.yml
fi

# Create and populate "static" directory (for API view in HTML format)
mkdir -p ~/www/static/
chmod 755 ~/www/ ~/www/static/
cd ~/hetmech-backend
python manage.py collectstatic --clear --no-input

# Restart Gunicorn and Nginx
sudo /etc/init.d/supervisor restart
sudo /etc/init.d/nginx restart
