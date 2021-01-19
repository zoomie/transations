#!/bin/bash
imageName="transactions_image"
containerName="running_transactions"
docker rm --force ${containerName}
docker build -t ${imageName} .
docker run -p 80:80 --name=${containerName} ${imageName}

