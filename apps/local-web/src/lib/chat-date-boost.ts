/*
 * Boost temporal del `lastMessageAt` de un chat cuando entra a un split.
 *
 * El servidor no acepta hoy `PATCH /sessions` sobre `last_message_at`, así
 * que para que un chat viejo aparezca en "Today" al agruparlo en un split
 * (y siga apareciendo ahí si el usuario disuelve el split), guardamos un
 * boost en localStorage y lo aplicamos sobre la lista que devuelve el
 * server. Cuando el chat recibe un mensaje real que iguala o supera el
 * boost, el boost se limpia solo — el server vuelve a ser la fuente de
 * verdad y no queda ruido acumulado.
 */

import type { AgentSession } from '@sandwalk/agent-ui-core'

const STORAGE_KEY = 'sandwalk.chat-date-boost'

type BoostMap = Record<string, string>

function readBoosts(): BoostMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') return parsed as BoostMap
  } catch {
    // ignore corrupt storage
  }
  return {}
}

function writeBoosts(map: BoostMap): void {
  try {
    if (Object.keys(map).length === 0) {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
    }
  } catch {
    // storage full / disabled → best effort
  }
}

/** Guarda el boost de varios chats a la misma marca de tiempo (`now` ISO). */
export function setChatDateBoosts(chatIds: string[], iso: string): void {
  if (chatIds.length === 0) return
  const map = readBoosts()
  for (const id of chatIds) map[id] = iso
  writeBoosts(map)
}

/**
 * Aplica los boosts vigentes sobre una lista de sesiones del server.
 * Devuelve la lista con `lastMessageAt` override cuando corresponde, y
 * limpia de storage los boosts que ya quedaron "superados" por actividad
 * real posterior — el server vuelve a mandar; no acumulamos ruido.
 */
export function applyChatDateBoosts(sessions: AgentSession[]): AgentSession[] {
  const boosts = readBoosts()
  if (Object.keys(boosts).length === 0) return sessions
  let mutated = false
  const nextBoosts: BoostMap = { ...boosts }
  const nextSessions = sessions.map(session => {
    const boost = boosts[session.id]
    if (!boost) return session
    const boostTs = new Date(boost).getTime()
    const serverTs = new Date(
      session.lastMessageAt || session.updatedAt || 0
    ).getTime()
    if (Number.isFinite(serverTs) && serverTs >= boostTs) {
      // El server ya alcanzó al boost — limpiar y confiar en el server.
      delete nextBoosts[session.id]
      mutated = true
      return session
    }
    return { ...session, lastMessageAt: boost }
  })
  if (mutated) writeBoosts(nextBoosts)
  return nextSessions
}
