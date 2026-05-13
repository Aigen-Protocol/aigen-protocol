package com.aigen

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.openapi.options.Configurable
import com.intellij.openapi.ui.LabeledComponent
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBTextField
import com.intellij.util.xmlb.XmlSerializerUtil
import javax.swing.BoxLayout
import javax.swing.JComponent
import javax.swing.JPanel

/** Persisted plugin settings (stored at ~/.config/JetBrains/<IDE>/options/aigen.xml). */
@State(name = "AigenSettings", storages = [Storage("aigen.xml")])
@Service(Service.Level.APP)
class AigenSettings : PersistentStateComponent<AigenSettings.State> {
    data class State(
        var baseUrl: String = "https://cryptogenesis.duckdns.org",
        var agentId: String = "jetbrains-user",
        var autoScan: Boolean = true,
    )

    private var state = State()

    override fun getState(): State = state
    override fun loadState(s: State) { XmlSerializerUtil.copyBean(s, state) }

    var baseUrl: String
        get() = state.baseUrl
        set(v) { state.baseUrl = v }

    var agentId: String
        get() = state.agentId
        set(v) { state.agentId = v }

    var autoScan: Boolean
        get() = state.autoScan
        set(v) { state.autoScan = v }

    companion object {
        fun getInstance(): AigenSettings =
            ApplicationManager.getApplication().getService(AigenSettings::class.java)
    }
}

/** Settings UI under Tools → AIGEN. */
class AigenSettingsConfigurable : Configurable {
    private val baseUrlField = JBTextField()
    private val agentIdField = JBTextField()
    private val autoScanCheck = JBCheckBox("Auto-show safety hover for 0x... addresses")

    override fun getDisplayName(): String = "AIGEN"

    override fun createComponent(): JComponent {
        val panel = JPanel()
        panel.layout = BoxLayout(panel, BoxLayout.Y_AXIS)
        panel.add(LabeledComponent.create(baseUrlField, "Base URL"))
        panel.add(LabeledComponent.create(agentIdField, "Agent ID"))
        panel.add(autoScanCheck)
        reset()
        return panel
    }

    override fun isModified(): Boolean {
        val s = AigenSettings.getInstance()
        return baseUrlField.text != s.baseUrl ||
                agentIdField.text != s.agentId ||
                autoScanCheck.isSelected != s.autoScan
    }

    override fun apply() {
        val s = AigenSettings.getInstance()
        s.baseUrl = baseUrlField.text.trim()
        s.agentId = agentIdField.text.trim()
        s.autoScan = autoScanCheck.isSelected
    }

    override fun reset() {
        val s = AigenSettings.getInstance()
        baseUrlField.text = s.baseUrl
        agentIdField.text = s.agentId
        autoScanCheck.isSelected = s.autoScan
    }
}
