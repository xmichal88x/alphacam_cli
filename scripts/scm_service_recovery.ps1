# Ustawia Recovery dla usługi AlphaCAMGateway: restart po awarii (2x), potem restart co 1 dzien.
# Uwaga: dziala tylko dla uslugi zarejestrowanej w SCM.
# Jesli usluga jest uruchamiana przez nssm, Recovery ustawia sie w nssm:
#   nssm set <name> AppExit Default Restart
$svc = "AlphaCAMGateway"
sc.exe failure $svc reset= 86400 actions= restart/5000/restart/10000/restart/60000
sc.exe failureflag $svc 1
Write-Output "Recovery configured for $svc"
