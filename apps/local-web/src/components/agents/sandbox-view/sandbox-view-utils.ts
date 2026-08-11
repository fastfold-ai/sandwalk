import type { SandboxSettings } from '@sandwalk/agent-ui-core'

export type ImageDraft = {
  modalApp: string
  idleTtlSeconds: string
  cpuImage: string
  gpuImage: string
  pipPackages: string
}

export const DEFAULT_CPU_IMAGE = 'python:3.12-slim'
export const DEFAULT_GPU_IMAGE = 'pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime'
export const DEFAULT_PIP =
  'pandas, numpy, scipy, scikit-learn, matplotlib, seaborn'
export const DEFAULT_MODAL_APP = 'sandwalk'
export const DEFAULT_IDLE_TTL = '600'

export function settingsToImageDraft(settings: SandboxSettings | null): ImageDraft {
  return {
    modalApp: settings?.modalApp ?? DEFAULT_MODAL_APP,
    idleTtlSeconds: String(settings?.idleTtlSeconds ?? DEFAULT_IDLE_TTL),
    cpuImage: settings?.cpuImage?.trim() || DEFAULT_CPU_IMAGE,
    gpuImage: settings?.gpuImage?.trim() || DEFAULT_GPU_IMAGE,
    pipPackages: settings?.pipPackages ?? DEFAULT_PIP
  }
}

export function defaultImageDraft(): ImageDraft {
  return {
    modalApp: DEFAULT_MODAL_APP,
    idleTtlSeconds: DEFAULT_IDLE_TTL,
    cpuImage: DEFAULT_CPU_IMAGE,
    gpuImage: DEFAULT_GPU_IMAGE,
    pipPackages: DEFAULT_PIP
  }
}

export function clampNumber(
  value: string,
  minimum: number,
  maximum: number,
  fallback: number
) {
  const n = Number(value)
  if (!Number.isFinite(n)) return fallback
  return Math.max(minimum, Math.min(maximum, n))
}
