import Foundation
import HealthKit

struct HealthKitDelta {
    let samples: [HealthKitSamplePayload]
    let deletedSampleIDs: [String]
    let anchors: [String: HKQueryAnchor]
}

/// Reads precisely the HealthKit types that the member authorized. Apple does
/// not expose granular read-permission results, so UI reports actual sync only.
final class HealthKitManager {
    let store = HKHealthStore()
    private let anchors = AnchorStore()
    private var observerQueries: [HKObserverQuery] = []

    func authorize() async throws {
        guard HKHealthStore.isHealthDataAvailable() else { throw HealthKitBridgeError.unavailable }
        try await store.requestAuthorization(toShare: [], read: HealthKitTypes.readTypes())
    }

    func collectIncremental() async throws -> HealthKitDelta {
        var samples: [HealthKitSamplePayload] = []
        var deleted: [String] = []
        var nextAnchors: [String: HKQueryAnchor] = [:]
        for descriptor in HealthKitTypes.descriptors {
            let result = try await anchoredSamples(for: descriptor)
            samples.append(contentsOf: result.samples)
            deleted.append(contentsOf: result.deletedSampleIDs)
            if let anchor = result.anchor { nextAnchors[descriptor.key] = anchor }
        }
        return .init(samples: samples, deletedSampleIDs: Array(Set(deleted)), anchors: nextAnchors)
    }

    func commit(_ delta: HealthKitDelta) {
        for (key, anchor) in delta.anchors { anchors.save(anchor, key: anchorKey(for: key)) }
    }

    /// iOS schedules observer/background delivery. Automatic is not real-time.
    func enableAutomaticUpdates(onChange: @escaping (@escaping () -> Void) -> Void) {
        guard observerQueries.isEmpty else { return }
        for descriptor in HealthKitTypes.descriptors {
            let query = HKObserverQuery(sampleType: descriptor.sampleType, predicate: nil) { [weak self] _, completion, error in
                guard error == nil, self != nil else { completion(); return }
                // HealthKit's completion handler is released only after the
                // incremental upload has finished or failed.
                onChange(completion)
            }
            observerQueries.append(query)
            store.execute(query)
            store.enableBackgroundDelivery(for: descriptor.sampleType, frequency: .immediate) { _, _ in }
        }
    }

    private func anchoredSamples(for descriptor: HealthKitDescriptor) async throws -> (samples: [HealthKitSamplePayload], deletedSampleIDs: [String], anchor: HKQueryAnchor?) {
        try await withCheckedThrowingContinuation { continuation in
            let query = HKAnchoredObjectQuery(type: descriptor.sampleType, predicate: nil, anchor: anchors.load(anchorKey(for: descriptor.key)), limit: HKObjectQueryNoLimit) { [weak self] _, added, deleted, newAnchor, error in
                if let error { continuation.resume(throwing: error); return }
                let payloads = (added ?? []).compactMap { self?.payload(for: $0, descriptor: descriptor) }
                continuation.resume(returning: (payloads, (deleted ?? []).map { $0.uuid.uuidString }, newAnchor))
            }
            store.execute(query)
        }
    }

    private func payload(for sample: HKSample, descriptor: HealthKitDescriptor) -> HealthKitSamplePayload? {
        let valueAndUnit: (CodableValue, String?)
        if let quantity = sample as? HKQuantitySample {
            switch descriptor.key {
            case "stepCount": valueAndUnit = (.number(quantity.quantity.doubleValue(for: .count())), "count")
            case "activeEnergyBurned": valueAndUnit = (.number(quantity.quantity.doubleValue(for: .kilocalorie())), "kcal")
            case "appleExerciseTime": valueAndUnit = (.number(quantity.quantity.doubleValue(for: .minute())), "minutes")
            case "heartRate", "restingHeartRate": valueAndUnit = (.number(quantity.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))), "bpm")
            case "oxygenSaturation": valueAndUnit = (.number(quantity.quantity.doubleValue(for: .percent())), "percent")
            case "bodyMass": valueAndUnit = (.number(quantity.quantity.doubleValue(for: .gramUnit(with: .kilo))), "kg")
            default: return nil
            }
        } else if let category = sample as? HKCategorySample, descriptor.key == "sleepAnalysis" {
            guard let stage = sleepStage(category) else { return nil }
            valueAndUnit = (.text(stage), nil)
        } else { return nil }
        let device = sample.device.map { DevicePayload(name: $0.name, manufacturer: $0.manufacturer, model: $0.model, hardwareVersion: $0.hardwareVersion, softwareVersion: $0.softwareVersion) }
        return .init(sampleID: sample.uuid.uuidString, type: descriptor.backendType, value: valueAndUnit.0, unit: valueAndUnit.1, startDate: sample.startDate, endDate: sample.endDate, source: .init(name: sample.sourceRevision.source.name, bundleIdentifier: sample.sourceRevision.source.bundleIdentifier), device: device)
    }

    private func sleepStage(_ sample: HKCategorySample) -> String? {
        if #available(iOS 16.0, *) {
            switch HKCategoryValueSleepAnalysis(rawValue: sample.value) {
            case .inBed: return "inBed"
            case .awake: return "awake"
            case .asleep: return "asleep"
            case .asleepCore: return "asleepCore"
            case .asleepDeep: return "asleepDeep"
            case .asleepREM: return "asleepREM"
            case .asleepUnspecified: return "asleepUnspecified"
            default: return nil
            }
        }
        switch sample.value {
        case HKCategoryValueSleepAnalysis.inBed.rawValue: return "inBed"
        case HKCategoryValueSleepAnalysis.asleep.rawValue: return "asleep"
        default: return nil
        }
    }
    private func anchorKey(for type: String) -> String { "ExecutiveHealthBridge.anchor.\(type)" }
}

enum HealthKitBridgeError: LocalizedError {
    case unavailable
    var errorDescription: String? { "这台设备不支持 Apple 健康数据。" }
}
