import Foundation

/// Values come from an ignored BridgeSecrets.xcconfig file; no token lives in source.
struct BridgeConfiguration {
    let apiBaseURL: URL
    let bridgeToken: String
    let memberExternalID: String
    let installationID: String

    static func load(bundle: Bundle = .main) throws -> BridgeConfiguration {
        guard
            let apiBase = bundle.object(forInfoDictionaryKey: "HEALTHOPS_API_BASE_URL") as? String,
            let url = URL(string: apiBase),
            let token = bundle.object(forInfoDictionaryKey: "HEALTHOPS_BRIDGE_TOKEN") as? String,
            let member = bundle.object(forInfoDictionaryKey: "HEALTHOPS_MEMBER_EXTERNAL_ID") as? String,
            !apiBase.contains("$("), !token.contains("$("), !member.contains("$(")
        else { throw BridgeConfigurationError.missingLocalConfiguration }
        let key = "ExecutiveHealthBridge.installationID"
        let installationID = UserDefaults.standard.string(forKey: key) ?? UUID().uuidString
        UserDefaults.standard.set(installationID, forKey: key)
        return .init(apiBaseURL: url, bridgeToken: token, memberExternalID: member, installationID: installationID)
    }
}

enum BridgeConfigurationError: LocalizedError {
    case missingLocalConfiguration
    var errorDescription: String? { "尚未配置本机后端地址、桥接令牌或成员标识。请按使用说明创建 BridgeSecrets.xcconfig。" }
}
