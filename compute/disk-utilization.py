import oci
import psutil
import datetime
import requests
from pytz import timezone

# use instance principal authentication
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

# initialize service client with instance principal authentication
monitoring_client = oci.monitoring.MonitoringClient(
    config={},
    signer=signer,
    service_endpoint=f"https://telemetry-ingestion.{signer.region}.oraclecloud.com",
)

# get disk usage with psutil
disk_usages = {
    p.mountpoint: psutil.disk_usage(path=p.mountpoint).percent
    for p in psutil.disk_partitions()
    if  not p.mountpoint.startswith('/boot') and 
        not p.mountpoint.startswith('/var/lib/containers/storage/overlay') and 
        not p.mountpoint.startswith('/var/lib/kubelet/pods')
}

timestamp = datetime.datetime.now(tz=timezone('UTC'))

# get instance metadata
instance = requests.get(
    url='http://169.254.169.254/opc/v2/instance/',
    headers={'Authorization': 'Bearer Oracle'},
).json()

# post custom metric to oci monitoring
post_metric_data_response = monitoring_client.post_metric_data(
    post_metric_data_details=oci.monitoring.models.PostMetricDataDetails(
        metric_data=[
            oci.monitoring.models.MetricDataDetails(
                namespace="custom_metrics",
                compartment_id=instance['compartmentId'],
                name="DiskUtilization",
                dimensions={
                    'partisionName': mount_point,
                    'resourceDisplayName': instance['displayName'],
                    'resourceId': instance['id'],
                },
                datapoints=[
                    oci.monitoring.models.Datapoint(
                        timestamp=datetime.datetime.strftime(
                            timestamp, "%Y-%m-%dT%H:%M:%S.%fZ"),
                        value=disk_usages[mount_point]
                    )
                ],
                metadata={
                    'unit': "parcent",
                }
            ) for mount_point in disk_usages
        ]
    )
)

# Get the data from response
print(post_metric_data_response.data)
