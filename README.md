# AirShare PC

**AirShare PC** is a fast, native Android app (Kotlin + Jetpack Compose) for wireless file transfer between your phone and any PC over local Wi-Fi — no cables, cloud uploads, or desktop software required.

## Key Features

- **Instant Wi-Fi Access** — open your phone's files in any PC browser over the local network with one tap.
- **Biometric & Code Sign-In** — confirm PC connections directly on your phone via fingerprint, a 2-digit verification code, or PIN, with brute-force lockout and security alerts.
- **Trusted & Guest Modes** — grant full read/write access to your own PC or read-only guest access to other devices, and disconnect any client anytime.
- **Remote Folder Switching** — switch shared folders (`Downloads`, `Camera Roll`, `Documents`, or `All Storage`) right from the PC web UI with phone confirmation.
- **Full Media Gallery** — browse your entire photo and video library by date and albums with video thumbnails and built-in media preview.
- **Smart File Manager** — drag-and-drop uploads with SHA-256 verification, streaming ZIP downloads, search, favorites, rename, move/copy, and a safe manual Trash folder.
- **Themes, Parallax & 6 Languages** — Dark and Light themes, 2-column view, 3D Parallax sky, background auto-off timer, and full localization in English, Russian, Ukrainian, Spanish, German, and Lithuanian.

## Quick Start

1. Connect your phone and PC to the same Wi-Fi network (or enable a mobile hotspot).
2. Open **AirShare PC** and tap **Connect**.
3. Open the shown `http://...` address in your PC browser and approve the sign-in on your phone.

## Build

Pushes to `main` automatically build a Debug APK via GitHub Actions (`.github/workflows/build-apk.yml`). When release keystore secrets are configured, signed Release AAB and APK artifacts are built as well.

Crafted by JackBrownUA • Powered by Gemini
