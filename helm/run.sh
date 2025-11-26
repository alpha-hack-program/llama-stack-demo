#!/bin/sh
APP_NAME=eligibility
# VALUES="--values intel.yaml"
# VALUES="--values nvidia.yaml"
# VALUES=""

helm template . --name-template ${APP_NAME} \
  --include-crds ${VALUES} 
  