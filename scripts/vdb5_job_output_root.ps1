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
    $cmd.CommandText = "SELECT j.JobDetailID, cfg.DrawingFileOutputLocation, cfg.GenerateReports, cfg.NCFileOutputLocation, cfg.ReplaceSpaceWithUnderscore, cfg.Nesting_SplitNestedSheetDrawings, cfg.Nesting_UseNameIdentifiers FROM AM_JobDetails j JOIN AM_ConfigurationSettings cfg ON j.fkConfigurationSetID = cfg.ConfigurationSettingID WHERE j.JobName = '$job'"
    $r = $cmd.ExecuteReader()
    $loc = ""
    $gen = ""
    $ncloc = ""
    $rswu = ""
    $split = ""
    $useids = ""
    if ($r.Read()) {
        if (-not $r.IsDBNull(1)) { $loc = [string]$r.GetValue(1) }
        if (-not $r.IsDBNull(2)) { $gen = [string]$r.GetValue(2) }
        if (-not $r.IsDBNull(3)) { $ncloc = [string]$r.GetValue(3) }
        if (-not $r.IsDBNull(4)) { $rswu = [string]$r.GetValue(4) }
        if (-not $r.IsDBNull(5)) { $split = [string]$r.GetValue(5) }
        if (-not $r.IsDBNull(6)) { $useids = [string]$r.GetValue(6) }
    }
    $r.Close()
    Write-Output ("output: " + $loc)
    Write-Output ("nc_output: " + $ncloc)
    Write-Output ("generate_reports: " + $gen)
    Write-Output ("replace_space_with_underscore: " + $rswu)
    Write-Output ("split_nested_sheet_drawings: " + $split)
    Write-Output ("use_name_identifiers: " + $useids)
} finally {
    $conn.Close()
}
