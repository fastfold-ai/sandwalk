import type {
  AgentSkill,
  McpCatalogEntry,
  McpServer,
  Specialist
} from '@sandwalk/agent-ui-core'
import type { Dispatch, SetStateAction } from 'react'
import { useEffect, useMemo, useState } from 'react'

import {
  emptySpecialistForm,
  type SpecialistCapabilityIssue,
  specialistFormFromRecord,
  type SpecialistFormState
} from '@/components/agents/specialists-view/specialists-view-utils'

type SpecialistsEditorFormInput = {
  mode: 'new' | 'edit'
  editing: Specialist | null
}

export function useSpecialistsEditorForm({
  mode,
  editing
}: SpecialistsEditorFormInput) {
  const [form, setForm] = useState<SpecialistFormState>(emptySpecialistForm)
  const [slugTouched, setSlugTouched] = useState(false)
  const [skillAddQuery, setSkillAddQuery] = useState('')
  const [mcpAddQuery, setMcpAddQuery] = useState('')
  const [skillAddOpen, setSkillAddOpen] = useState(false)
  const [mcpAddOpen, setMcpAddOpen] = useState(false)
  const [appearanceOpen, setAppearanceOpen] = useState(false)
  const [iconQuery, setIconQuery] = useState('')

  useEffect(() => {
    if (mode === 'new') {
      setForm(emptySpecialistForm())
      setSlugTouched(false)
      setSkillAddQuery('')
      setMcpAddQuery('')
      setIconQuery('')
      return
    }
    if (mode === 'edit' && editing) {
      setForm(specialistFormFromRecord(editing))
      setSlugTouched(true)
      setSkillAddQuery('')
      setMcpAddQuery('')
      setIconQuery('')
    }
  }, [editing, mode])

  return {
    form,
    setForm,
    slugTouched,
    setSlugTouched,
    skillAddQuery,
    setSkillAddQuery,
    mcpAddQuery,
    setMcpAddQuery,
    skillAddOpen,
    setSkillAddOpen,
    mcpAddOpen,
    setMcpAddOpen,
    appearanceOpen,
    setAppearanceOpen,
    iconQuery,
    setIconQuery
  }
}

type SpecialistsEditorSelectionInput = {
  form: SpecialistFormState
  setForm: Dispatch<SetStateAction<SpecialistFormState>>
  skills: AgentSkill[]
  mcpServers: McpServer[]
  mcpCatalog: McpCatalogEntry[]
  skillAddQuery: string
  mcpAddQuery: string
  setSkillAddQuery: (value: string) => void
  setMcpAddQuery: (value: string) => void
  setSkillAddOpen: (value: boolean) => void
  setMcpAddOpen: (value: boolean) => void
}

