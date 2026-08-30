import SwiftUI

struct ContentView: View {
    @StateObject private var sync = HealthSyncService()
    var body: some View {
        NavigationStack {
            Form {
                Section("Apple 健康") {
                    LabeledContent("状态", value: sync.isSyncing ? "同步中" : sync.status)
                    Button("连接 Apple 健康") { Task { await sync.authorize() } }
                    Button("立即同步") { Task { await sync.syncNow() } }
                        .disabled(!sync.ready || sync.isSyncing)
                    Text("授权可按数据类型单独选择。系统只显示已实际同步的数据类型，不声称已获得全部权限。").font(.footnote).foregroundStyle(.secondary)
                }
                Section("可同步的数据") {
                    ForEach(HealthKitTypes.descriptors) { item in
                        HStack { Text(item.label); Spacer(); Text(sync.synchronizedTypeKeys.contains(item.backendType) ? "已同步" : "等待数据").foregroundStyle(.secondary) }
                    }
                }
                Section("最近结果") {
                    Text(sync.lastResult)
                    Text("自动同步由 iOS 系统调度，不承诺实时。").font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("健康数据同步")
            .onOpenURL { _ in Task { await sync.authorize() } }
        }
    }
}
