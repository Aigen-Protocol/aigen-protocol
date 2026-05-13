package com.aigen

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBScrollPane
import org.json.JSONObject
import javax.swing.BoxLayout
import javax.swing.JButton
import javax.swing.JPanel
import javax.swing.SwingConstants
import java.awt.Desktop
import java.awt.Dimension
import java.net.URI
import javax.swing.BorderFactory

class AigenToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = JPanel()
        panel.layout = BoxLayout(panel, BoxLayout.Y_AXIS)
        panel.border = BorderFactory.createEmptyBorder(10, 10, 10, 10)

        val title = JBLabel("AIGEN — Open Bounty Protocol", SwingConstants.LEFT)
        title.font = title.font.deriveFont(java.awt.Font.BOLD, 14f)
        panel.add(title)
        panel.add(JBLabel("0.5% protocol fee · USDC/ETH/SOL/AIGEN payouts"))
        panel.add(javax.swing.Box.createVerticalStrut(10))

        val statusLabel = JBLabel("Loading stats…", SwingConstants.LEFT)
        panel.add(statusLabel)
        panel.add(javax.swing.Box.createVerticalStrut(8))

        val missionsPanel = JPanel()
        missionsPanel.layout = BoxLayout(missionsPanel, BoxLayout.Y_AXIS)
        panel.add(JBScrollPane(missionsPanel).apply {
            preferredSize = Dimension(280, 240)
        })

        panel.add(javax.swing.Box.createVerticalStrut(10))
        panel.add(JButton("Open AIGEN site").apply {
            addActionListener { openInBrowser(AigenClient.baseUrl()) }
        })
        panel.add(JButton("Browse all missions").apply {
            addActionListener { openInBrowser("${AigenClient.baseUrl()}/missions") }
        })
        panel.add(JButton("Post a mission").apply {
            addActionListener { openInBrowser("${AigenClient.baseUrl()}/missions/new") }
        })

        // Async load stats + missions
        ApplicationManager.getApplication().executeOnPooledThread {
            val stats = AigenClient.get("/missions/stats")
            val missions = AigenClient.listMissions(5)
            ApplicationManager.getApplication().invokeLater {
                statusLabel.text = "Open: ${stats.optInt("open", 0)} · Total ever: ${stats.optInt("total", 0)} · Resolved: ${stats.optInt("resolved", 0)}"

                missionsPanel.removeAll()
                val arr = missions.optJSONArray("missions")
                if (arr != null && arr.length() > 0) {
                    for (i in 0 until arr.length()) {
                        val m = arr.getJSONObject(i)
                        val mid = m.optString("id", "?").take(14)
                        val titleS = m.optString("title", "?").take(60)
                        val rew = m.optInt("reward_aigen", 0)
                        val link = JButton("<html><body style='width:240px'><b>$mid</b> — $rew AIGEN<br>$titleS</body></html>")
                        link.horizontalAlignment = SwingConstants.LEFT
                        link.addActionListener { openInBrowser("${AigenClient.baseUrl()}/m/${m.optString("id")}") }
                        missionsPanel.add(link)
                    }
                } else {
                    missionsPanel.add(JBLabel("No open missions"))
                }
                missionsPanel.revalidate()
                missionsPanel.repaint()
            }
        }

        toolWindow.contentManager.addContent(
            toolWindow.contentManager.factory.createContent(panel, "", false)
        )
    }

    private fun openInBrowser(url: String) {
        try {
            if (Desktop.isDesktopSupported() && Desktop.getDesktop().isSupported(Desktop.Action.BROWSE)) {
                Desktop.getDesktop().browse(URI(url))
            }
        } catch (_: Exception) {}
    }
}