export function useSpecialistsEditorSelection({
  form,
  setForm,
  skills,
  mcpServers,
  mcpCatalog,
  skillAddQuery,
  mcpAddQuery,
  setSkillAddQuery,
  setMcpAddQuery,
  setSkillAddOpen,
  setMcpAddOpen
}: SpecialistsEditorSelectionInput) {
  const availableSkills = useMemo(() => {
    const selected = new Set(form.skillNames)
    const needle = skillAddQuery.trim().toLowerCase()
    return skills.filter(skill => {
      if (selected.has(skill.name)) return false
      if (!needle) return true
      return `${skill.name} ${skill.description || ''}`
        .toLowerCase()
        .includes(needle)
    })
  }, [form.skillNames, skillAddQuery, skills])

  const availableMcps = useMemo(() => {
    const selected = new Set(form.mcpServerIds)
    const needle = mcpAddQuery.trim().toLowerCase()
    return mcpServers.filter(server => {
      if (selected.has(server.id)) return false
      if (!needle) return true
      return `${server.name} ${server.id}`.toLowerCase().includes(needle)
    })
  }, [form.mcpServerIds, mcpAddQuery, mcpServers])

  const selectedSkillRows = useMemo(() => {
    return form.skillNames.map(name => {
      const skill = skills.find(item => item.name === name) || null
      let status: 'ok' | 'missing' | 'disabled' = 'ok'
      let statusLabel: string | null = null
      if (!skill) {
        status = 'missing'
        statusLabel = 'Not installed'
      } else if (!skill.enabled) {
        status = 'disabled'
        statusLabel = 'Disabled'
      }
      return { name, skill, status, statusLabel }
    })
  }, [form.skillNames, skills])

  const selectedMcpRows = useMemo(() => {
    const rows: Array<{
      key: string
      kind: 'server' | 'catalog'
      name: string
      server: McpServer | null
      catalog: McpCatalogEntry | null
      status: 'ok' | 'missing' | 'disabled' | 'disconnected'
      statusLabel: string | null
    }> = []

    for (const id of form.mcpServerIds) {
      const server = mcpServers.find(item => item.id === id) || null
      let status: 'ok' | 'missing' | 'disabled' | 'disconnected' = 'ok'
      let statusLabel: string | null = null
      if (!server) {
        status = 'missing'
        statusLabel = 'Missing server'
      } else if (!server.enabled) {
        status = 'disabled'
        statusLabel = 'Disabled'
      }
      rows.push({
        key: `server:${id}`,
        kind: 'server',
        name: server?.name || id,
        server,
        catalog: null,
        status,
        statusLabel
      })
    }

    for (const catalogId of form.mcpCatalogIds) {
      const catalog = mcpCatalog.find(item => item.id === catalogId) || null
      const server =
        mcpServers.find(item => item.catalogId === catalogId) || null
      let status: 'ok' | 'missing' | 'disabled' | 'disconnected' = 'ok'
      let statusLabel: string | null = null
      if (!server) {
        status = 'disconnected'
        statusLabel = 'Not connected'
      } else if (!server.enabled) {
        status = 'disabled'
        statusLabel = 'Disabled'
      }
      rows.push({
        key: `catalog:${catalogId}`,
        kind: 'catalog',
        name: catalog?.name || server?.name || catalogId,
        server,
        catalog,
        status,
        statusLabel
      })
    }

    return rows
  }, [form.mcpCatalogIds, form.mcpServerIds, mcpCatalog, mcpServers])

  const capabilityIssues = useMemo(() => {
    const issues: SpecialistCapabilityIssue[] = []
    for (const row of selectedSkillRows) {
      if (row.status === 'ok' || !row.statusLabel) continue
      issues.push({ kind: 'skill', name: row.name, detail: row.statusLabel })
    }
    for (const row of selectedMcpRows) {
      if (row.status === 'ok' || !row.statusLabel) continue
      issues.push({ kind: 'mcp', name: row.name, detail: row.statusLabel })
    }
    return issues
  }, [selectedMcpRows, selectedSkillRows])

  const addSkill = (name: string) => {
    setForm(current => ({
      ...current,
      skillNames: Array.from(new Set([...current.skillNames, name])).sort()
    }))
    setSkillAddQuery('')
    setSkillAddOpen(false)
  }

  const removeSkill = (name: string) => {
    setForm(current => ({
      ...current,
      skillNames: current.skillNames.filter(item => item !== name)
    }))
  }

  const addMcp = (id: string) => {
    setForm(current => ({
      ...current,
      mcpServerIds: Array.from(new Set([...current.mcpServerIds, id])).sort()
    }))
    setMcpAddQuery('')
    setMcpAddOpen(false)
  }

  const removeMcp = (id: string) => {
    setForm(current => ({
      ...current,
      mcpServerIds: current.mcpServerIds.filter(item => item !== id)
    }))
  }

  const removeMcpCatalog = (catalogId: string) => {
    setForm(current => ({
      ...current,
      mcpCatalogIds: current.mcpCatalogIds.filter(item => item !== catalogId)
    }))
  }

  return {
    availableSkills,
    availableMcps,
    selectedSkillRows,
    selectedMcpRows,
    capabilityIssues,
    addSkill,
    removeSkill,
    addMcp,
    removeMcp,
    removeMcpCatalog
  }
}
