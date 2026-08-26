import { describe, it, expect } from 'vitest'
import { prefetchRoute } from './prefetch'

describe('prefetchRoute', () => {
  it('does nothing for unknown path', () => {
    expect(() => prefetchRoute('/unknown-path')).not.toThrow()
  })

  it('does not throw for empty string', () => {
    expect(() => prefetchRoute('')).not.toThrow()
  })

  it('handles known route gracefully (import may fail in test env)', () => {
    // Import may fail in test environment, but prefetchRoute should not throw
    expect(() => prefetchRoute('/')).not.toThrow()
  })
})
