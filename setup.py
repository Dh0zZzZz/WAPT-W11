# -*- coding: utf-8 -*-
from setuphelpers import *
import os

def install():
    iso_path   = makepath(basedir, "Win11_24H2_French_x64.iso")
    log_path   = r"C:\install\w11log.txt"
    marker_file = r"C:\install\w11_done.txt"
    ps1_path   = makepath(basedir, "w11_upgrade.ps1")

    if isfile(marker_file):
        print("Mise à jour déjà appliquée. Fin du script.")
        return

    ps_script = r'''
$ErrorActionPreference = "Stop"
$logFile = "C:\install\w11log.txt"
function Log($message) {
    $timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Add-Content $logFile "$timestamp - $message"
}

Log("=== Début du script de mise à niveau Windows 10 vers Windows 11 24H2 ===")

# Vérification de l'OS (Windows 10 ou 11 requis)
try {
    $osCaption = (Get-CimInstance -ClassName Win32_OperatingSystem).Caption
} catch {
    $osCaption = ""
}
if ($osCaption -notlike "*Windows 10*" -and $osCaption -notlike "*Windows 11*") {
    Log("Système d'exploitation actuel non supporté pour ce script. Arrêt du script.")
    exit 0
}

# Vérification du fichier témoin
$markerFile = "C:\install\w11_done.txt"
if (Test-Path $markerFile) {
    Log("Fichier témoin déjà présent ($markerFile). Mise à niveau déjà effectuée. Arrêt du script.")
    exit 0
}

# Vérification d’un redémarrage en attente
$pendingReboot = $false
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') { $pendingReboot = $true }
if (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue) { $pendingReboot = $true }
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') { $pendingReboot = $true }
if ($pendingReboot) {
    Log("Un redémarrage en attente a été détecté. Veuillez redémarrer le système avant de relancer la mise à niveau.")
    exit 1
}

# Montage de l'ISO et détection du lecteur
$isoPath = "%ISO_PATH%"
if (!(Test-Path $isoPath)) {
    Log("ISO introuvable à l'emplacement $isoPath. Abandon de la mise à niveau.")
    exit 1
}
try {
    $diskImage = Get-DiskImage -ImagePath $isoPath -ErrorAction Stop
} catch {
    $diskImage = $null
}
if ($diskImage -and $diskImage.IsMounted) {
    $driveLetter = ($diskImage | Get-Volume).DriveLetter
    Log("ISO déjà montée sur $driveLetter`:\\")
} else {
    Log("Montage de l'ISO $isoPath ...")
    try {
        $diskImage = Mount-DiskImage -ImagePath $isoPath -PassThru
        $driveLetter = ($diskImage | Get-Volume).DriveLetter
        Log("ISO montée sur le lecteur $driveLetter`:\\")
    } catch {
        Log("Échec du montage de l'ISO. Erreur : $($_.Exception.Message)")
        exit 1
    }
}

# Construire les arguments de setup.exe (NoReboot mode)
$setupExe  = "$driveLetter`:\setup.exe"
$arguments = "/auto upgrade /DynamicUpdate disable /Quiet /Compat IgnoreWarning /EULA accept /Telemetry Disable /ShowOOBE none /NoReboot"
Log("Lancement de l'installation silencieuse : $setupExe $arguments")

# Lancer l'installation et attendre la fin du processus
try {
    $process = Start-Process -FilePath $setupExe -ArgumentList $arguments -Wait -PassThru
} catch {
    Log("Erreur lors de l'exécution de setup.exe : $($_.Exception.Message)")
    try { Dismount-DiskImage -ImagePath $isoPath } catch {}
    exit 1
}
$exitCode = $process.ExitCode
Log("Processus d'installation terminé avec le code de sortie $exitCode")

# Démontage de l'ISO
try {
    Dismount-DiskImage -ImagePath $isoPath
    Log("ISO démontée.")
} catch {
    Log("Erreur lors du démontage de l'ISO : $($_.Exception.Message)")
}

# Analyser le résultat et créer le fichier témoin si succès
if ($exitCode -eq 3) {
    Log("Mise à niveau lancée avec succès (installation en attente de redémarrage manuel). Création du fichier témoin.")
    New-Item -Path $markerFile -ItemType File -Force | Out-Null
    exit 0
} elseif ($exitCode -eq 0) {
    Log("Aucune mise à niveau nécessaire (code 0). Création du fichier témoin.")
    New-Item -Path $markerFile -ItemType File -Force | Out-Null
    exit 0
} else {
    Log("La mise à niveau a échoué ou a été interrompue (code $exitCode). Aucun fichier témoin créé.")
    exit $exitCode
}
'''.replace('%ISO_PATH%', iso_path)

    with open(ps1_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    run(f'powershell.exe -ExecutionPolicy Bypass -File "{ps1_path}"', timeout=7200)
