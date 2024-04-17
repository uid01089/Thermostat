pip freeze > requirements.txt
docker build -t thermostat -f Dockerfile .
docker tag thermostat:latest docker.diskstation/thermostat
docker push docker.diskstation/thermostat:latest