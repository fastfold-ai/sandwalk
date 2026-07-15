import SwiftUI

extension ModalSandboxDetailView {
    @MainActor
    func load() async {
        busy = true
        error = nil
        defer { busy = false }
        do {
            var next = try await SandwalkAPIClient.getSandboxSettings()
            if next.computeType == "gpu" {
                if ModalSandboxPresets.gpuPresets.first(where: { $0.gpu == next.gpuClass }) == nil {
                    let preset = ModalSandboxPresets.defaultGpuPreset
                    next.gpuClass = preset.gpu
                    next.cpuCores = preset.cpu
                    next.ramGb = preset.ram
                }
            } else if ModalSandboxPresets.cpuPresets.first(where: {
                Int($0.cpu.rounded()) == Int(next.cpuCores.rounded())
                    && Int($0.ram.rounded()) == Int(next.ramGb.rounded())
            }) == nil {
                let preset = ModalSandboxPresets.defaultCpuPreset
                next.cpuCores = preset.cpu
                next.ramGb = preset.ram
            }
            saved = next
            draft = next
            loaded = true
        } catch {
            self.error = error.localizedDescription
            loaded = false
        }
    }

    @MainActor
    func apply() async {
        busy = true
        error = nil
        statusMessage = nil
        defer { busy = false }

        let selectedGpu: String
        let cores: Double
        let ram: Double
        if draft.computeType == "gpu" {
            let preset = selectedGpuPreset
            selectedGpu = preset.gpu
            cores = preset.cpu
            ram = preset.ram
        } else if let preset = ModalSandboxPresets.cpuPresets.first(where: { $0.id == matchedCpuPresetId }) {
            selectedGpu = draft.gpuClass.isEmpty ? ModalSandboxPresets.defaultGpuPreset.gpu : draft.gpuClass
            cores = preset.cpu
            ram = preset.ram
        } else {
            let preset = ModalSandboxPresets.defaultCpuPreset
            selectedGpu = draft.gpuClass.isEmpty ? ModalSandboxPresets.defaultGpuPreset.gpu : draft.gpuClass
            cores = preset.cpu
            ram = preset.ram
        }

        let body: [String: Any] = [
            "modalApp": draft.modalApp.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? "sandwalk" : draft.modalApp,
            "cpuImage": draft.cpuImage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? "python:3.12-slim" : draft.cpuImage,
            "gpuImage": draft.gpuImage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime" : draft.gpuImage,
            "pipPackages": draft.pipPackages,
            "computeType": draft.computeType == "gpu" ? "gpu" : "cpu",
            "gpuClass": selectedGpu,
            "cpuCores": cores,
            "ramGb": ram,
            "idleTtlSeconds": max(60, min(86400, draft.idleTtlSeconds)),
        ]

        do {
            let next = try await SandwalkAPIClient.updateSandboxSettings(body)
            saved = next
            draft = next
            statusMessage = "Saved. Modal chats use these compute and image settings."
        } catch {
            self.error = error.localizedDescription
        }
    }
}
