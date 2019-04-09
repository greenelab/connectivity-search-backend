# Deployment

This directory includes a shell script `setup.sh` and a few configuration files
for packages that are required for hetmech backend deployment.

## Prerequisites of Deployment Box:
 - OS: Ubuntu 18.04
 - Path of a Django secrets file (default name is `secrets.yml`)
 - User account `ubuntu` that has `sudo` privilege

## Deployment Steps:

Type the following command on the deplyment box:
```shell
./setup.sh
```

Here is a summary of what this script does:
 - Install/configure Nginx web server
 - Install SSL certificate (issued by Let's Encrypt)
 - Install a daily cron job to upgrade packages using `apt` command
 - Install/configure Miniconda
 - Download hetmech-backend code from Github and create a Conda environment
 - Install/configure `supervisord`, which runs `Gunicorn` as a daemon

Please reboot the deployment box at the end to ensure that the new
configurations will become effective.
