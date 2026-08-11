import { describe, expect, it } from 'vitest'

import { seekVideoPosterFrame } from './VideoPlayPreview'

describe('seekVideoPosterFrame', () => {
  it('seeks to a small non-zero time so a frame can decode', () => {
    const video = {
      duration: 10,
      currentTime: 0
    } as HTMLVideoElement

    seekVideoPosterFrame(video)
    expect(video.currentTime).toBeCloseTo(0.1, 5)
  })

  it('clamps short clips near the start', () => {
    const video = {
      duration: 0.05,
      currentTime: 0
    } as HTMLVideoElement

    seekVideoPosterFrame(video)
    expect(video.currentTime).toBeCloseTo(0.001, 5)
  })

  it('ignores seek errors', () => {
    const video = {
      duration: 5,
      get currentTime() {
        return 0
      },
      set currentTime(_value: number) {
        throw new Error('seek blocked')
      }
    } as HTMLVideoElement

    expect(() => seekVideoPosterFrame(video)).not.toThrow()
  })
})
