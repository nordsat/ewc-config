#!/usr/bin/env python3

"""Schedule troll flow jobs."""

import os
import logging
import datetime
import random

from kubernetes import client, config

# Environment variables
JOB_SCHEDULER_DEBUG_LEVEL = os.getenv("JOB_SCHEDULER_DEBUG_LEVEL", "INFO")
JOB_SCHEDULER_NAMESPACE = os.getenv("JOB_SCHEDULER_NAMESPACE", "nordsat-processing")
JOB_SCHEDULER_IMAGE = os.getenv("JOB_SCHEDULER_IMAGE", "centos:7")
JOB_SCHEDULER_COMMAND = ["bin/bash", "-c", "for i in 9 8 7 6 5 4 3 2 1 ; do echo $i ; done"]

_LOGGER = logging.getLogger("schedule-k8s-job")

if JOB_SCHEDULER_DEBUG_LEVEL == 'INFO':
    logging.basicConfig(level=logging.INFO)

if JOB_SCHEDULER_DEBUG_LEVEL == 'DEBUG':
    logging.basicConfig(level=logging.DEBUG)

_LOGGER.info("Running script to schedule trollflow in Kubernetes Jobs.")

_LOGGER.info(f"JOB_SCHEDULER_NAMESPACE set to {JOB_SCHEDULER_NAMESPACE}.")
_LOGGER.info(f"JOB_SCHEDULER_IMAGE set to {JOB_SCHEDULER_IMAGE}.")


def get_troll_flow_configmaps(client_api: client.CoreV1Api, namespace: str) -> list:
   """Get Kubernetes ConfigMap with trollflow configs.

   INPUTS:
   client_api: Client API class for Kubernetes
   namespace:  Kubernetes Namespace where the Kubernetes ConfigMap are located
   """
   configmap_names = []

   try:
      # This return : https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1ConfigMapList.md
      api_response= client_api.list_namespaced_config_map(
         namespace=namespace,
      )
      _LOGGER.info("V1ConfigMapList received from CoreV1Api->list_namespaced_config_map.")
   except Exception as e:
      _LOGGER.error("Exception when calling CoreV1Api->list_namespaced_config_map: %s\n" % e)
      return configmap_names
   
   # This return list[V1ConfigMap]
   # return: https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1ConfigMap.md
   configmap_list = api_response.items

   configmap_names = []

   for configmap in configmap_list:
      # Filter by prefix (e.g. satpy-)
      if configmap.metadata.name.startswith("satpy-"):
      # get name from metadata: https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1ObjectMeta.md
         configmap_names.append(configmap.metadata.name)

   if len(configmap_names) == 0:
      _LOGGER.warning(f"There are no satpy-* configs for troll-flow in {namespace} namespace!")

   return configmap_names


def create_job_object(job_name: str, configmap_name: str) -> client.V1Job:
   """Create Kubernetes Job object.
   
   INPUTS:
   job_name: Name of the Kubernetes Job
   configmap_name: Name of the Kubernetes ConfigMap provided to the Kubernetes Pod
   """
   # Configure Pod template container
   container = client.V1Container(
      name=f"processing-{configmap_name}",
      image=JOB_SCHEDULER_IMAGE,
      command=JOB_SCHEDULER_COMMAND,
      env=[
         client.V1EnvVar(
            name="TROLL_FLOW_CONFIG",
            value_from=client.V1EnvVarSource(
               config_map_key_ref=client.V1ConfigMapKeySelector(
                  name=configmap_name,
                  key="data"
               )
            )
         )
      ]
   )
    
   # Create and configure a spec section
   template = client.V1PodTemplateSpec(
      metadata=client.V1ObjectMeta(
         labels={"app": "pi"}
      ),
      spec=client.V1PodSpec(
         restart_policy="Never",
         containers=[container]
      )
   )
 
   # Create the specification of deployment
   spec = client.V1JobSpec(
      template=template,
      backoff_limit=4
   )

   # Instantiate the job object
   job = client.V1Job(
      api_version="batch/v1",
      kind="Job",
      metadata=client.V1ObjectMeta(name=job_name),
      spec=spec
   )

   _LOGGER.debug(f"Kubernetes Job Template inputs: {job}")

   return job


def schedule_job(
   client_api: client.BatchV1Api,
   namespace: str,
   job_template: client.V1Job
) -> bool:
   """Schedule the Kubernetes Job.

   INPUTS:
   client_api: Client API class for Kubernetes
   namespace: Kubernetes Namespace where the Kubernetes Job will be scheduled
   job_template: Kubernetes Job template
   """
   try: 
      api_response = client_api.create_namespaced_job(
         body=job_template,
         namespace=namespace
      )
      _LOGGER.info("Job created. status='%s'" % str(api_response.status))
      return True
   except Exception as e:
      _LOGGER.error("Exception when calling BatchV1Api->patch_namespaced_job: %s\n" % e)
      return False


def main():
   """Main script"""
   # Configs can be set in Configuration class directly or using helper
   # utility. If no argument provided, the config will be loaded from
   # default location.
   config.load_kube_config()
   
   # Get trollflow configs from Kubernetes
   troll_flow_configs_names = get_troll_flow_configmaps(
      client_api=client.CoreV1Api(),
      namespace=JOB_SCHEDULER_NAMESPACE
   )
   if not troll_flow_configs_names:
      raise Exception(
         f"You need to have at least one trollflow config in namespace {JOB_SCHEDULER_NAMESPACE}"
         " in order to schedule satpy processing Kubernetes Job"
   )
   _LOGGER.info(f"ConfigMap names for troll flow configs: {troll_flow_configs_names}")

   expected_job_counter = len(troll_flow_configs_names)
   jobs_history = {}

   # Iterate over all  trollflow configs and create k8s jobs
   for configmap_name in troll_flow_configs_names:
      suffix = f"-{datetime.datetime.now():%y%m%d%H%M%S}-{random.getrandbits(64):08x}"
      job_name = f"{configmap_name}" + suffix
      
      _LOGGER.info(f"Preparing for scheduling {job_name} job.")
      # Create a job object with client-python API.
      job_template = create_job_object(
         job_name=job_name,
         configmap_name=configmap_name
      )
      # Schedule actual job in kubernetes cluster
      job_is_scheduled = schedule_job(
         client_api=client.BatchV1Api(),
         namespace=JOB_SCHEDULER_NAMESPACE,
         job_template=job_template
      )
      jobs_history[job_name] = job_is_scheduled

   if sum([int(v) for v in jobs_history.values()]) != expected_job_counter:
      raise Exception(
         f"Not all jobs have been scheduled successfully. See history: {jobs_history}"
      )
   else:
      _LOGGER.info(f"Scheduled successfully all jobs: {jobs_history}")


if __name__ == '__main__':
   main()
