# connectivity search backend

[![CircleCI](https://circleci.com/gh/greenelab/connectivity-search-backend.svg?style=svg)](https://circleci.com/gh/greenelab/connectivity-search-backend)

This django application powers the API available at <https://search-api.het.io/>.

## Environment

This repository uses [conda](http://conda.pydata.org/docs/) to manage its environment as specified in [`environment.yml`](environment.yml).
Install the environment with:

```shell
conda env create --file=environment.yml
```

Then use `conda activate hetmech-backend` and `conda deactivate` to activate or deactivate the environment.

## Secrets

Users must supply `dj_hetmech/secrets.yml` with the database connection information.
See [`dj_hetmech/secrets-template.yml`](dj_hetmech/secrets-template.yml) for what fields should be defined.
These secrets will determine whether django connects to a local database or a remote database.

## Notebooks

Use the [following command](https://medium.com/ayuth/how-to-use-django-in-jupyter-notebook-561ea2401852) to launch Jupyter Notebook in your browser for interactive development:

```shell
python manage.py shell_plus --notebook
```

## Server

A local development server can be started with the command:

```shell
python manage.py runserver
```

This exposes the API at <http://localhost:8000/v1/>.

## Database

This project uses a PostgreSQL database.
The deployed version of this application uses a remote database.

To erect a new database locally for development, run:

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
