[CmdletBinding()]
param (
    [Parameter(Position=0)]
    [string]$problem,

    [Alias("h")]
    [switch]$help,

    [Alias("s")]
    [switch]$silent,

    [Alias("c")]
    [string]$config,

    [Alias("r")]
    [string]$result,

    [Alias("t")]
    [string]$teams
)

$mounts = ""
$docker_args = ""

if ($problem) {
    $mounts += "--mount type=bind,source=" + (Resolve-Path $problem) + ",target=/algobattle/problem,readonly "
    $docker_args += "/algobattle/problem "
}
if ($help) {
    $docker_args += "-h "
}
if ($silent) {
    $docker_args += "-s "
}
if ($config) {
    $mounts += "--mount type=bind,source=" + (Resolve-Path $config) + ",target=/algobattle/config,readonly "
    $docker_args += "-c /algobattle/config "
}
if ($result) {
    $mounts += "--mount type=bind,source=" + (Resolve-Path $result) + ",target=/algobattle/result "
    $docker_args += "-r /algobattle/result "
}
if ($teams) {
    $mounts += "--mount type=bind,source=" + (Resolve-Path $teams) + ",target=/algobattle/teams "
}

$tempFolderPath = Join-Path $Env:Temp $(New-Guid)
New-Item -Type Directory -Path $tempFolderPath | Out-Null

try {
    Invoke-Expression ("docker run -it --rm " +
        "--mount type=bind,source=" + $tempFolderPath + ",target=/algobattle/io " +
        "--env ALGOBATTLE_IO_DIR=" + $tempFolderPath + " " +
        "--mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock " +
        $mounts +
        "algobattle " +
        $docker_args 
    )
} finally {
    Remove-Item -LiteralPath $tempFolderPath -Force -Recurse
}
