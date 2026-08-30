import Foundation
import HealthKit

/// Anchors remain on the iPhone and are committed only after API success.
final class AnchorStore {
    func load(_ key: String) -> HKQueryAnchor? {
        UserDefaults.standard.data(forKey: key).flatMap {
            try? NSKeyedUnarchiver.unarchivedObject(ofClass: HKQueryAnchor.self, from: $0)
        }
    }
    func save(_ anchor: HKQueryAnchor, key: String) {
        guard let data = try? NSKeyedArchiver.archivedData(withRootObject: anchor, requiringSecureCoding: true) else { return }
        UserDefaults.standard.set(data, forKey: key)
    }
    func remove(_ key: String) { UserDefaults.standard.removeObject(forKey: key) }
}
