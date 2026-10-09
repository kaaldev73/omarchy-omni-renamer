import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

Item {
  id: root
  property var shell: null
  property var manifest: null
  property bool opened: false
  property var paths: []
  property var rows: []
  property string errorText: ""
  property bool planSafe: false
  property int changedCount: 0
  property bool previewQueued: false
  property bool agentMode: false
  property var manualNames: []
  property string agentProvider: ""
  property var agentReasons: []
  property var presetNames: []
  property bool tooltipsEnabled: true
  property bool magicMode: false
  property string magicSequence: ""
  property string activeFeature: "name"
  property bool prefixBeforeDate: false
  property int sessionSerial: 0
  property string backendPath: (manifest && manifest.__sourceDir ? manifest.__sourceDir : "") + "/care_cli.py"

  function open(payloadJson) {
    sessionSerial += 1
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (e) { payload = ({}) }
    paths = payload.paths || []
    opened = true
    errorText = ""
    agentMode = false
    manualNames = []
    agentReasons = []
    magicMode = false
    listPresets()
    previewTimer.restart()
    Qt.callLater(function() { searchField.forceActiveFocus() })
  }

  function dismiss() {
    if (applyProc.running) return
    opened = false
    if (shell && typeof shell.hide === "function") shell.hide(manifest.id)
  }

  function payload() {
    var prefixes = []
    if (prefixBeforeDate && prefixField.text.trim()) prefixes.push(prefixField.text.trim())
    if (dateDay.checked) prefixes.push(Qt.formatDate(new Date(), "yyyyMMdd"))
    if (dateMonth.checked) prefixes.push(Qt.formatDate(new Date(), "yyyyMM"))
    if (dateYear.checked) prefixes.push(Qt.formatDate(new Date(), "yyyy"))
    if (!prefixBeforeDate && prefixField.text.trim()) prefixes.push(prefixField.text.trim())
    var suffixes = []
    if (suffixField.text.trim()) suffixes.push(suffixField.text.trim())
    return {
      paths: paths,
      names: manualNames,
      options: {
        case_style: styleBox.currentText,
        name: nameField.text,
        prefixes: prefixes,
        suffixes: suffixes,
        find: searchField.text,
        replace: replaceField.text,
        use_regex: regexCheck.checked,
        case_sensitive: caseCheck.checked,
        counter_start: counterCheck.checked ? counterStart.value : null,
        counter_step: counterStep.value,
        counter_padding: counterPadding.value,
        counter_position: counterPrefix.checked ? "prefix" : "suffix",
        trim_start: trimStart.value,
        trim_end: trimEnd.value,
        person: personField.text.trim(),
        person_position: personPrefix.checked ? "prefix" : "suffix"
      }
    }
  }

  function presetState() {
    return {
      case_style: styleBox.currentText, prefix: prefixField.text, suffix: suffixField.text,
      name: nameField.text,
      find: searchField.text, replace: replaceField.text, use_regex: regexCheck.checked,
      case_sensitive: caseCheck.checked, date_day: dateDay.checked,
      date_month: dateMonth.checked, date_year: dateYear.checked,
      counter_enabled: counterCheck.checked, counter_start: counterStart.value,
      counter_step: counterStep.value, counter_padding: counterPadding.value,
      counter_position: counterPrefix.checked ? "prefix" : "suffix",
      trim_start: trimStart.value, trim_end: trimEnd.value,
      person: personField.text, person_position: personPrefix.checked ? "prefix" : "suffix"
    }
  }
  function applyPreset(preset) {
    var styleIndex = styleBox.find(preset.case_style || "kebab-case")
    styleBox.currentIndex = styleIndex < 0 ? 0 : styleIndex
    nameField.text = preset.name || ""
    prefixField.text = preset.prefix || ""; suffixField.text = preset.suffix || ""
    searchField.text = preset.find || ""; replaceField.text = preset.replace || ""
    regexCheck.checked = preset.use_regex === true; caseCheck.checked = preset.case_sensitive === true
    dateDay.checked = preset.date_day === true; dateMonth.checked = preset.date_month === true; dateYear.checked = preset.date_year === true
    counterCheck.checked = preset.counter_enabled === true; counterStart.value = preset.counter_start === undefined ? 1 : preset.counter_start
    counterStep.value = preset.counter_step === undefined ? 1 : preset.counter_step
    counterPadding.value = preset.counter_padding === undefined ? 2 : preset.counter_padding
    counterPrefix.checked = preset.counter_position === "prefix"
    trimStart.value = preset.trim_start || 0; trimEnd.value = preset.trim_end || 0
    personField.text = preset.person || ""; personPrefix.checked = preset.person_position === "prefix"
    root.rulesChanged()
  }
  function listPresets() {
    if (presetProc.running) return
    presetProc.action = "list"
    presetProc.command = ["python", backendPath, "list-presets", "{}"]
    presetProc.running = true
  }
  function savePreset() {
    if (!presetName.text.trim() || presetProc.running) return
    presetProc.action = "save"
    presetProc.command = ["python", backendPath, "save-preset", JSON.stringify({name: presetName.text.trim(), preset: presetState()})]
    presetProc.running = true
  }
  function loadPreset() {
    if (!presetBox.currentText || presetProc.running) return
    presetProc.action = "load"
    presetProc.command = ["python", backendPath, "load-preset", JSON.stringify({name: presetBox.currentText})]
    presetProc.running = true
  }

  function refreshPreview() { previewQueued = true; previewTimer.restart() }
  function rulesChanged() { agentMode = false; manualNames = []; agentReasons = []; refreshPreview() }
  function runPreview() {
    if (!opened || paths.length === 0 || previewProc.running) return
    previewQueued = false
    previewProc.command = ["python", backendPath, agentMode ? "preview-manual" : "preview", JSON.stringify(payload())]
    previewProc.serial = sessionSerial
    previewProc.running = true
  }
  function applyRename() {
    if (!planSafe || changedCount < 1 || applyProc.running) return
    applyProc.command = ["python", backendPath, agentMode ? "apply-manual" : "apply", JSON.stringify(payload())]
    applyProc.serial = sessionSerial
    applyProc.running = true
  }
  function undoRename() {
    if (paths.length < 1 || undoProc.running) return
    undoProc.command = ["python", backendPath, "undo", JSON.stringify({paths: paths})]
    undoProc.serial = sessionSerial
    undoProc.running = true
  }
  function recommendNames() {
    if (paths.length < 1 || agentProc.running) return
    errorText = ""
    agentProc.command = ["python", backendPath, "recommend", JSON.stringify({paths: paths, allow_agent: agentCheck.checked, include_content: agentCheck.checked && contentCheck.checked})]
    agentProc.serial = sessionSerial
    agentProc.running = true
  }
  function editSuggestion(index, name) {
    var next = manualNames.length === rows.length ? manualNames.slice() : []
    if (next.length === 0)
      for (var i = 0; i < rows.length; i++) next.push(rows[i].renamed)
    next[index] = name
    manualNames = next
    agentMode = true
    refreshPreview()
  }

  function focusControl(control) {
    magicMode = false
    control.forceActiveFocus()
  }
  function activateFeature(feature) {
    activeFeature = feature
    if (feature === "name") focusControl(nameField)
    else if (feature === "prefix") focusControl(prefixField)
    else if (feature === "suffix") focusControl(suffixField)
    else if (feature === "replace") focusControl(searchField)
    else if (feature === "date") { dateDay.checked = !dateDay.checked; magicMode = false }
    else if (feature === "number") { counterCheck.checked = !counterCheck.checked; magicMode = false }
  }
  function magicKey(key) {
    magicSequence += key
    magicTimer.restart()
  }
  function runMagicSequence() {
    var command = magicSequence
    magicSequence = ""
    magicMode = false
    if (command === "S") return focusControl(styleBox)
    if (command === "2") return focusControl(nameField)
    if (command === "22") return recommendNames()
    if (command === "2c") return focusControl(searchField)
    if (command === "1") return activateFeature("prefix")
    if (command === "1x") { prefixField.text = ""; return }
    if (command === "3") return activateFeature("suffix")
    if (command === "4") return activateFeature("date")
    if (command === "4c2") { dateDay.checked = false; dateMonth.checked = !dateMonth.checked; return }
    if (command === "4c3") { dateDay.checked = false; dateYear.checked = !dateYear.checked; return }
    if (command === "5") return activateFeature("number")
    if (command === "5c112") return focusControl(counterStart)
    if (command === "31") { prefixBeforeDate = true; refreshPreview(); return }
    if (command === "13") { prefixBeforeDate = false; refreshPreview(); return }
  }
  function restoreOriginalNames() {
    var names = []
    for (var i = 0; i < rows.length; i++) names.push(rows[i].original)
    manualNames = names
    agentMode = true
    refreshPreview()
  }

  Timer { id: previewTimer; interval: 120; repeat: false; onTriggered: root.runPreview() }
  Timer { id: magicTimer; interval: 550; repeat: false; onTriggered: root.runMagicSequence() }
  Shortcut { sequence: "`"; onActivated: { root.magicMode = true; root.magicSequence = "" } }
  Shortcut { sequence: "S"; enabled: root.magicMode; onActivated: root.magicKey("S") }
  Shortcut { sequence: "1"; enabled: root.magicMode; onActivated: root.magicKey("1") }
  Shortcut { sequence: "2"; enabled: root.magicMode; onActivated: root.magicKey("2") }
  Shortcut { sequence: "3"; enabled: root.magicMode; onActivated: root.magicKey("3") }
  Shortcut { sequence: "4"; enabled: root.magicMode; onActivated: root.magicKey("4") }
  Shortcut { sequence: "5"; enabled: root.magicMode; onActivated: root.magicKey("5") }
  Shortcut { sequence: "C"; enabled: root.magicMode; onActivated: root.magicKey("c") }
  Shortcut { sequence: "X"; enabled: root.magicMode; onActivated: root.magicKey("x") }
  Shortcut { sequence: "U"; enabled: root.magicMode; onActivated: { root.magicMode = false; root.undoRename() } }
  Shortcut { sequence: "Return"; enabled: root.magicMode; onActivated: { root.magicMode = false; root.applyRename() } }
  Shortcut { sequence: "Escape"; enabled: root.magicMode; onActivated: { root.magicMode = false; root.restoreOriginalNames() } }
  Shortcut { sequence: "Escape"; enabled: root.magicMode; onActivated: root.magicMode = false }
  Process {
    id: presetProc
    property string action: ""
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var result = JSON.parse(text)
          if (!result.ok) { root.errorText = result.error; return }
          if (presetProc.action === "load") {
            root.applyPreset(result.preset)
            presetName.text = presetBox.currentText
          } else {
            root.presetNames = result.names || []
            if (presetProc.action === "save") presetBox.currentIndex = presetBox.find(presetName.text.trim())
          }
        } catch (e) { root.errorText = "Could not read preset data" }
      }
    }
  }
  Process {
    id: previewProc
    property int serial: -1
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (previewProc.serial !== root.sessionSerial) return
        try {
          var result = JSON.parse(text)
          root.errorText = result.ok ? "" : result.error
          root.rows = result.items || []
          root.planSafe = result.safe === true
          root.changedCount = result.changed || 0
        } catch (e) { root.errorText = "Could not read rename preview" }
      }
    }
    onRunningChanged: if (!running && root.opened && root.previewQueued) previewTimer.restart()
  }
  Process {
    id: agentProc
    property int serial: -1
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (agentProc.serial !== root.sessionSerial) return
        try {
          var result = JSON.parse(text)
          if (!result.ok) { root.errorText = result.error; return }
          var names = []
          var reasons = []
          for (var i = 0; i < result.recommendations.length; i++) {
            names.push(result.recommendations[i].suggested_name)
            reasons.push(result.recommendations[i].reason || "Contextual recommendation")
          }
          root.manualNames = names
          root.agentReasons = reasons
          root.agentProvider = result.provider
          root.agentMode = true
          root.refreshPreview()
        } catch (e) { root.errorText = "Agent recommendations were unreadable" }
      }
    }
  }
  Process {
    id: applyProc
    property int serial: -1
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (applyProc.serial !== root.sessionSerial) return
        try {
          var result = JSON.parse(text)
          if (!result.ok) root.errorText = result.error
          else { root.paths = result.paths; root.refreshPreview() }
        } catch (e) { root.errorText = "Rename result was unreadable" }
      }
    }
  }
  Process {
    id: undoProc
    property int serial: -1
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (undoProc.serial !== root.sessionSerial) return
        try {
          var result = JSON.parse(text)
          if (!result.ok) root.errorText = result.error
          else { root.paths = result.paths; root.refreshPreview() }
        } catch (e) { root.errorText = "Undo result was unreadable" }
      }
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omnirename"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle { anchors.fill: parent; color: Color.menu.scrim }
    MouseArea { anchors.fill: parent; onClicked: root.dismiss() }

    Rectangle {
      width: Math.min(1000, panel.width - Math.max(24, Style.gapsOut * 2))
      height: Math.min(780, panel.height - Math.max(24, Style.gapsOut * 2))
      anchors.centerIn: parent
      radius: Math.max(20, Style.cornerRadius)
      clip: true
      color: Color.menu.background
      border.color: Color.menu.border
      border.width: 1
      MouseArea { anchors.fill: parent; onClicked: {} }

      ColumnLayout {
        anchors.fill: parent
        anchors.margins: Style.spacing.panelPadding
        spacing: Style.space(8)

        RowLayout {
          Layout.fillWidth: true
          ColumnLayout {
            Label { text: "OmniRename"; color: Color.menu.text; font.pixelSize: Style.font.title; font.bold: true }
            Label { text: "F2 • Batch rename"; color: Color.menu.text; opacity: 0.62 }
            Label { text: root.magicMode ? "⌁ command mode: press a key" : "` = command mode"; color: root.magicMode ? "#5ee6a8" : Color.menu.text; opacity: 0.72 }
          }
          Item { Layout.fillWidth: true }
          Button {
            text: "ⓘ"
            flat: true
            Accessible.name: "Naming guide"
            onClicked: namingGuide.visible = !namingGuide.visible
            ToolTip.visible: root.tooltipsEnabled && hovered
            ToolTip.text: "Show recommended filename patterns by category"
          }
          Button {
            text: root.tooltipsEnabled ? "Tips: On" : "Tips: Off"
            flat: true
            onClicked: root.tooltipsEnabled = !root.tooltipsEnabled
            ToolTip.visible: root.tooltipsEnabled && hovered
            ToolTip.text: "Turn hover explanations on or off for every control"
          }
          Button { text: "×"; flat: true; onClicked: root.dismiss() }
        }

        RowLayout {
          Layout.alignment: Qt.AlignHCenter
          spacing: Style.space(8)
          Button { text: "Date"; onClicked: root.activateFeature("date"); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Add or remove a date token" }
          Button { text: "Prefix"; onClicked: root.activateFeature("prefix"); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Add or edit the prefix" }
          Button { text: "New Name"; highlighted: true; onClicked: root.activateFeature("name"); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Edit the new base name (always available)" }
          Button { text: "Suffix"; onClicked: root.activateFeature("suffix"); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Add or edit the suffix" }
          Button { text: "Number"; onClicked: root.activateFeature("number"); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Add or remove sequence numbering" }
        }

        GridLayout {
          Layout.fillWidth: true
          Layout.maximumWidth: 900
          Layout.alignment: Qt.AlignHCenter
          columns: 4
          columnSpacing: Style.space(6)
          rowSpacing: Style.space(5)
          Label {
            text: "Style"
            Layout.row: 0; Layout.column: 0
            color: Color.menu.text
            HoverHandler { id: styleHover }
            ToolTip.visible: root.tooltipsEnabled && styleHover.hovered
            ToolTip.text: "Choose how words are separated and capitalized in the new name"
          }
          ComboBox {
            id: styleBox
            Layout.row: 0; Layout.column: 1; Layout.columnSpan: 3
            model: ["kebab-case", "snake_case", "PascalCase", "camelCase", "UPPERCASE", "lowercase", "Title Case", "Sentence case"]
            onCurrentTextChanged: root.rulesChanged()
            ToolTip.visible: root.tooltipsEnabled && hovered
            ToolTip.text: "Choose how words are separated and capitalized in the new name"
          }
          Label { text: "Name"; color: Color.menu.text; Layout.row: 1; Layout.column: 0 }
          TextField { id: nameField; placeholderText: "Name to be written"; Layout.row: 1; Layout.column: 1; Layout.columnSpan: 3; onTextChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Write the new base name; the preview below updates immediately" }
          Label { text: "AI Suggestion"; color: Color.menu.text; Layout.row: 2; Layout.column: 0 }
          RowLayout { Layout.row: 2; Layout.column: 1; Layout.columnSpan: 3; Button { text: agentProc.running ? "Thinking…" : "Suggest names"; enabled: !agentProc.running; highlighted: true; onClicked: root.recommendNames(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Generate editable local or Codex-assisted name suggestions" } CheckBox { id: agentCheck; text: "Use Codex"; ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Explicitly allow Codex to receive names and metadata" } CheckBox { id: contentCheck; text: "Share text excerpts"; enabled: agentCheck.checked; ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Also send a short text excerpt" } }
          Label { text: "Replace"; color: Color.menu.text; Layout.row: 3; Layout.column: 0 }
          TextField { id: searchField; placeholderText: "Find"; Layout.row: 3; Layout.column: 1; onTextChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Text or pattern to find in each base name" }
          TextField { id: replaceField; placeholderText: "Replace with"; Layout.row: 3; Layout.column: 2; onTextChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Text that replaces the match" }
          RowLayout {
            Layout.row: 3; Layout.column: 3
            CheckBox { id: regexCheck; text: "Regex"; onCheckedChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Use a pattern for advanced find and replace, such as \\d+ for numbers" }
            CheckBox { id: caseCheck; text: "Aa"; onCheckedChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Match uppercase and lowercase letters exactly" }
          }
          TextField { id: prefixField; placeholderText: "Before"; Layout.row: 4; Layout.column: 0; onTextChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Text added before the date and new name" }
          Label { text: "Date"; color: Color.menu.text; Layout.row: 4; Layout.column: 1 }
          RowLayout {
            id: dateOptions
            Layout.row: 4; Layout.column: 2
            spacing: Style.space(10)
            CheckBox { id: dateDay; text: "YYYYMMDD"; onCheckedChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Add the full date, such as 20260905" }
            CheckBox { id: dateMonth; text: "YYYYMM"; onCheckedChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Add year and month, such as 202609" }
            CheckBox { id: dateYear; text: "YYYY"; onCheckedChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Add the four-digit year" }
            Item { Layout.fillWidth: true }
          }
          TextField { id: suffixField; placeholderText: "After"; Layout.row: 4; Layout.column: 3; onTextChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Text added after the date and new name" }
          Label { text: "Person"; color: Color.menu.text; ToolTip.visible: root.tooltipsEnabled && personHover.hovered; ToolTip.text: "Add a person's name to every selected filename"; HoverHandler { id: personHover } }
          TextField { id: personField; placeholderText: "e.g. Ada Lovelace"; onTextChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Useful for authors, clients, subjects, or owners" }
          RowLayout {
            RadioButton { id: personPrefix; text: "Before"; onCheckedChanged: root.rulesChanged() }
            RadioButton { text: "After"; checked: true; onCheckedChanged: root.rulesChanged() }
          }
          Item { Layout.fillWidth: true }
          CheckBox { id: counterCheck; text: "Number"; onCheckedChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Add a sequential number to each filename" }
          RowLayout { RadioButton { id: counterPrefix; text: "Before"; onCheckedChanged: root.rulesChanged() } RadioButton { text: "After"; checked: true; onCheckedChanged: root.rulesChanged() } }
          Label { text: "Sequence"; color: Color.menu.text }
          RowLayout { Label { text: "Start"; color: Color.menu.text } SpinBox { id: counterStart; from: -999999; to: 999999; value: 1; onValueChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "First number in the sequence" } }
          RowLayout {
            Label { text: "Step"; color: Color.menu.text }
            SpinBox { id: counterStep; from: 1; to: 999; value: 1; onValueChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Increase each following number by this amount. Example: step 5 gives 1, 6, 11." }
          }
          RowLayout { Label { text: "Digits"; color: Color.menu.text } SpinBox { id: counterPadding; from: 1; to: 12; value: 2; onValueChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Pad numbers with zeros, for example 001" } }
          Label { text: "Trim"; color: Color.menu.text }
          RowLayout { Label { text: "Left"; color: Color.menu.text } SpinBox { id: trimStart; from: 0; to: 999; onValueChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Remove this many characters from the beginning" } }
          RowLayout { Label { text: "Right"; color: Color.menu.text } SpinBox { id: trimEnd; from: 0; to: 999; onValueChanged: root.rulesChanged(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Remove this many characters from the end" } }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Color.menu.border }
        RowLayout { Layout.fillWidth: true; Layout.maximumWidth: 900; Layout.alignment: Qt.AlignHCenter; Label { text: "Old Name"; color: Color.menu.text; opacity: 0.72; font.pixelSize: 14; Layout.preferredWidth: 260 } Label { text: "New Name"; color: Color.menu.text; font.bold: true; font.pixelSize: Style.font.title; Layout.preferredWidth: 400 } Label { text: "Status"; color: Color.menu.text; font.bold: true; Layout.preferredWidth: Style.space(70) } }
        ListView {
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          model: root.rows
          spacing: 2
          delegate: Rectangle {
            objectName: "previewRow"
            required property var modelData
            required property int index
            width: ListView.view.width
            height: Math.max(44, Style.space(30))
            radius: Style.cornerRadius / 2
            color: index % 2 ? Qt.lighter(Color.menu.background, 1.16) : Qt.lighter(Color.menu.background, 1.09)
            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: Style.space(6)
              anchors.rightMargin: Style.space(6)
              spacing: Style.space(6)
              Rectangle {
                objectName: "originalName"
                color: Qt.lighter(Color.menu.background, 1.03)
                radius: Math.max(6, Style.cornerRadius / 2)
                Layout.preferredWidth: 260
                Layout.fillHeight: true
                Text {
                  anchors.fill: parent
                  anchors.leftMargin: Style.space(6)
                  anchors.rightMargin: Style.space(6)
                  text: modelData.original
                  color: Color.menu.text
                  font.pixelSize: Style.font.body
                  elide: Text.ElideMiddle
                  verticalAlignment: Text.AlignVCenter
                }
              }
              TextField {
                objectName: "renameInput"
                text: modelData.renamed
                color: modelData.safe ? Color.menu.text : "#ff6b6b"
                selectedTextColor: Color.menu.background
                selectionColor: Color.menu.text
                Layout.preferredWidth: 400
                Layout.fillHeight: true
                leftPadding: Style.space(6)
                rightPadding: Style.space(6)
                background: Rectangle {
                  radius: Math.max(6, Style.cornerRadius / 2)
                  color: Qt.lighter(Color.menu.background, 1.24)
                  border.color: parent.activeFocus ? Color.menu.text : Color.menu.border
                  border.width: parent.activeFocus ? 2 : 1
                }
                onEditingFinished: root.editSuggestion(index, text)
                ToolTip.visible: root.tooltipsEnabled && hovered && root.agentReasons[index]
                ToolTip.text: root.agentReasons[index] || "Edit this name directly"
              }
              Button { visible: root.agentMode; text: "Keep"; flat: true; onClicked: root.editSuggestion(index, modelData.original); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Keep this item's original name" }
              Text {
                objectName: "renameStatus"
                text: modelData.status
                color: modelData.status === "ready" ? "#5ee6a8" : (modelData.safe ? Color.menu.text : "#ff6b6b")
                font.pixelSize: Style.font.body
                font.bold: true
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
                Layout.preferredWidth: Style.space(70)
              }
            }
          }
        }
        Label { visible: root.errorText !== ""; text: root.errorText; color: "#ef4444"; wrapMode: Text.Wrap; Layout.fillWidth: true }
        RowLayout {
          Layout.fillWidth: true
          Label { text: root.planSafe ? (root.changedCount + " ready") : "Resolve conflicts"; color: root.planSafe ? "#34d399" : "#ef4444" }
          Label { text: "Presets"; color: Color.menu.text }
          ComboBox { id: presetBox; model: root.presetNames; Layout.preferredWidth: Style.space(110); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Choose a saved set of naming rules" }
          TextField { id: presetName; placeholderText: "Preset name"; Layout.preferredWidth: Style.space(130); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Give this reusable set of rules a name" }
          Button { text: "Save preset"; enabled: presetName.text.trim() !== "" && !presetProc.running; onClicked: root.savePreset(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Save the current naming rules for later" }
          Button { text: "Load"; enabled: presetBox.currentText !== "" && !presetProc.running; onClicked: root.loadPreset(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Restore all rules from this preset" }
          Item { Layout.fillWidth: true }
          Button { text: "Undo"; onClicked: root.undoRename(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Undo the last OmniRename operation for these items" }
          Button { text: "Cancel"; onClicked: root.dismiss(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Close without renaming" }
          Button { text: "Rename"; enabled: root.planSafe && root.changedCount > 0; highlighted: true; onClicked: root.applyRename(); ToolTip.visible: root.tooltipsEnabled && hovered; ToolTip.text: "Apply the safe previewed names" }
        }
      }

      Rectangle {
        id: namingGuide
        visible: false
        z: 20
        width: Math.min(430, parent.width - Style.space(20))
        anchors { top: parent.top; right: parent.right; bottom: parent.bottom }
        radius: Math.max(20, Style.cornerRadius)
        color: Qt.lighter(Color.menu.background, 1.08)
        border.color: Color.menu.border
        border.width: 1
        MouseArea { anchors.fill: parent; onClicked: {} }
        ColumnLayout {
          anchors.fill: parent
          anchors.margins: Style.spacing.panelPadding
          spacing: Style.space(8)
          RowLayout {
            Label { text: "Naming guide"; color: Color.menu.text; font.pixelSize: Style.font.title; font.bold: true }
            Item { Layout.fillWidth: true }
            Button { text: "×"; flat: true; onClicked: namingGuide.visible = false }
          }
          Label { text: "Use short, consistent words. Put the most sortable information first."; color: Color.menu.text; opacity: 0.7; wrapMode: Text.Wrap; Layout.fillWidth: true }
          Label { text: "Magic keys: ` then S Style • 2 Name • A AI • C Replace • 1/3/4 Dates • 5 Number • U Undo • Enter Rename • Esc cancel"; color: "#7dd3fc"; wrapMode: Text.Wrap; Layout.fillWidth: true }
          Repeater {
            model: [
              {category: "Documents", example: "20260905-project-topic-v01"},
              {category: "Invoices", example: "20260905-invoice-client-001"},
              {category: "Photos", example: "20260905-event-001"},
              {category: "Meetings", example: "20260905-team-topic-notes"},
              {category: "Deliverables", example: "client-project-final-v01"},
              {category: "People", example: "person-topic-20260905"}
            ]
            delegate: ColumnLayout {
              required property var modelData
              Layout.fillWidth: true
              Label { text: modelData.category; color: Color.menu.text; font.bold: true }
              Label { text: modelData.example; color: "#5ee6a8"; font.family: "monospace"; wrapMode: Text.Wrap; Layout.fillWidth: true }
            }
          }
          Item { Layout.fillHeight: true }
          Label { text: "Tip: avoid vague words like final-final. Use a date, version, or status instead."; color: Color.menu.text; opacity: 0.7; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
      }
    }

    Shortcut { sequence: "Escape"; enabled: !root.magicMode; onActivated: root.dismiss() }
  }
}
