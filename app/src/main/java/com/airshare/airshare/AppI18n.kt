package com.airshare.airshare

import android.content.Context
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

object AppI18n {
    private val cache = ConcurrentHashMap<String, Map<String, String>>()

    fun load(context: Context, lang: String): Map<String, String> {
        val code = if (lang in SettingsStore.SUPPORTED_CODES) lang else "en"
        cache[code]?.let { return it }
        return try {
            val raw = context.assets.open("web/locales/$code.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
            val obj = JSONObject(raw)
            val map = HashMap<String, String>(obj.length())
            val keys = obj.keys()
            while (keys.hasNext()) {
                val k = keys.next()
                map[k] = obj.optString(k, k)
            }
            cache[code] = map
            map
        } catch (_: Exception) {
            if (code != "en") load(context, "en") else emptyMap()
        }
    }

    fun tr(context: Context, key: String, lang: String, vararg args: Pair<String, Any>): String {
        val dict = load(context, lang)
        var text = dict[key] ?: load(context, "en")[key] ?: key
        for ((k, v) in args) {
            text = text.replace("{$k}", v.toString())
        }
        return text
    }

    fun rawJson(context: Context, lang: String): String {
        val code = if (lang in SettingsStore.SUPPORTED_CODES) lang else "en"
        return try {
            context.assets.open("web/locales/$code.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
        } catch (_: Exception) {
            "{}"
        }
    }
}
