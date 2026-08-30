import Foundation
import HealthKit

/// The only HealthKit types read by the first bridge version. This registry
/// mirrors the backend canonical mapping; it never infers risk or creates data.
struct HealthKitDescriptor: Identifiable {
    let key: String
    let label: String
    let sampleType: HKSampleType
    let backendType: String
    var id: String { key }
}

enum HealthKitTypes {
    static let descriptors: [HealthKitDescriptor] = [
        .init(key: "stepCount", label: "步数", sampleType: HKQuantityType(.stepCount), backendType: "stepCount"),
        .init(key: "activeEnergyBurned", label: "活动消耗", sampleType: HKQuantityType(.activeEnergyBurned), backendType: "activeEnergyBurned"),
        .init(key: "appleExerciseTime", label: "活动时长", sampleType: HKQuantityType(.appleExerciseTime), backendType: "appleExerciseTime"),
        .init(key: "heartRate", label: "心率", sampleType: HKQuantityType(.heartRate), backendType: "heartRate"),
        .init(key: "restingHeartRate", label: "静息心率", sampleType: HKQuantityType(.restingHeartRate), backendType: "restingHeartRate"),
        .init(key: "sleepAnalysis", label: "睡眠", sampleType: HKCategoryType(.sleepAnalysis), backendType: "sleepAnalysis"),
        .init(key: "oxygenSaturation", label: "血氧", sampleType: HKQuantityType(.oxygenSaturation), backendType: "oxygenSaturation"),
        .init(key: "bodyMass", label: "体重", sampleType: HKQuantityType(.bodyMass), backendType: "bodyMass"),
    ]

    static func readTypes() -> Set<HKObjectType> { Set(descriptors.map(\.sampleType)) }
}

struct HealthKitSamplePayload: Codable, Identifiable {
    let sampleID: String
    let type: String
    let value: CodableValue
    let unit: String?
    let startDate: Date
    let endDate: Date
    let source: SourcePayload
    let device: DevicePayload?
    var id: String { sampleID }
    enum CodingKeys: String, CodingKey {
        case sampleID = "sample_id", type, value, unit
        case startDate = "start_date", endDate = "end_date", source, device
    }
}

struct SourcePayload: Codable {
    let name: String
    let bundleIdentifier: String?
    enum CodingKeys: String, CodingKey { case name; case bundleIdentifier = "bundle_identifier" }
}

struct DevicePayload: Codable {
    let name: String?
    let manufacturer: String?
    let model: String?
    let hardwareVersion: String?
    let softwareVersion: String?
    enum CodingKeys: String, CodingKey {
        case name, manufacturer, model
        case hardwareVersion = "hardware_version"
        case softwareVersion = "software_version"
    }
}

/// HealthKit supplies numbers and sleep category values. Keep the JSON types
/// intact until the backend's existing unit-normalization layer receives them.
enum CodableValue: Codable {
    case number(Double)
    case text(String)
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let number = try? container.decode(Double.self) { self = .number(number); return }
        self = .text(try container.decode(String.self))
    }
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self { case .number(let value): try container.encode(value); case .text(let value): try container.encode(value) }
    }
}
