import type { Specialist } from '@sandwalk/agent-ui-core'
import { useState } from 'react'
import { toast } from 'sonner'

import {
  resolveSkillInstallSource,
  type SpecialistFormState
} from '@/components/agents/specialists-view/specialists-view-utils'

type SpecialistsEditorActionsInput = {
  mode: 'new' | 'edit'
  specialistId: string | null
  form: SpecialistFormState
  onRefresh: () => Promise<void>
  onCreate: (input: {
    name: string
    slug?: string | null
    description?: string | null
    instructions?: string | null
    color?: string
    icon?: string
    skillNames?: string[]
    toolNames?: string[]
    mcpServerIds?: string[]
    mcpCatalogIds?: string[]
    enabled?: boolean
  }) => Promise<Specialist>
  onUpdate: (
    id: string,
    input: {
      name?: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    }
  ) => Promise<Specialist>
  onDelete: (id: string) => Promise<void>
  onOpenEdit: (id: string) => void
  onBack: () => void
  onManageSkills?: () => void
  onEnableSkill?: (name: string) => Promise<void>
  onInstallSkill?: (source: string) => Promise<void>
}

export function useSpecialistsEditorActions({
  mode,
  specialistId,
  form,
  onRefresh,
  onCreate,
  onUpdate,
  onDelete,
  onOpenEdit,
  onBack,
  onManageSkills,
  onEnableSkill,
  onInstallSkill
}: SpecialistsEditorActionsInput) {
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [skillActionPending, setSkillActionPending] = useState<string | null>(
    null
  )
  const [togglePendingId, setTogglePendingId] = useState<string | null>(null)

  const save = async () => {
    const name = form.name.trim()
    if (!name) {
      toast.error('Name is required')
      return
    }
    setSaving(true)
    try {
      const payload = {
        name,
        slug: form.slug.trim() || undefined,
        description: form.description.trim() || null,
        instructions: form.instructions.trim() || null,
        color: form.color,
        icon: form.icon,
        skillNames: form.skillNames,
        toolNames: form.toolNames,
        mcpServerIds: form.mcpServerIds,
        mcpCatalogIds: form.mcpCatalogIds,
        enabled: form.enabled
      }
      if (mode === 'edit' && specialistId) {
        await onUpdate(specialistId, payload)
        await onRefresh()
        toast.success('Specialist saved')
      } else {
        const created = await onCreate(payload)
        await onRefresh()
        toast.success('Specialist created')
        onOpenEdit(created.id)
      }
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : 'Unable to save specialist'
      )
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!specialistId) return
    if (
      !window.confirm(
        'Delete this specialist? Sessions using it will clear the selection.'
      )
    ) {
      return
    }
    setDeleting(true)
    try {
      await onDelete(specialistId)
      toast.success('Specialist deleted')
      await onRefresh()
      onBack()
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : 'Unable to delete specialist'
      )
    } finally {
      setDeleting(false)
    }
  }

  const toggleSpecialistEnabled = async (
    id: string,
    nextEnabled: boolean
  ) => {
    setTogglePendingId(id)
    try {
      await onUpdate(id, { enabled: nextEnabled })
      await onRefresh()
    } catch (cause) {
      toast.error(
        cause instanceof Error
          ? cause.message
          : 'Unable to update specialist'
      )
    } finally {
      setTogglePendingId(null)
    }
  }

  const handleEnableSkill = async (name: string) => {
    if (!onEnableSkill) return
    setSkillActionPending(name)
    try {
      await onEnableSkill(name)
      toast.success(`Enabled ${name}`)
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : `Unable to enable ${name}`
      )
    } finally {
      setSkillActionPending(null)
    }
  }

  const handleInstallSkill = async (name: string) => {
    const source = resolveSkillInstallSource(name)
    if (!source || !onInstallSkill) {
      onManageSkills?.()
      toast.message(`Open Skills to install “${name}”.`)
      return
    }
    setSkillActionPending(name)
    try {
      await onInstallSkill(source)
      toast.success(`Installed ${name}`)
    } catch (cause) {
      toast.error(
        cause instanceof Error
          ? cause.message
          : `Unable to install ${name}. Try Skills → Find.`
      )
    } finally {
      setSkillActionPending(null)
    }
  }

  return {
    saving,
    deleting,
    skillActionPending,
    togglePendingId,
    save,
    remove,
    toggleSpecialistEnabled,
    handleEnableSkill,
    handleInstallSkill
  }
}
