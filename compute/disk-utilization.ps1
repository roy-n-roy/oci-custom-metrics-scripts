Import-Module OCI.PSModules.Monitoring

$timestamp = Get-Date

# get instance metadata
$instance = Invoke-RestMethod `
    -Method GET `
    -Uri "http://169.254.169.254/opc/v2/instance/" `
    -Headers @{Authorization = "Bearer Oracle"}

# post custom metric to oci monitoring
$metrics_data = [System.Collections.Generic.List[Oci.MonitoringService.Models.MetricDataDetails]]::new()
Get-Volume | ForEach-Object {
    $dimensions = [System.Collections.Generic.Dictionary[[string],[string]]]::new()
    $dimensions.Add("partisionName", "$($_.DriveLetter)" + $null -eq $_.FriendlyName ? "" : " ($($_.FriendlyName))")
    $dimensions.Add("resourceDisplayName", $instance.displayName)
    $dimensions.Add("resourceId", $instance.id)
    $metadata = [System.Collections.Generic.Dictionary[[string],[string]]]::new()
    $metadata.Add("unit", "parcent")


    $metrics_data += [Oci.MonitoringService.Models.MetricDataDetails]@{
        Namespace = "custom_metrics"
        CompartmentId = $instance.compartmentId
        Name = "DiskUtilization"
        Dimensions = $dimensions
        Datapoints = @(
            [Oci.MonitoringService.Models.Datapoint]@{
                    Timestamp = $timestamp.ToUniversalTime().ToString("o")
                    Value = ($_.Size - $_.SizeRemaining) * 100/$_.Size
            }
        )
        Metadata = $metadata
    }
}
$post_metric_data_response = Submit-OCIMonitoringMetricData `
    -AuthType InstancePrincipal `
    -Endpoint "https://telemetry-ingestion.$($instance.region).oraclecloud.com" `
    -PostMetricDataDetails (
        [Oci.MonitoringService.Models.PostMetricDataDetails]@{
            MetricData = $metrics_data
        }
    )

# Get the data from response
Write-Host $post_metric_data_response.FailedMetrics
