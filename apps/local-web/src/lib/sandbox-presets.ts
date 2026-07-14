/** Shared Modal compute presets (aligned with Cloud Thread Sandbox). */

export type CpuPreset = {
  id: string
  cpu: number
  ram: number
  label: string
  shortLabel: string
}

export type GpuPreset = {
  gpu: string
  vram: number
  cpu: number
  ram: number
  label: string
  shortLabel: string
}

export const CPU_PRESETS: CpuPreset[] = [
  {
    id: '2c8g',
    cpu: 2,
    ram: 8,
    label: '2 CPU cores · 8 GB RAM',
    shortLabel: '2 CPU · 8 GB'
  },
  {
    id: '4c16g',
    cpu: 4,
    ram: 16,
    label: '4 CPU cores · 16 GB RAM',
    shortLabel: '4 CPU · 16 GB'
  },
  {
    id: '8c32g',
    cpu: 8,
    ram: 32,
    label: '8 CPU cores · 32 GB RAM',
    shortLabel: '8 CPU · 32 GB'
  },
  {
    id: '16c64g',
    cpu: 16,
    ram: 64,
    label: '16 CPU cores · 64 GB RAM',
    shortLabel: '16 CPU · 64 GB'
  }
]

export const GPU_PRESETS: GpuPreset[] = [
  {
    gpu: 'T4',
    vram: 16,
    cpu: 8,
    ram: 32,
    label: 'T4 · 16 GB VRAM · 8 CPU · 32 GB RAM',
    shortLabel: 'T4 · 16GB'
  },
  {
    gpu: 'L4',
    vram: 24,
    cpu: 8,
    ram: 32,
    label: 'L4 · 24 GB VRAM · 8 CPU · 32 GB RAM',
    shortLabel: 'L4 · 24GB'
  },
  {
    gpu: 'A10',
    vram: 24,
    cpu: 8,
    ram: 32,
    label: 'A10 · 24 GB VRAM · 8 CPU · 32 GB RAM',
    shortLabel: 'A10 · 24GB'
  },
  {
    gpu: 'L40S',
    vram: 48,
    cpu: 16,
    ram: 64,
    label: 'L40S · 48 GB VRAM · 16 CPU · 64 GB RAM',
    shortLabel: 'L40S · 48GB'
  },
  {
    gpu: 'A100',
    vram: 80,
    cpu: 16,
    ram: 64,
    label: 'A100 · 80 GB VRAM · 16 CPU · 64 GB RAM',
    shortLabel: 'A100 · 80GB'
  },
  {
    gpu: 'RTX-PRO-6000',
    vram: 48,
    cpu: 16,
    ram: 64,
    label: 'RTX-PRO-6000 · 48 GB VRAM · 16 CPU · 64 GB RAM',
    shortLabel: 'RTX-PRO-6000 · 48GB'
  },
  {
    gpu: 'H100',
    vram: 80,
    cpu: 16,
    ram: 64,
    label: 'H100 · 80 GB VRAM · 16 CPU · 64 GB RAM',
    shortLabel: 'H100 · 80GB'
  },
  {
    gpu: 'H200',
    vram: 141,
    cpu: 16,
    ram: 64,
    label: 'H200 · 141 GB VRAM · 16 CPU · 64 GB RAM',
    shortLabel: 'H200 · 141GB'
  }
]

export const DEFAULT_CPU_PRESET = CPU_PRESETS[0]
export const DEFAULT_GPU_PRESET = GPU_PRESETS[0]

export function matchCpuPresetId(
  cores: number,
  ram: number
): string | null {
  return (
    CPU_PRESETS.find(preset => preset.cpu === cores && preset.ram === ram)
      ?.id ?? null
  )
}

export function matchGpuPreset(gpuClass: string): GpuPreset | null {
  return GPU_PRESETS.find(preset => preset.gpu === gpuClass) ?? null
}
