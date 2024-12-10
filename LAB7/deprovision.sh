#!/bin/bash

# Script to clean up after Boutique, Istio, and GKE cluster deprovision

cluster=$1
zone=$2

# Check if arguments are provided
if [ -z "$cluster" ] || [ -z "$zone" ]; then
  echo "Usage: $0 <cluster-name> <zone>"
  exit 1
fi

# Delete Istio addons
echo "Deleting Istio addons..."
kubectl delete -f istio-master/samples/addons || echo "Failed to delete Istio addons"

# Delete the Boutique application
echo "Deleting Boutique application..."
kubectl delete -k microservices-demo-main/kustomize || echo "Failed to delete Boutique application"

# Prompt for cluster deletion
read -p "Delete the cluster as well? Enter y to continue, n otherwise: " yn
if [ "$yn" != "y" ]; then
  echo "Leaving cluster intact"
  exit 0
else
  echo "Deleting cluster $cluster in zone ${zone}-a..."
  gcloud container clusters delete "$cluster" --zone="${zone}-a" --quiet || echo "Failed to delete the cluster"
fi
