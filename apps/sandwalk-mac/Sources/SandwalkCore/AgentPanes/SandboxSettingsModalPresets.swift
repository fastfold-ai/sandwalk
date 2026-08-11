import SwiftUI

/// Matches `apps/local-web/src/lib/sandbox-presets.ts`.
enum ModalSandboxPresets {
    struct CpuPreset: Identifiable {
        let id: String
        let cpu: Double
        let ram: Double
        let label: String
    }

    struct GpuPreset: Identifiable {
        var id: String { gpu }
        let gpu: String
        let vram: Int
        let cpu: Double
        let ram: Double
        let label: String
    }

    static let cpuPresets: [CpuPreset] = [
        .init(id: "2c8g", cpu: 2, ram: 8, label: "2 CPU cores · 8 GB RAM"),
        .init(id: "4c16g", cpu: 4, ram: 16, label: "4 CPU cores · 16 GB RAM"),
        .init(id: "8c32g", cpu: 8, ram: 32, label: "8 CPU cores · 32 GB RAM"),
        .init(id: "16c64g", cpu: 16, ram: 64, label: "16 CPU cores · 64 GB RAM"),
    ]

    static let gpuPresets: [GpuPreset] = [
        .init(gpu: "T4", vram: 16, cpu: 8, ram: 32, label: "T4 · 16 GB VRAM · 8 CPU · 32 GB RAM"),
        .init(gpu: "L4", vram: 24, cpu: 8, ram: 32, label: "L4 · 24 GB VRAM · 8 CPU · 32 GB RAM"),
        .init(gpu: "A10", vram: 24, cpu: 8, ram: 32, label: "A10 · 24 GB VRAM · 8 CPU · 32 GB RAM"),
        .init(gpu: "L40S", vram: 48, cpu: 16, ram: 64, label: "L40S · 48 GB VRAM · 16 CPU · 64 GB RAM"),
        .init(gpu: "A100", vram: 80, cpu: 16, ram: 64, label: "A100 · 80 GB VRAM · 16 CPU · 64 GB RAM"),
        .init(gpu: "RTX-PRO-6000", vram: 48, cpu: 16, ram: 64, label: "RTX-PRO-6000 · 48 GB VRAM · 16 CPU · 64 GB RAM"),
        .init(gpu: "H100", vram: 80, cpu: 16, ram: 64, label: "H100 · 80 GB VRAM · 16 CPU · 64 GB RAM"),
        .init(gpu: "H200", vram: 141, cpu: 16, ram: 64, label: "H200 · 141 GB VRAM · 16 CPU · 64 GB RAM"),
    ]

    static let defaultCpuPreset = cpuPresets[0]
    static let defaultGpuPreset = gpuPresets[0]
}
