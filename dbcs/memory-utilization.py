import oci
import datetime
from pytz import timezone
from pexpect import pxssh
import re

database_id = 'ocid1.database.oc1.ap-osaka-1.anvwsljrnllsviaalkqcqqdu6iybrvs2nf4picgbdita52migjhtjlpbl5xq'
db_metric_namespace = 'custom_db_metrics'
pattern = re.compile(r'(.+):\s+([0-9]+)(\s+kB|)')

# use instance principal authentication
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

# initialize service client with instance principal authentication
db_client = oci.database.DatabaseClient(
    config={},
    signer=signer,
)

monitoring_client = oci.monitoring.MonitoringClient(
    config={},
    signer=signer,
    service_endpoint=f"https://telemetry-ingestion.{signer.region}.oraclecloud.com",
)

# get database infomations
db = db_client.get_database(database_id=database_id).data

db_system = db_client.get_db_system(db_system_id=db.db_system_id).data

db_nodes = db_client.list_db_nodes(compartment_id=db_system.compartment_id, db_system_id=db_system.id).data


times_stamp = datetime.datetime.strftime(datetime.datetime.now(tz=timezone('UTC')), "%Y-%m-%dT%H:%M:%S.%fZ")

for db_node in db_nodes:
    metric_data_list = []
    try:
        # ssh login to dbcs instance
        ssh = pxssh.pxssh()
        ssh.login(server=f"{db_node.hostname}.{db_system.domain}", username='opc', ssh_key=True)

        # get instance memory infomation
        ssh.sendline('cat /proc/meminfo')
        ssh.prompt()

        meminfo = {m[0]: m[1]
                for m in pattern.findall(ssh.before.decode(encoding='utf-8'))}

        # ssh logout
        ssh.logout()

        dimensions = {
            'hostName': db_node.hostname,
            'resourceDisplayName': db_system.display_name,
            'resourceId': db.id,
            'resourceName': db.db_name,
        }

        # add memory usage to metrics
        metric_data_list.extend([
            oci.monitoring.models.MetricDataDetails(
                namespace=db_metric_namespace,
                compartment_id=db.compartment_id,
                name=str(name).replace('(','_').replace(')',''),
                dimensions=dimensions,
                datapoints=[
                    oci.monitoring.models.Datapoint(
                        timestamp=times_stamp,
                        value=float(meminfo[name])
                    )
                ],
                metadata={
                    'unit': "kilobytes",
                }
            ) for name in meminfo
        ])
        # add utilizations to metrics
        metric_data_list.append(
            oci.monitoring.models.MetricDataDetails(
                namespace=db_metric_namespace,
                compartment_id=db.compartment_id,
                name="MemoryUtilization",
                dimensions=dimensions,
                datapoints=[
                    oci.monitoring.models.Datapoint(
                        timestamp=times_stamp,
                        value=float(int(meminfo['MemTotal']) - int(meminfo['MemFree'])) * 100 / float(meminfo['MemTotal'])
                    )
                ],
                metadata={
                    'unit': "parcent",
                }
            )
        )
        metric_data_list.append(
            oci.monitoring.models.MetricDataDetails(
                namespace=db_metric_namespace,
                compartment_id=db.compartment_id,
                name="SwapUtilization",
                dimensions=dimensions,
                datapoints=[
                    oci.monitoring.models.Datapoint(
                        timestamp=times_stamp,
                        value=float(int(meminfo['SwapTotal']) - int(meminfo['SwapFree'])) * 100 / float(meminfo['SwapTotal'])
                    )
                ],
                metadata={
                    'unit': "parcent",
                }
            )
        )
        # post custom metric to oci monitoring
        post_metric_data_response = monitoring_client.post_metric_data(
            post_metric_data_details=oci.monitoring.models.PostMetricDataDetails(
                metric_data=metric_data_list
            )
        )
        # Get the data from response
        print(post_metric_data_response.data)
    except:
        None
