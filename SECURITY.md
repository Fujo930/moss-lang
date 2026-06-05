# Security policy

Moss is experimental alpha software and should not currently execute untrusted
source code.

## Supported versions

Only the latest tagged version receives fixes.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature when available.
If private reporting is unavailable, open an issue that describes the affected
surface without publishing exploit details.

Particularly important areas include workspace path containment, network and
filesystem effects, package boundaries, future host-language bindings, and the
future C virtual machine.
