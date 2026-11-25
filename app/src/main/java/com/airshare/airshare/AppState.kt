package com.airshare.airshare

import com.airshare.airshare.server.AuthChallenge
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class TransferProgress(
    val filename: String = "",
    val transferredBytes: Long = 0L,
    val totalBytes: Long = 0L,
    val direction: String = "download",
    val active: Boolean = false,
)

data class ToastEvent(
    val id: Long = System.nanoTime(),
    val message: String,
    val kind: String = "info",
)

object AppState {
    @Volatile
    var isActivityInForeground: Boolean = false

    private val _serverRunning = MutableStateFlow(false)
    val serverRunning: StateFlow<Boolean> = _serverRunning.asStateFlow()

    private val _serverUrl = MutableStateFlow("")
    val serverUrl: StateFlow<String> = _serverUrl.asStateFlow()

    private val _sentCount = MutableStateFlow(0)
    val sentCount: StateFlow<Int> = _sentCount.asStateFlow()

    private val _receivedCount = MutableStateFlow(0)
    val receivedCount: StateFlow<Int> = _receivedCount.asStateFlow()

    private val _transferHistory = MutableStateFlow<List<String>>(emptyList())
    val transferHistory: StateFlow<List<String>> = _transferHistory.asStateFlow()

    private val _currentTransfer = MutableStateFlow(TransferProgress())
    val currentTransfer: StateFlow<TransferProgress> = _currentTransfer.asStateFlow()

    private val _pendingChallenge = MutableStateFlow<AuthChallenge?>(null)
    val pendingChallenge: StateFlow<AuthChallenge?> = _pendingChallenge.asStateFlow()

    private val _toast = MutableStateFlow<ToastEvent?>(null)
    val toast: StateFlow<ToastEvent?> = _toast.asStateFlow()

    private val _activeFolderKey = MutableStateFlow("downloads")
    val activeFolderKey: StateFlow<String> = _activeFolderKey.asStateFlow()

    private val _devicesVersion = MutableStateFlow(0)
    val devicesVersion: StateFlow<Int> = _devicesVersion.asStateFlow()

    fun setServerRunning(running: Boolean, url: String = "") {
        _serverRunning.value = running
        if (url.isNotEmpty() || !running) _serverUrl.value = url
        if (!running) {
            _pendingChallenge.value = null
            _currentTransfer.value = TransferProgress()
        }
    }

    fun setActiveFolder(key: String) {
        _activeFolderKey.value = key
    }

    fun updateTransferProgress(filename: String, done: Long, total: Long, direction: String) {
        _currentTransfer.value = TransferProgress(
            filename = filename,
            transferredBytes = done,
            totalBytes = total,
            direction = direction,
            active = true,
        )
    }

    fun recordTransfer(entry: String, direction: String) {
        if (direction == "upload") _receivedCount.value += 1 else _sentCount.value += 1
        _currentTransfer.value = _currentTransfer.value.copy(active = false)
        _transferHistory.value = (listOf(entry) + _transferHistory.value).take(50)
    }

    fun setPendingChallenge(ch: AuthChallenge?) {
        _pendingChallenge.value = ch
    }

    fun showToast(msg: String, kind: String = "info") {
        _toast.value = ToastEvent(message = msg, kind = kind)
    }

    fun clearToast() {
        _toast.value = null
    }

    fun bumpDevices() {
        _devicesVersion.value += 1
    }
}
