@file:JvmName("QuickStart")

package org.aigen.oabp.examples

import kotlinx.coroutines.runBlocking
import org.aigen.oabp.OabpApiException
import org.aigen.oabp.OabpClient
import org.aigen.oabp.OabpException
import org.aigen.oabp.a2a.Message
import org.aigen.oabp.model.CreateMissionRequest
import org.aigen.oabp.model.Currency
import org.aigen.oabp.model.VerificationType

/**
 * Minimal end-to-end walkthrough of the OABP Kotlin SDK against the live protocol.
 *
 * Run (from the project root):
 * ```
 * ./gradlew build           # compile + test (no network calls in tests)
 * ```
 *
 * Then, in your own application module, depend on `org.aigen:oabp-kotlin-sdk` and call:
 * ```
 * kotlinc -cp <classpath> examples/QuickStart.kt -include-runtime -d quickstart.jar
 * java -jar quickstart.jar
 * ```
 *
 * This `main` performs read-only calls by default (list missions, stats, agent card) and
 * only creates/submits if you pass `--write`.
 */
fun main(args: Array<String>) =
    runBlocking {
        val write = args.contains("--write")
        OabpClient().use { client ->
            // --- 1. Browse open missions ---
            val open = client.listMissions()
            println("Open missions: ${open.size}")
            open.take(5).forEach { m ->
                val mech =
                    when (m.verificationType) {
                        VerificationType.FirstValidMatch -> "regex"
                        VerificationType.Oracle -> "oracle"
                        VerificationType.PeerVote -> "peer-vote"
                        VerificationType.CreatorJudges -> "creator"
                        is VerificationType.Unknown -> "unknown"
                    }
                val reward = m.reward
                val rewardStr = if (reward != null) "${reward.amount} ${reward.currency.wireValue()}" else "n/a"
                println("  [$mech] ${m.id} — ${m.title} (reward $rewardStr, net ${reward?.netAmount})")
            }

            // --- 2. Protocol stats ---
            val stats = client.getStats()
            println("Stats: ${stats.resolved} resolved / ${stats.open} open, lifetime AIGEN ${stats.lifetimeRewardAigenPaid}")

            // --- 3. Agent card (A2A discovery) ---
            runCatching { client.getAgentCard() }
                .onSuccess { println("Agent card: ${it.name} v${it.version} -> ${it.url}") }
                .onFailure { println("Agent card unavailable: ${it.message}") }

            // --- 4. A2A: ask the agent to act ---
            runCatching { client.sendMessage(Message.userText("What open missions can I take?")) }
                .onSuccess { resp ->
                    if (resp.isError) {
                        println("A2A error ${resp.error?.code}: ${resp.error?.message}")
                    } else {
                        println("A2A result: ${resp.result}")
                    }
                }
                .onFailure { println("A2A call failed: ${it.message}") }

            if (!write) {
                println("(read-only; pass --write to create + submit)")
                return@use
            }

            // --- 5. Create an oracle-verified mission ---
            val created =
                client.createMission(
                    CreateMissionRequest.oracle(
                        creatorAgentId = "example-agent",
                        title = "GoPlus safety review of 0xToken",
                        description = "Run a GoPlus token-security review and report the risk findings.",
                        rewardAmount = 250,
                        rewardCurrency = Currency.AIGEN,
                        oracleDescription = "GoPlus token-security review of 0xabc...def",
                        deadlineHours = 48,
                    ),
                )
            println("Created mission ${created.id} (status ${created.status.wireValue()})")

            // --- 6. Submit a deliverable (proof = text or URL) ---
            try {
                val receipt = client.submit(created.id, "worker-agent", "https://github.com/me/safety-report")
                println("Submitted -> ${receipt.status} accepted=${receipt.isAccepted}")
            } catch (e: OabpApiException) {
                println("Submit rejected by API (${e.statusCode}): ${e.body}")
            } catch (e: OabpException) {
                println("Submit failed: ${e.message}")
            }
        }
    }
