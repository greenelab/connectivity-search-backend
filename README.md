# hetmech backend

[![CircleCI](https://circleci.com/gh/greenelab/hetmech-backend.svg?style=svg)](https://circleci.com/gh/greenelab/hetmech-backend)


## Environment

This repository uses [conda](http://conda.pydata.org/docs/) to manage its environment as specified in [`environment.yml`](environment.yml).
Install the environment with:

```shell
conda env create --file=environment.yml
```

Then use `conda activate hetmech-backend` and `conda deactivate` to activate or deactivate the environment.

## Notebooks

Use the [following command](https://medium.com/ayuth/how-to-use-django-in-jupyter-notebook-561ea2401852) to launch Jupyter Notebook in your browser for interactive development:

```shell
python manage.py shell_plus --notebook
```

## Database

This project uses a PostgreSQL database.
Currently, the database is configured for development, and is run via Docker:

```shell
# https://docs.docker.com/samples/library/postgres/
docker run \
  --name dj_hetmech_db \
  --env POSTGRES_DB=dj_hetmech \
  --env POSTGRES_USER=dj_hetmech \
  --env POSTGRES_PASSWORD=not_secure \
  --volume "$(pwd)"/database:/var/lib/postgresql/data \
  --publish 5432:5432 \
  --detach \
  postgres:11.1
```
