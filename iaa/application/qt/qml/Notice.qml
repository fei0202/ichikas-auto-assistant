/**
 * Toast 通知单例。
 *
 * 任何组件均可直接调用 `App.Notice.show(kind, text)` 弹出通知，
 * 无需通过父组件传递信号。实际渲染由 NoticeHost 负责；
 * 若 NoticeHost 尚未注册，消息会暂存到 pending 队列，
 * 注册后立即重放。
 *
 * 使用示例：
 *   App.Notice.show("success", "保存成功")
 *   App.Notice.show("error", "保存失败：" + reason)
 */
pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick

QtObject {
    id: root

    /** 当前已注册的 NoticeHost 实例，null 表示尚未注册 */
    property var host: null
    /** host 注册前暂存的通知队列 */
    property var pending: []

    /**
     * 注册 NoticeHost 实例。由 NoticeHost 在 Component.onCompleted 时调用。
     * 注册后立即重放 pending 队列。
     * @param {var} hostItem - NoticeHost 实例，传 null 表示注销
     */
    function registerHost(hostItem) {
        root.host = hostItem
        root.flushPending()
    }

    /**
     * 弹出一条 Toast 通知。
     * 若 NoticeHost 尚未注册，消息会进入 pending 队列，待注册后自动重放。
     * @param {string} kind - 通知类型：`"info"` | `"success"` | `"warning"` | `"error"`
     * @param {string} text - 通知正文
     */
    function show(kind, text) {
        var payload = { kind: kind, text: text }
        if (!root.host) {
            root.pending.push(payload)
            return
        }
        root.host.show(payload.kind, payload.text)
    }

    /** 将 pending 队列中的消息依次发送给已注册的 host */
    function flushPending() {
        if (!root.host || root.pending.length === 0) {
            return
        }
        var items = root.pending.slice(0)
        root.pending = []
        for (var i = 0; i < items.length; i++) {
            root.host.show(items[i].kind, items[i].text)
        }
    }
}
