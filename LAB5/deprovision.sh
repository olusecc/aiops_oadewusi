# script to clean up after Boutique, Istio, and GKE cluster deprovision

# arg 1 is the name of the cluster to delete
cluster=$1

# arg 2 is the zone where the cluster should be deleted from, without the -a suffix
zone=$2

# similar to provision script, must run in the root dir that has microservices-demo-main and istio-master subdirs

# delete the Istio addons which in turn will free the 10G PV

kubectl delete -f istio-master/samples/addons

# then delete the Boutique application using the kustomize yaml file

kubectl delete -k microservices-demo-main/kustomize

# finally the cluster can go as well

echo "Delete the cluster as well?"
read -p "Enter y to continue to delete, n otherwise: " yn
if [ "$yn" != "y" ]
then
   echo "Leaving cluster intact"
   exit 999
else
  echo "Continuing to delete cluster"

  gcloud container clusters delete ${cluster} --zone=${zone}-a
fi
