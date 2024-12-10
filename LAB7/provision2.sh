# run this script from the root project directory that must contain two subdirectories:
# -- "microservices-demo-main" which then has a "kustomize" directory of the Boutique microservices-demo under it, and
# -- "istio-master" which has a "samples/addons" directory containing kiali, prometheus, and grafana

# be sure to set the components config in kustomize to include istio before running the first time!

# arg 1 is the name of the cluster to create
cluster=$1
# arg 2 is the project under which the cluster should be created
projectID=$2
# arg 3 is the zone where the cluster should be created, without the -a suffix
zone=$3

# check to be sure we don't already have a cluster running, quit if so!

cluster_check=`gcloud container clusters list`
echo ${cluster_check}

if [ -z "$cluster_check" ]
then
      echo "No current clusters found, continuing to deploy one"

      gcloud container clusters create ${cluster} \
          --project=${projectID} \
          --zone=${zone}-a \
          --machine-type=e2-standard-4 \
          --num-nodes=1 \
          --workload-pool ${projectID}.svc.id.goog \
          --gateway-api "standard"
else
      echo "You already have a cluster deployed, do you want to redeploy Boutique and Istio using it?"
      read -p "Enter y to continue to deploy, n otherwise: " yn
      if [ "$yn" != "y" ]
      then
         exit 999
      else
        echo "Continuing to deploy Istio and Boutique components"
      fi
fi

# install istioctl with enough capacity to run demos
istioctl install --set profile=demo -y

ret=`kubectl get deploy -n istio-system | grep istiod`
echo $ret

if [ -z "$ret" ]
then
      echo "istio install failed, please retry...exiting"
      exit 1
else
      echo "istio install complete"
fi

# mark the default namespace to set up istio side-car injection when app is deployed
kubectl label namespace default istio-injection=enabled --overwrite=true

# fetch the "all" firewall rule name so it can be updated with ports to open
cluster_info=`gcloud compute firewall-rules list --filter="name~gke-${cluster}-[0-9a-z-]*-all" --format=json`

# get just the raw text name for the "all" rule using jq
cluster_name=`echo $cluster_info | jq -r '.[0].name'`

echo $cluster_name

# update the firewall "all" rule to open needed ports
gcloud compute firewall-rules update $cluster_name --allow tcp:10250,tcp:443,tcp:15017

# install the app using kustomize (be sure to have set the kustomize config first time running this)
kubectl apply -k microservices-demo-main/kustomize

# patch the loadgenerator yaml to route traffic through the istio gateway...be sure you have patch_lg.json in your dir
kubectl patch deploy loadgenerator -p "$(cat patch_lg.json)" -o yaml

# check the service to be sure the external ip is being provisioned...may need to do this a couple of times afterwards
kubectl get svc

# finally, install the istio addons

kubectl apply -f istio-master/samples/addons
kubectl get svc -n istio-system
