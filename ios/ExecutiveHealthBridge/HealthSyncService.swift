import Foundation

struct AppleHealthSyncRequest: Codable {
    let externalMemberID: String
    let deviceInstallationID: String
    let syncID: String
    let syncStartedAt: Date
    let samples: [HealthKitSamplePayload]
    let deletedSampleIDs: [String]
    enum CodingKeys: String, CodingKey {
        case externalMemberID = "external_member_id"
        case deviceInstallationID = "device_installation_id"
        case syncID = "sync_id"
        case syncStartedAt = "sync_started_at"
        case samples
        case deletedSampleIDs = "deleted_sample_ids"
    }
}

@MainActor
final class HealthSyncService: ObservableObject {
    @Published var status = "未连接"
    @Published var lastResult = "尚未同步"
    @Published var synchronizedTypeKeys: Set<String> = []
    @Published var isSyncing = false
    private let health = HealthKitManager()

    var ready: Bool { status == "Apple 健康授权已完成" || isSyncing }

    func authorize() async {
        do {
            try await health.authorize()
            status = "Apple 健康授权已完成"
            health.enableAutomaticUpdates { [weak self] completion in
                Task {
                    await self?.syncNow(automatic: true)
                    completion()
                }
            }
            await syncNow(automatic: false)
        } catch {
            status = "授权未完成"
            lastResult = error.localizedDescription
        }
    }

    func syncNow(automatic: Bool = false) async {
        guard !isSyncing else { return }
        isSyncing = true
        defer { isSyncing = false }
        do {
            let configuration = try BridgeConfiguration.load()
            let delta = try await health.collectIncremental()
            if delta.samples.isEmpty && delta.deletedSampleIDs.isEmpty {
                health.commit(delta)
                lastResult = "没有新的 Apple 健康数据。"
                return
            }
            let payload = AppleHealthSyncRequest(
                externalMemberID: configuration.memberExternalID,
                deviceInstallationID: configuration.installationID,
                syncID: UUID().uuidString,
                syncStartedAt: Date(),
                samples: delta.samples,
                deletedSampleIDs: delta.deletedSampleIDs
            )
            try await post(payload, configuration: configuration)
            health.commit(delta)
            synchronizedTypeKeys.formUnion(Set(delta.samples.map(\.type)))
            lastResult = automatic ? "已完成一次自动同步。后台同步由 iOS 系统调度。" : "同步完成：新增或更新 \(delta.samples.count) 条数据。"
        } catch {
            lastResult = "同步未完成：\(error.localizedDescription)"
        }
    }

    private func post(_ payload: AppleHealthSyncRequest, configuration: BridgeConfiguration) async throws {
        let endpoint = configuration.apiBaseURL.appendingPathComponent("integrations/apple-health/sync")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(configuration.bridgeToken)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder.healthOps.encode(payload)
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else { throw HealthSyncError.serverRejected }
    }
}

private extension JSONEncoder {
    static let healthOps: JSONEncoder = { let encoder = JSONEncoder(); encoder.dateEncodingStrategy = .iso8601; return encoder }()
}

enum HealthSyncError: LocalizedError {
    case serverRejected
    var errorDescription: String? { "平台未接受本次同步。请检查后端地址、HTTPS 和桥接令牌。" }
}
