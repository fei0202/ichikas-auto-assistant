pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

ColumnLayout {
    id: root

    required property var field
    required property var formController

    spacing: 4

    // 当 field 从外部更新（如 discard、switchProfile）时，若输入框未聚焦则同步文本。
    onFieldChanged: {
        if (!tf.activeFocus) {
            tf.text = String(root.field.value ?? "")
        }
    }

    FormField {
        Layout.fillWidth: true
        labelText: root.field.label
        helpText: root.field.helpText || ""
        errorText: root.field.error || ""
        TextField {
            id: tf
            Layout.fillWidth: true
            enabled: !!root.field.enabled
            placeholderText: root.field.props && root.field.props.placeholder ? root.field.props.placeholder : ""
            Component.onCompleted: tf.text = String(root.field.value ?? "")
            onEditingFinished: root.formController.setValue(root.field.id, tf.text)
        }
    }

}
