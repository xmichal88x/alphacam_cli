# Ustawia Recovery dla uslugi AlphaCAMGateway: restart po awarii.
# Obsluguje dwa przypadki:
#   1) Usluga pod NSSM (PathName zawiera nssm.exe) -> recovery przez parametry nssm:
#      AppExit Default Restart + AppRestartDelay. Uwaga: `sc failure` wtedy NIE dziala
#      (restartem zarzadza nssm przez wlasne parametry AppExit/AppRestartDelay).
#   2) Zwykla usluga SCM -> sc.exe failure (restart po awarii, reset po 1 dniu) + failureflag.
$svc = "AlphaCAMGateway"

$service = Get-CimInstance Win32_Service -Filter "Name='$svc'"
if ($null -eq $service) {
    Write-Error "Usluga '$svc' nie istnieje w SCM."
    exit 1
}

$pathName = [string]$service.PathName
$isNssm = $pathName -like "*nssm*"

if ($isNssm) {
    Write-Output "Usluga '$svc' dziala pod NSSM (PathName: $pathName) - konfiguruje recovery przez nssm."

    # Wyciagnij sciezke nssm.exe z PathName (obetnij argumenty; obsluz sciezki w cudzyslowach).
    $p = $pathName.Trim()
    $nssm = ""
    if ($p.StartsWith('"')) {
        $end = $p.IndexOf('"', 1)
        if ($end -gt 0) { $nssm = $p.Substring(1, $end - 1) }
    } else {
        $space = $p.IndexOf(' ')
        if ($space -gt 0) { $nssm = $p.Substring(0, $space) } else { $nssm = $p }
    }

    # Fallback: nssm z PATH, gdy sciezka z PathName nie istnieje.
    if (-not (Test-Path $nssm)) {
        if (Get-Command "nssm" -ErrorAction SilentlyContinue) {
            $nssm = "nssm"
        } else {
            Write-Error "Nie znaleziono nssm.exe (PathName: $pathName ani w PATH)."
            exit 1
        }
    }

    & $nssm set $svc AppExit Default Restart
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Nie udalo sie ustawic 'AppExit Default Restart' przez nssm."
        exit 1
    }

    & $nssm set $svc AppRestartDelay 5000
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Nie udalo sie ustawic 'AppRestartDelay 5000' przez nssm."
        exit 1
    }

    $appExit = (& $nssm get $svc AppExit Default)
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Nie udalo sie odczytac 'AppExit Default' przez nssm."
        exit 1
    }

    Write-Output "NSSM recovery skonfigurowany dla $svc (AppExit Default = $appExit, AppRestartDelay = 5000)."
} else {
    Write-Output "Usluga '$svc' dziala jako zwykla usluga SCM - konfiguruje recovery przez sc.exe."

    sc.exe failure $svc reset= 86400 actions= restart/5000/restart/10000/restart/60000
    if ($LASTEXITCODE -ne 0) {
        Write-Error "sc.exe failure nie powiodlo sie dla $svc."
        exit 1
    }

    sc.exe failureflag $svc 1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "sc.exe failureflag nie powiodlo sie dla $svc."
        exit 1
    }

    Write-Output "SCM recovery skonfigurowany dla $svc (restart po awarii, reset= 86400)."
}
