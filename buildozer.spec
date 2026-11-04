[app]
title = AirShare PC
package.name = airshare
package.domain = com.airshare

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js

version = 1.0.0
requirements = python3,kivy,pyjnius,charset-normalizer==2.1.1,android

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 0
