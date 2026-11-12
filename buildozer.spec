[app]
title = AirShare PC
package.name = airshare
package.domain = com.airshare
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash_blank.png
android.presplash_color = #14171A

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js

# Единый источник версии — константа APP_VERSION в config.py
version.regex = APP_VERSION = ['"](.*)['"]
version.filename = %(source.dir)s/config.py
requirements = python3,kivy,pyjnius,charset-normalizer==2.1.1,android

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK,MANAGE_EXTERNAL_STORAGE,POST_NOTIFICATIONS
android.api = 35
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = master
p4a.hook = %(source.dir)s/p4a_hook.py

[buildozer]
log_level = 2
warn_on_root = 0
