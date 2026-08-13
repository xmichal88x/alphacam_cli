param(
    [string]$JobName,
    [int]$MaterialID
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $job = $JobName.Replace("'", "''")
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT JobDetailID FROM AM_JobDetails WHERE JobName = '$job'"
    $r = $cmd.ExecuteReader()
    $jdId = $null
    if ($r.Read()) { $jdId = [int]$r.GetValue(0) }
    $r.Close()
    if ($null -ne $jdId) {
        $cmd2 = $conn.CreateCommand()
        $cmd2.CommandText = "UPDATE CDM_OrderDetails SET [fkMaterialID] = $MaterialID WHERE fkJobDetailID = $jdId"
        Write-Output ("detail_rows: " + $cmd2.ExecuteNonQuery())
    } else {
        Write-Output "detail_rows: 0"
    }
} finally {
    $conn.Close()
}
