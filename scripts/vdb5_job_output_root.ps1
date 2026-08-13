param(
    [string]$JobName
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $job = $JobName.Replace("'", "''")
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT j.JobDetailID, cfg.DrawingFileOutputLocation FROM AM_JobDetails j JOIN AM_ConfigurationSettings cfg ON j.fkConfigurationSetID = cfg.ConfigurationSettingID WHERE j.JobName = '$job'"
    $r = $cmd.ExecuteReader()
    $loc = ""
    if ($r.Read()) {
        if (-not $r.IsDBNull(1)) { $loc = [string]$r.GetValue(1) }
    }
    $r.Close()
    Write-Output ("output: " + $loc)
} finally {
    $conn.Close()
}
