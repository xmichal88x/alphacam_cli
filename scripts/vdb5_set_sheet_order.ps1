param(
    [string]$ConfigName,
    [int]$Value
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $config = $ConfigName.Replace("'", "''")
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "UPDATE AM_ConfigurationSettings SET Nesting_SheetOrderType = $Value WHERE ConfigurationSettingName = '$config'"
    Write-Output ("rows: " + $cmd.ExecuteNonQuery())
} finally {
    $conn.Close()
}
