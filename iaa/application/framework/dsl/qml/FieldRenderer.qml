pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "./controls"

Item {
    id: root

    required property string fieldId
    required property var initialField
    required property var formController

    // 工作副本：初始化时从 initialField 同步，后续由 fieldUpdated 信号更新。
    // 不使用绑定，避免因 runtimeChanged 全量刷新时被重置而打断用户输入。
    property var field: root.initialField

    onInitialFieldChanged: root.field = root.initialField

    Connections {
        target: root.formController
        function onFieldUpdated(id, fieldJson) {
            if (id === root.fieldId) {
                root.field = JSON.parse(fieldJson)
            }
        }
    }

    implicitWidth: loader.implicitWidth
    implicitHeight: loader.implicitHeight

    Loader {
        id: loader
        anchors.left: parent.left
        anchors.right: parent.right

        sourceComponent: {
            switch (root.field.kind) {
            case "text": return textFieldComponent
            case "select": return selectFieldComponent
            case "segmented": return segmentedFieldComponent
            case "checkbox": return checkboxFieldComponent
            case "mumu_picker": return mumuPickerComponent
            case "transfer_list": return transferListComponent
            default: return unsupportedComponent
            }
        }
    }

    Component {
        id: textFieldComponent
        DslTextField {
            field: root.field
            formController: root.formController
        }
    }

    Component {
        id: selectFieldComponent
        DslSelectField {
            field: root.field
            formController: root.formController
        }
    }

    Component {
        id: segmentedFieldComponent
        DslSegmentedField {
            field: root.field
            formController: root.formController
        }
    }

    Component {
        id: checkboxFieldComponent
        DslCheckboxField {
            field: root.field
            formController: root.formController
        }
    }

    Component {
        id: mumuPickerComponent
        DslMumuPicker {
            field: root.field
            formController: root.formController
        }
    }

    Component {
        id: transferListComponent
        DslTransferList {
            field: root.field
            formController: root.formController
        }
    }

    Component {
        id: unsupportedComponent
        Label {
            color: "#DC3545"
            text: "不支持的字段类型: " + (root.field.kind || "")
        }
    }
}
