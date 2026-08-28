
[System.Reflection.Assembly]::LoadFrom((Resolve-Path 'LibreHardwareMonitorLib.dll')) | Out-Null
 = [System.AppDomain]::CurrentDomain.GetAssemblies() | Where-Object { .GetName().Name -eq 'LibreHardwareMonitorLib' }
 = .GetManifestResourceNames()
foreach ( in ) {
    Write-Host 'Found Resource:' 
     = .GetManifestResourceStream()
     = New-Object byte[] .Length
    .Read(, 0, .Length) | Out-Null
    [System.IO.File]::WriteAllBytes(, )
    Write-Host 'Exported:'  'Size:' .Length
}
