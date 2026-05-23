pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick

QtObject {
    id: root

    property var host: null
    property var pending: []

    function registerHost(hostItem) {
        root.host = hostItem
        root.flushPending()
    }

    function message(options, callback) {
        var payload = { options: options || {}, callback: callback }
        if (!root.host) {
            root.pending.push(payload)
            return
        }
        root.host.message(payload.options, payload.callback)
    }

    function flushPending() {
        if (!root.host || root.pending.length === 0) {
            return
        }
        var items = root.pending.slice(0)
        root.pending = []
        for (var i = 0; i < items.length; i++) {
            root.host.message(items[i].options, items[i].callback)
        }
    }
}
