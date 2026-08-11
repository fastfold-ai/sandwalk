import type { AgentSkillSource } from '@sandwalk/agent-ui-core'
import { useEffect, useRef, useState } from 'react'

import type { SkillsViewMode } from '@/lib/skills-catalog'

type SkillsViewImportInput = {
  mode: SkillsViewMode
  installing: boolean
  setInstalling: (value: boolean) => void
  onBack: () => void
  onInstall: (source: string) => Promise<string[] | void>
  onUpload: (file: File) => Promise<void>
  onLoadSuggestedSources: (signal?: AbortSignal) => Promise<AgentSkillSource[]>
}

export function useSkillsViewImport({
  mode,
  installing,
  setInstalling,
  onBack,
  onInstall,
  onUpload,
  onLoadSuggestedSources
}: SkillsViewImportInput) {
  const [githubSource, setGithubSource] = useState(
    'fastfold-ai/skills@skills/fold'
  )
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const uploadInputRef = useRef<HTMLInputElement | null>(null)
  const [trustedSources, setTrustedSources] = useState<AgentSkillSource[]>([])
  const [trustedSelected, setTrustedSelected] = useState<
    Record<string, boolean>
  >({})
  /** False until the first suggestions fetch settles (avoids empty→skeleton flash). */
  const [trustedLoaded, setTrustedLoaded] = useState(false)
  // Parents pass inline lambdas; keep the latest loader without re-firing the effect.
  const loadSuggestedRef = useRef(onLoadSuggestedSources)
  loadSuggestedRef.current = onLoadSuggestedSources

  useEffect(() => {
    if (mode !== 'import_file') return
    const timer = window.setTimeout(() => {
      if (uploadInputRef.current) {
        uploadInputRef.current.value = ''
        uploadInputRef.current.click()
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [mode])

  useEffect(() => {
    if (mode !== 'trusted_sources') return
    const controller = new AbortController()
    let active = true
    void loadSuggestedRef
      .current(controller.signal)
      .then(items => {
        if (!active || controller.signal.aborted) return
        setTrustedSources(items)
        setTrustedSelected(current => {
          const next = { ...current }
          for (const item of items) {
            if (next[item.source] === undefined) next[item.source] = false
          }
          return next
        })
        setTrustedLoaded(true)
      })
      .catch(() => {
        if (!active || controller.signal.aborted) return
        setTrustedSources([])
        setTrustedLoaded(true)
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [mode])

  const submitGithubInstall = async () => {
    if (installing) return
    setInstalling(true)
    try {
      const source = githubSource.trim()
      if (!source) return
      await onInstall(source)
      onBack()
    } finally {
      setInstalling(false)
    }
  }

  const submitFileInstall = async () => {
    if (installing || !uploadFile) return
    setInstalling(true)
    try {
      await onUpload(uploadFile)
      onBack()
    } finally {
      setInstalling(false)
    }
  }

  const selectedTrustedSources = trustedSources
    .map(item => item.source)
    .filter(source => Boolean(trustedSelected[source]))

  const submitTrustedInstall = async () => {
    if (installing || selectedTrustedSources.length === 0) return
    setInstalling(true)
    try {
      for (const source of selectedTrustedSources) {
        await onInstall(source)
      }
      onBack()
    } finally {
      setInstalling(false)
    }
  }

  return {
    githubSource,
    setGithubSource,
    uploadFile,
    setUploadFile,
    uploadInputRef,
    trustedSources,
    trustedSelected,
    setTrustedSelected,
    trustedLoading: mode === 'trusted_sources' && !trustedLoaded,
    selectedTrustedSources,
    submitGithubInstall,
    submitFileInstall,
    submitTrustedInstall
  }
}
