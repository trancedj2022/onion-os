# Onion OS 26.2.6-r2 Execution Guide

This guide reflects the public `26.2.6-r2` release. Older 26.2.0/26.2.5 notes are historical and should not be used as the recommended download target.

## Release Target

`26.2.6-r2` is the current public replacement for the earlier 26.2.x images. It focuses on:

- boot reliability after 26.2.5 reported `invalid magic number` / `you need to load the kernel first`;
- desktop polish fixes found during VirtualBox testing;
- installer branding so Live installation produces Onion OS, not a Debian-looking install;
- update button and OTA clarity;
- HDD/SSD and low-memory runtime tuning.

## Final Artifact

```text
output/onion-os-26.2.6-r2-home-amd64-f2823efa.iso
```

```text
Size:   2568552448
SHA256: f2823efa5545502fb6ec93ad8b476b5821c915ccede8366283f4c560fc26ce25
```

Official public URL:

```text
https://scallion.uno/iso/onion-os-26.2.6-r2-home-amd64-f2823efa.iso
```

GitHub release:

```text
https://github.com/bzm2008/onion-os/releases/tag/v26.2.6-r2
```

## GitHub Release Assets

GitHub uses split assets for the ISO:

```text
onion-os-26.2.6-r2-home-amd64.iso.part01
onion-os-26.2.6-r2-home-amd64.iso.part02
onion-os-26.2.6-r2-home-amd64.iso.sha256
SHA256SUMS
```

Merge and verify:

```bash
cat onion-os-26.2.6-r2-home-amd64.iso.part01 onion-os-26.2.6-r2-home-amd64.iso.part02 > onion-os-26.2.6-r2-home-amd64.iso
sha256sum -c onion-os-26.2.6-r2-home-amd64.iso.sha256
```

## Verification Checklist

Build or repack output must pass:

- `/live/vmlinuz`, `/live/initrd`, and `/live/filesystem.squashfs` exist.
- Extracted `/live/vmlinuz` is a Linux bzImage, not zeroed data.
- ISO volume label is `ONION_OS_2626`.
- `xorriso -report_el_torito` shows both BIOS and UEFI boot images.
- `fdisk -l` should not show the old HFS/APM hybrid layout.
- QEMU or VirtualBox reaches the Onion OS boot menu and starts loading kernel/initrd.
- Live mode auto-logins as `onion`; Ventoy/Live should not ask for username/password.
- Desktop wallpaper is Onion-branded.
- White-background icon overrides are not present on main Onion icons.
- `Onion 安全管家` opens or shows a readable diagnostic log.
- Desktop installer is `Install Onion OS` / `安装 Onion OS`, not `Install Debian`.
- Installed system identity is Onion OS after Calamares completes.
- Desktop update button opens a clear check/download/install flow.

## OTA Publish Flow

Current OTA endpoint:

```text
https://scallion.uno/api/onion-update/check?version=26.2.0&channel=stable
```

Expected public response:

```json
{
  "version": "26.2.6-r2",
  "ready": true,
  "status": "ready",
  "download_url": "https://scallion.uno/iso/onion-os-26.2.6-r2-home-amd64-f2823efa.iso",
  "checksum": "f2823efa5545502fb6ec93ad8b476b5821c915ccede8366283f4c560fc26ce25",
  "size": 2568552448
}
```

Recommended deploy helper:

```bash
python scallion/scripts/deploy-onion-26.2-server.py \
  --check --deploy --verify-public \
  --version 26.2.6-r2 \
  --release-date 2026-06-21 \
  --iso-name onion-os-26.2.6-r2-home-amd64-f2823efa.iso \
  --public-iso-name onion-os-26.2.6-r2-home-amd64-f2823efa.iso \
  --sha256 f2823efa5545502fb6ec93ad8b476b5821c915ccede8366283f4c560fc26ce25 \
  --size 2568552448
```

## User Communication

Say plainly:

- Onion OS can run on 2GB RAM, but a heavy WeChat account may still consume too much memory.
- Prefer desktop buttons: Onion Settings, update button, app folders, All Disks, and GUI repair tools.
- Command-line usage is for advanced troubleshooting, not the normal path.
- For Rufus/Ventoy boot issues, test both ISO mode and DD mode, and record the exact error text and machine generation.
