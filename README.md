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