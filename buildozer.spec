[app]
title = AirShare PC
package.name = airshare
package.domain = com.airshare

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js

version = 1.0.0
requirements = python3,kivy,android

orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.2.1

fullscreen = 0

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,FOREGROUND_SERVICE,FOREGROUND_SERVICE_SPECIAL_USE,POST_NOTIFICATIONS
android.api = 33
android.minapi = 24
android.ndk_api = 33
android.archs = arm64-v8a,armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 0
