import type {
  AgentSkillBatchAction,
  AgentSkillBatchResult,
  AgentSkillDetail
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useState } from 'react'

import { skillInstallSource, type SkillsViewMode } from '@/lib/skills-catalog'

import { resolveInstalledDetailPresentation } from './skills-view-installed-detail'
import type { useSkillsViewFilters } from './use-skills-view-filters'

type SkillsViewListActionsInput = {
  mode: SkillsViewMode
  detail: AgentSkillDetail | null
  listData: ReturnType<typeof useSkillsViewFilters>['listData']
  onBack: () => void
  onBulkAction: (
    action: AgentSkillBatchAction,
    names: string[]
  ) => Promise<AgentSkillBatchResult>
  onSetEnabled: (name: string, enabled: boolean) => Promise<void>
  onRemove: (name: string) => Promise<void>
}

export function useSkillsViewListActions({
  mode,
  detail,
  listData,
  onBack,
  onBulkAction,
  onSetEnabled,
  onRemove
}: SkillsViewListActionsInput) {
  const [pendingEnabled, setPendingEnabled] = useState<Record<string, boolean>>({})
  const [pendingRemove, setPendingRemove] = useState<Record<string, boolean>>({})
  const [removeTarget, setRemoveTarget] = useState<
    | { type: 'single'; name: string }
    | { type: 'filtered'; count: number }
    | null
  >(null)
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchToast, setBatchToast] = useState<{
    message: string
    tone: 'success' | 'warning'
  } | null>(null)
  const [copiedInstall, setCopiedInstall] = useState(false)

  useEffect(() => {
    if (!batchToast) return
    const timer = window.setTimeout(() => setBatchToast(null), 2800)
    return () => window.clearTimeout(timer)
  }, [batchToast])

  useEffect(() => {
    setCopiedInstall(false)
  }, [detail?.name])

  const detailInstallCommand = detail
    ? `sandwalk skills add ${skillInstallSource(detail.name, detail.source)} --skill ${detail.name}`
    : ''

  const detailPresentation = detail
    ? resolveInstalledDetailPresentation(detail)
    : null

  const handleCopyInstall = useCallback(() => {
    if (!detailInstallCommand) return
    void navigator.clipboard.writeText(detailInstallCommand).then(() => {
      setCopiedInstall(true)
      window.setTimeout(() => setCopiedInstall(false), 2000)
    })
  }, [detailInstallCommand])

  const setSkillEnabled = async (name: string, enabled: boolean) => {
    setPendingEnabled(current => ({ ...current, [name]: true }))
    try {
      await onSetEnabled(name, enabled)
    } finally {
      setPendingEnabled(current => ({ ...current, [name]: false }))
    }
  }

  const removeSkill = (name: string) => {
    if (batchBusy || pendingRemove[name]) return
    setRemoveTarget({ type: 'single', name })
  }

  const removeFiltered = () => {
    if (listData.filteredSkillNames.length === 0 || batchBusy) return
    setRemoveTarget({
      type: 'filtered',
      count: listData.filteredSkillNames.length
    })
  }

  const confirmRemoveSkill = async () => {
    const target = removeTarget
    if (!target) return
    setRemoveTarget(null)
    if (target.type === 'single') {
      const name = target.name
      setPendingRemove(current => ({ ...current, [name]: true }))
      try {
        await onRemove(name)
        if (mode === 'detail' && detail?.name === name) {
          onBack()
        }
      } finally {
        setPendingRemove(current => ({ ...current, [name]: false }))
      }
      return
    }
    if (listData.filteredSkillNames.length === 0 || batchBusy) return
    setBatchBusy(true)
    try {
      const result = await onBulkAction('remove', listData.filteredSkillNames)
      setBatchToast({
        message:
          result.failed.length > 0
            ? `Removed ${result.succeeded.length}/${result.requested} skills (${result.failed.length} failed).`
            : `Removed ${result.succeeded.length}/${result.requested} skills.`,
        tone: result.failed.length > 0 ? 'warning' : 'success'
      })
      if (mode === 'detail' && detail && result.succeeded.includes(detail.name)) {
        onBack()
      }
    } finally {
      setBatchBusy(false)
    }
  }

  const setFilteredEnabled = async (enabled: boolean) => {
    if (listData.filteredSkillNames.length === 0 || batchBusy) return
    setBatchBusy(true)
    try {
      const result = await onBulkAction(
        enabled ? 'enable' : 'disable',
        listData.filteredSkillNames
      )
      const actionLabel = enabled ? 'Enabled' : 'Disabled'
      setBatchToast({
        message:
          result.failed.length > 0
            ? `${actionLabel} ${result.succeeded.length}/${result.requested} skills (${result.failed.length} failed).`
            : `${actionLabel} ${result.succeeded.length}/${result.requested} skills.`,
        tone: result.failed.length > 0 ? 'warning' : 'success'
      })
    } finally {
      setBatchBusy(false)
    }
  }

  const handleRemoveDialogOpenChange = (open: boolean) => {
    if (!open) setRemoveTarget(null)
  }

  return {
    pendingEnabled,
    pendingRemove,
    removeTarget,
    batchBusy,
    batchToast,
    copiedInstall,
    detailInstallCommand,
    detailPresentation,
    handleCopyInstall,
    setSkillEnabled,
    removeSkill,
    removeFiltered,
    confirmRemoveSkill,
    setFilteredEnabled,
    handleRemoveDialogOpenChange
  }
}
