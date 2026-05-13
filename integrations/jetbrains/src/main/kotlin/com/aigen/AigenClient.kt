package com.aigen

import com.intellij.openapi.diagnostic.Logger
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

/**
 * Lightweight HTTP client for the AIGEN protocol. Uses java.net.HttpURLConnection
 * to avoid pulling in OkHttp / kotlinx.serialization.
 */
object AigenClient {
    private val LOG = Logger.getInstance("AigenClient")

    fun baseUrl(): String = AigenSettings.getInstance().baseUrl
    fun agentId(): String = AigenSettings.getInstance().agentId

    fun get(path: String): JSONObject {
        return request("GET", path, null)
    }

    fun post(path: String, body: JSONObject): JSONObject {
        return request("POST", path, body)
    }

    private fun request(method: String, path: String, body: JSONObject?): JSONObject {
        val url = URL(baseUrl() + path)
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 10_000
            readTimeout = 15_000
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("User-Agent", "aigen-jetbrains/0.1")
            doOutput = body != null
        }

        if (body != null) {
            conn.outputStream.use { it.write(body.toString().toByteArray(StandardCharsets.UTF_8)) }
        }

        val rc = conn.responseCode
        val stream = if (rc in 200..299) conn.inputStream else conn.errorStream ?: conn.inputStream
        val raw = stream?.bufferedReader(StandardCharsets.UTF_8)?.use { it.readText() } ?: "{}"
        try {
            return JSONObject(raw)
        } catch (e: Exception) {
            LOG.warn("AIGEN $method $path → $rc, body=$raw", e)
            return JSONObject().put("error", "AIGEN $method $path → $rc")
        }
    }

    fun scanToken(address: String, chain: String = "base"): JSONObject {
        return get("/scan?address=$address&chain=$chain")
    }

    fun listMissions(limit: Int = 5): JSONObject {
        return get("/missions/active?limit=$limit")
    }

    fun createMission(title: String, description: String, rewardAmount: Int,
                      rewardCurrency: String = "AIGEN",
                      verificationType: String = "peer_vote",
                      category: String = "code"): JSONObject {
        val body = JSONObject()
            .put("creator_agent_id", agentId())
            .put("title", title)
            .put("description", description)
            .put("reward_amount", rewardAmount)
            .put("reward_currency", rewardCurrency)
            .put("verification_type", verificationType)
            .put("deadline_hours", 48)
            .put("category", category)

        var r = post("/missions/create", body)
        // Auto-faucet on insufficient
        val err = r.optString("error", "")
        if (err.contains("insufficient", true) && rewardCurrency == "AIGEN") {
            post("/join", JSONObject().put("agent_id", agentId()))
            r = post("/missions/create", body)
        }
        return r
    }
}
