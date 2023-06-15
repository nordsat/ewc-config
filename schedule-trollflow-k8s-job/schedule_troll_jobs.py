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
JOB_SCHEDULER_IMAGE = os.getenv("JOB_SCHEDULER_IMAGE", "mraspaud/trollflow2-kub")
TROLL_FLOW_CONFIGMAP_NAME = os.getenv(
    "JOB_SCHEDULER_TROLL_FLOW_CONFIGMAP_NAME", "satpy-test-fm"
)
JOB_SCHEDULER_COMMAND = [
    "/bin/bash",
    "-c",
    "source /opt/conda/.bashrc && micromamba activate && satpy_cli -p pl.yaml s3://eumetcast/seviri-test/H-000-MSG4__-MSG4________-_________-PRO______-201802281500-__ s3://eumetcast/seviri-test/    H-000-MSG4__-MSG4________-_    ________-EPI______-201802281500-__ s3://eumetcast/seviri-test/H-000-MSG4__-MSG4________-VIS008___-000007___-201802281500-__",
    """ -m '{"start_time": "201802281500", "platform_name": "MSG4"}' """,
]


_LOGGER = logging.getLogger("schedule-k8s-job")

if JOB_SCHEDULER_DEBUG_LEVEL == "INFO":
    logging.basicConfig(level=logging.INFO)

if JOB_SCHEDULER_DEBUG_LEVEL == "DEBUG":
    logging.basicConfig(level=logging.DEBUG)

_LOGGER.info("Running script to schedule trollflow in Kubernetes Jobs.")

_LOGGER.info(f"JOB_SCHEDULER_NAMESPACE set to {JOB_SCHEDULER_NAMESPACE}.")
_LOGGER.info(f"JOB_SCHEDULER_IMAGE set to {JOB_SCHEDULER_IMAGE}.")


def verify_troll_flow_configmap_exists(
    client_api: client.CoreV1Api, namespace: str, configmap_name: str
) -> bool:
    """Get Kubernetes ConfigMap with trollflow configs.

    INPUTS:
    client_api: Client API class for Kubernetes
    namespace:  Kubernetes Namespace where the Kubernetes ConfigMap are located
    configmap_name: Kubernetes ConfigMap name with satpy information.
    """
    if not configmap_name.startswith("satpy-"):
        _LOGGER.error("ConfigMap name needs to start with satpy- prefix.")
        return False

    try:
        # This return : https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1ConfigMap.md
        client_api.read_namespaced_config_map(
            name=configmap_name,
            namespace=namespace,
        )
        _LOGGER.info("V1ConfigMap received from CoreV1Api->read_namespaced_config_map.")
        return True
    except Exception as e:
        _LOGGER.error(
            "Exception when calling CoreV1Api->read_namespaced_config_map: %s\n" % e
        )
        return False


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
                name="AWS_ACCESS_KEY_ID",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1ConfigMapKeySelector(
                        name="nordsat-aws-credentials", key="s3-access-key"
                    )
                ),
            ),
            client.V1EnvVar(
                name="AWS_SECRET_ACCESS_KEY",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1ConfigMapKeySelector(
                        name="nordsat-aws-credentials", key="s3-secret-key"
                    )
                ),
            ),
        ],
        volume_mounts=[
            client.V1VolumeMount(
                name=configmap_name, mount_path="pl.yaml", sub_path="pl.yaml"
            )
        ],
    )

    # Create and configure a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "schedule-job"}),
        spec=client.V1PodSpec(
            restart_policy="Never",
            containers=[container],
            volumes=[
                client.V1Volume(
                    name=configmap_name,
                    config_map=client.V1ConfigMapVolumeSource(
                        name=configmap_name,
                        items=[client.V1KeyToPath(key="pl.yaml", path="pl.yaml")],
                    ),
                )
            ],
        ),
    )

    # Create the specification of deployment
    spec = client.V1JobSpec(template=template, backoff_limit=1)

    # Instantiate the job object
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=spec,
    )

    _LOGGER.debug(f"Kubernetes Job Template inputs: {job}")

    return job


def schedule_job(
    client_api: client.BatchV1Api, namespace: str, job_template: client.V1Job
) -> bool:
    """Schedule the Kubernetes Job.

    INPUTS:
    client_api: Client API class for Kubernetes
    namespace: Kubernetes Namespace where the Kubernetes Job will be scheduled
    job_template: Kubernetes Job template
    """
    try:
        api_response = client_api.create_namespaced_job(
            body=job_template, namespace=namespace
        )
        _LOGGER.info("Job created. status='%s'" % str(api_response.status))
        return True
    except Exception as e:
        _LOGGER.error(
            "Exception when calling BatchV1Api->patch_namespaced_job: %s\n" % e
        )
        return False


def main():
    """Run main script."""
    # Configs can be set in Configuration class directly or using helper
    # utility. If no argument provided, the config will be loaded from
    # default location.
    config.load_kube_config()

    # Verify trollflow configs from Kubernetes exist
    troll_flow_configmap_exists = verify_troll_flow_configmap_exists(
        client_api=client.CoreV1Api(),
        namespace=JOB_SCHEDULER_NAMESPACE,
        configmap_name=TROLL_FLOW_CONFIGMAP_NAME,
    )

    if not troll_flow_configmap_exists:
        raise Exception(
            f"{TROLL_FLOW_CONFIGMAP_NAME} trollflow config is not available in namespace {JOB_SCHEDULER_NAMESPACE}."
            " Please add it in order to schedule satpy processing Kubernetes Job"
        )

    suffix = f"-{datetime.datetime.now():%y%m%d%H%M%S}-{random.getrandbits(64):08x}"
    job_name = f"{TROLL_FLOW_CONFIGMAP_NAME}" + suffix

    _LOGGER.info(f"Preparing for scheduling {job_name} job.")
    # Create a job object with client-python API.
    job_template = create_job_object(
        job_name=job_name, configmap_name=TROLL_FLOW_CONFIGMAP_NAME
    )
    # Schedule actual job in kubernetes cluster
    job_is_scheduled = schedule_job(
        client_api=client.BatchV1Api(),
        namespace=JOB_SCHEDULER_NAMESPACE,
        job_template=job_template,
    )

    if not job_is_scheduled:
        raise Exception(f"Job {job_name} has been scheduled successfully.")
    else:
        _LOGGER.info("Job was scheduled successfully!")


if __name__ == "__main__":
    main()

