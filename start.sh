#!/bin/bash
git pull
imageName="transactions_image"
containerName="running_transactions"
docker build -t ${imageName} .
docker rm --force ${containerName}
docker run -p 80:80 --name=${containerName} ${imageName}

