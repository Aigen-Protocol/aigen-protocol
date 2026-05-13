package com.aigen.actions

import com.aigen.AigenClient
import com.aigen.AigenSettings
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileTypes.PlainTextFileType
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.testFramework.LightVirtualFile
import com.intellij.ui.jcef.JBCefApp
import org.json.JSONObject
import java.awt.Desktop
import java.net.URI

private val ETH_ADDR = Regex("0x[a-fA-F0-9]{40}")

private fun openInBrowser(url: String) {
    try {
        if (Desktop.isDesktopSupported() && Desktop.getDesktop().isSupported(Desktop.Action.BROWSE)) {
            Desktop.getDesktop().browse(URI(url))
        }
    } catch (_: Exception) {}
}

private fun extractAddress(editor: Editor?): String? {
    if (editor == null) return null
    val sel = editor.selectionModel.selectedText?.trim()
    if (!sel.isNullOrBlank() && ETH_ADDR.matches(sel)) return sel

    val doc = editor.document
    val offset = editor.caretModel.offset
    val text = doc.text
    val start = (offset - 50).coerceAtLeast(0)
    val end = (offset + 50).coerceAtMost(text.length)
    val window = text.substring(start, end)
    return ETH_ADDR.findAll(window).firstOrNull()?.value
}

class ScanAtCursorAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = e.getData(CommonDataKeys.EDITOR)
        val addr = extractAddress(editor) ?: run {
            Messages.showErrorDialog(project, "No 0x... address found at cursor or in selection.", "AIGEN")
            return
        }
        runScan(project, addr)
    }
}

class ScanInputAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val addr = Messages.showInputDialog(project, "Token address (0x...)", "AIGEN scan", null) ?: return
        if (!ETH_ADDR.matches(addr)) {
            Messages.showErrorDialog(project, "Expected 0x-prefixed 40-char hex.", "AIGEN")
            return
        }
        runScan(project, addr)
    }
}

private fun runScan(project: Project, address: String) {
    object : Task.Backgroundable(project, "AIGEN scanning $address ...", false) {
        override fun run(indicator: ProgressIndicator) {
            val r = AigenClient.scanToken(address, "base")
            ApplicationManager.getApplication().invokeLater {
                showScanResult(project, address, r)
            }
        }
    }.queue()
}

private fun showScanResult(project: Project, address: String, r: JSONObject) {
    val score = r.optInt("safety_score", 0)
    val verdict = r.optString("verdict", "?")
    val token = r.optJSONObject("token") ?: JSONObject()
    val name = token.optString("name", "Unknown")
    val symbol = token.optString("symbol", "?")
    val flags = r.optJSONArray("flags")
    val flagLines = StringBuilder()
    if (flags != null) {
        for (i in 0 until minOf(flags.length(), 8)) {
            val f = flags.opt(i)
            val label = when (f) {
                is JSONObject -> f.optString("name", "?")
                else -> f.toString()
            }
            flagLines.append("- ").append(label).append("\n")
        }
    }
    val md = """
        # AIGEN Scan

        **${symbol}** (${name}) on BASE

        `${address}`

        ## Safety: ${score}/100 — ${verdict}

        ## Flags
        ${if (flagLines.isEmpty()) "_None_" else flagLines.toString()}

        [Full page →](${AigenClient.baseUrl()}/t/${address}?chain=base)
    """.trimIndent()

    val vf = LightVirtualFile("aigen-scan-${address.takeLast(6)}.md", PlainTextFileType.INSTANCE, md)
    FileEditorManager.getInstance(project).openFile(vf, true)
}

class CreateMissionAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = e.getData(CommonDataKeys.EDITOR)
        val sel = editor?.selectionModel?.selectedText ?: ""
        if (sel.isBlank()) {
            Messages.showErrorDialog(project, "Select some code first.", "AIGEN")
            return
        }
        val title = Messages.showInputDialog(project, "Mission title", "AIGEN: Create mission",
            null, "Audit this function", null) ?: return
        val rewardStr = Messages.showInputDialog(project, "Reward (whole AIGEN)", "AIGEN: Create mission",
            null, "50", null) ?: return
        val reward = rewardStr.toIntOrNull() ?: run {
            Messages.showErrorDialog(project, "Invalid reward amount.", "AIGEN"); return
        }

        val description = """
            Code review request:

            ```
            ${sel.take(1500)}
            ```
        """.trimIndent()

        object : Task.Backgroundable(project, "AIGEN creating mission ...", false) {
            override fun run(indicator: ProgressIndicator) {
                val r = AigenClient.createMission(title, description, reward, "AIGEN", "peer_vote", "audit")
                ApplicationManager.getApplication().invokeLater {
                    val mid = r.optString("id", "")
                    if (mid.isNotEmpty()) {
                        val url = "${AigenClient.baseUrl()}/m/$mid"
                        val choice = Messages.showYesNoDialog(project,
                            "Mission created: $mid\n\nOpen in browser?",
                            "AIGEN", null)
                        if (choice == Messages.YES) openInBrowser(url)
                    } else {
                        Messages.showErrorDialog(project, "Failed: ${r.optString("error", "unknown")}", "AIGEN")
                    }
                }
            }
        }.queue()
    }
}

class BrowseMissionsAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        openInBrowser("${AigenClient.baseUrl()}/missions")
    }
}

class OpenWebAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        openInBrowser(AigenClient.baseUrl())
    }
}
