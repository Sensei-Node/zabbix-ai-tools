#!/bin/bash

REPOS=$(grep image docker-compose.yml |  awk '{print $2}' | cut -d '}' -f 2 | cut -d ':' -f 1)

for REPO in $REPOS; do
    echo "Checking repository [${REPO}]"
    IMAGES_TO_PRUNE=$( aws ecr list-images --region ${AWS_REGION} --repository-name ${REPO} --filter "tagStatus=UNTAGGED" --query 'imageIds[*]' --output json )

    aws ecr batch-delete-image --region ${AWS_REGION} --repository-name ${REPO} --image-ids "${IMAGES_TO_PRUNE}" || true
done
