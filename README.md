# Canary | Markets helper
![alt text](backend/markets/static/markets/canary.png "Canary")

### Project intends to help getting important data of dynamics in market values, yields, shares.

## Prerequisite
* Postgres running with available DB and User according to `.env`

## Deployment
* copy project files/clone from git repo
* copy `.env.template` to `.env`. Edit database fields accordingly or leave default
* run `./setup.sh`
* add your server ip address/domain name to `backend.config.settings.ALLOWED_HOSTS`


## Start server
* run `./runserver.sh`

## Updates
Server automatically tries to fetch new data from sources daily at 23:59:59

To run data sync manually:
* activate virtual environment `source venv/bin/activate`
* run `python backend/manage.py sync daily`