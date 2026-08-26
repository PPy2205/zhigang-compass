import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebouncedValue, useDebouncedCallback } from './hooks'

describe('useDebouncedValue', () => {
  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebouncedValue('hello', 100))
    expect(result.current).toBe('hello')
  })

  it('updates after delay', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(({ val }) => useDebouncedValue(val, 100), {
      initialProps: { val: 'a' },
    })
    expect(result.current).toBe('a')

    rerender({ val: 'b' })
    expect(result.current).toBe('a') // not yet updated

    act(() => vi.advanceTimersByTime(100))
    expect(result.current).toBe('b')
    vi.useRealTimers()
  })
})

describe('useDebouncedCallback', () => {
  it('debounces calls', () => {
    vi.useFakeTimers()
    const fn = vi.fn()
    const { result } = renderHook(() => useDebouncedCallback(fn, 100))

    act(() => {
      result.current('a')
      result.current('b')
      result.current('c')
    })
    expect(fn).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(100))
    expect(fn).toHaveBeenCalledTimes(1)
    expect(fn).toHaveBeenCalledWith('c')
    vi.useRealTimers()
  })

  it('returns stable reference', () => {
    const fn = vi.fn()
    const { result, rerender } = renderHook(() => useDebouncedCallback(fn, 100))
    const first = result.current
    rerender()
    expect(result.current).toBe(first)
  })
})
