param(
    [string]$JobName,
    [string]$Values
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
    if ($null -eq $jdId) {
        Write-Error "job not found: $JobName"
        exit 1
    }
    $cmd2 = $conn.CreateCommand()
    $cmd2.CommandText = "SELECT CDMOrderDetailID FROM CDM_OrderDetails WHERE fkJobDetailID = $jdId ORDER BY CDMOrderDetailID DESC"
    $r2 = $cmd2.ExecuteReader()
    $ids = New-Object System.Collections.Generic.List[int]
    while ($r2.Read()) { $ids.Add([int]$r2.GetValue(0)) }
    $r2.Close()
    $flags = $Values -split ';'
    if ($ids.Count -lt $flags.Count) {
        Write-Error "row count mismatch: $($ids.Count) rows vs $($flags.Count) values"
        exit 1
    }
    if ($ids.Count -gt $flags.Count) {
        $ids = $ids.GetRange(0, $flags.Count)
    }
    $updated = 0
    for ($i = 0; $i -lt $ids.Count; $i++) {
        $flag = 0
        if ($flags[$i] -eq '1') { $flag = 1 }
        $cmd3 = $conn.CreateCommand()
        $cmd3.CommandText = "UPDATE CDM_OrderDetails SET [HasDrilling] = $flag WHERE CDMOrderDetailID = $($ids[$i])"
        $updated += $cmd3.ExecuteNonQuery()
    }
    Write-Output ("rows: " + $updated)
} finally {
    $conn.Close()
}
