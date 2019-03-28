#!/bin/bash

# This script should be run as user "ubuntu" only.
if [ `whoami` != 'ubuntu' ]; then
    echo "Error: current user is not 'ubuntu'"
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

# Build "static" directory (used by API view in HTML format)
mkdir -p ~/www/static && chmod 755 ~/www/ ~/www/static

# Copy "secrets.yml" into ~/hetmech-backend/dj_hetmech/, then continue
cd ~/hetmech-backend
python manage.py collectstatic --clear --no-input
python manage.py makemigrations dj_hetmech_app
python manage.py migrate

# Restart Gunicorn and Nginx
sudo /etc/init.d/supervisor restart
sudo /etc/init.d/nginx restart
