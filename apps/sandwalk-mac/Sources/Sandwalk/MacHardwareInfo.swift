import Darwin
import Foundation
import IOKit

/// Native macOS chip / GPU metrics (sysctl + IOKit) — independent of `/v1/status`.
enum MacHardwareInfo {
    struct Snapshot: Equatable {
        var chipName: String?
        var gpuCores: Int?
        var gpuUtilizationPercent: Double?

        var systemSubtitle: String {
            let os = ProcessInfo.processInfo.operatingSystemVersion
            let version = "\(os.majorVersion).\(os.minorVersion)"
                + (os.patchVersion > 0 ? ".\(os.patchVersion)" : "")
            #if arch(arm64)
            return "Apple Silicon · macOS \(version)"
            #else
            return "Intel · macOS \(version)"
            #endif
        }
    }

    static func current() -> Snapshot {
        var snap = Snapshot(chipName: sysctlString("machdep.cpu.brand_string"))
        fillGPU(into: &snap)
        return snap
    }

    private static func sysctlString(_ name: String) -> String? {
        var size: size_t = 0
        guard sysctlbyname(name, nil, &size, nil, 0) == 0, size > 1 else { return nil }
        var buf = [CChar](repeating: 0, count: Int(size))
        guard sysctlbyname(name, &buf, &size, nil, 0) == 0 else { return nil }
        let value = String(cString: buf).trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }

    private static func fillGPU(into snap: inout Snapshot) {
        guard let matching = IOServiceMatching("IOAccelerator") else { return }
        var iterator: io_iterator_t = 0
        let kr = IOServiceGetMatchingServices(kIOMainPortDefault, matching, &iterator)
        guard kr == KERN_SUCCESS else { return }
        defer { IOObjectRelease(iterator) }

        var service = IOIteratorNext(iterator)
        while service != 0 {
            defer {
                IOObjectRelease(service)
                service = IOIteratorNext(iterator)
            }
            var propsRef: Unmanaged<CFMutableDictionary>?
            let pkr = IORegistryEntryCreateCFProperties(service, &propsRef, kCFAllocatorDefault, 0)
            guard pkr == KERN_SUCCESS,
                  let dict = propsRef?.takeRetainedValue() as? [String: Any]
            else { continue }

            if snap.gpuCores == nil {
                if let cores = dict["gpu-core-count"] as? Int, cores > 0 {
                    snap.gpuCores = cores
                } else if let cores = dict["gpu-core-count"] as? NSNumber, cores.intValue > 0 {
                    snap.gpuCores = cores.intValue
                }
            }

            guard let perf = dict["PerformanceStatistics"] as? [String: Any] else { continue }

            if snap.gpuUtilizationPercent == nil {
                if let util = perf["Device Utilization %"] as? Double {
                    snap.gpuUtilizationPercent = max(0, min(100, util))
                } else if let util = perf["Device Utilization %"] as? Int {
                    snap.gpuUtilizationPercent = Double(max(0, min(100, util)))
                } else if let util = perf["Device Utilization %"] as? NSNumber {
                    snap.gpuUtilizationPercent = max(0, min(100, util.doubleValue))
                }
            }

            // First accelerator with useful stats is enough.
            if snap.gpuCores != nil || snap.gpuUtilizationPercent != nil {
                break
            }
        }
    }
}
