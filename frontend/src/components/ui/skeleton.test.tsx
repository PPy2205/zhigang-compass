import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { SkeletonText, SkeletonCard, SkeletonGraph, SkeletonList } from './skeleton'

describe('SkeletonText', () => {
  it('renders correct number of lines', () => {
    const { container } = render(<SkeletonText lines={5} />)
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThanOrEqual(5)
  })
})

describe('SkeletonCard', () => {
  it('renders with content', () => {
    const { container } = render(<SkeletonCard contentLines={3} />)
    expect(container.querySelector('.animate-pulse')).toBeTruthy()
  })
})

describe('SkeletonGraph', () => {
  it('renders rect variant', () => {
    const { container } = render(<SkeletonGraph variant="rect" />)
    expect(container.querySelector('.animate-pulse')).toBeTruthy()
  })

  it('renders circle variant', () => {
    const { container } = render(<SkeletonGraph variant="circle" />)
    const circle = container.querySelector('.rounded-full')
    expect(circle).toBeTruthy()
  })
})

describe('SkeletonList', () => {
  it('renders correct number of items', () => {
    const { container } = render(<SkeletonList count={4} />)
    const items = container.querySelectorAll('.rounded-md.border')
    expect(items.length).toBe(4)
  })
})
