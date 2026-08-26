import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { BottomNav } from './bottom-nav'
import { useAuthStore } from '@/store/auth'

// Mock auth store
vi.mock('@/store/auth', () => ({
  useAuthStore: vi.fn(),
}))

function renderWithRouter(ui: React.ReactNode, route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      {ui}
    </MemoryRouter>,
  )
}

describe('BottomNav', () => {
  it('renders only on mobile (sm:hidden class)', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: { id: '1', username: 'test', role: 'user', permissions: [] },
      isAuthenticated: true,
    } as never)

    const { container } = renderWithRouter(<BottomNav />)
    const nav = container.querySelector('nav')
    expect(nav).toBeTruthy()
    expect(nav?.className).toContain('sm:hidden')
  })

  it('shows public items for guest user', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: null,
      isAuthenticated: false,
    } as never)

    const { container } = renderWithRouter(<BottomNav />)
    const links = container.querySelectorAll('a')
    const linkTexts = Array.from(links).map((l) => l.textContent?.trim())
    // Guests see dashboard, graph, evolution (public pages)
    expect(linkTexts.some((t) => t?.includes('仪表盘'))).toBe(true)
    expect(linkTexts.some((t) => t?.includes('能力图谱'))).toBe(true)
    expect(linkTexts.some((t) => t?.includes('演化看板'))).toBe(true)
    // Guests do NOT see resume-match or profile
    expect(linkTexts.some((t) => t?.includes('简历匹配'))).toBe(false)
    expect(linkTexts.some((t) => t?.includes('个人中心'))).toBe(false)
  })

  it('shows user items for authenticated user', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: { id: '1', username: 'test', role: 'user', permissions: [] },
      isAuthenticated: true,
    } as never)

    const { container } = renderWithRouter(<BottomNav />)
    const links = container.querySelectorAll('a')
    const linkTexts = Array.from(links).map((l) => l.textContent?.trim())
    expect(linkTexts.some((t) => t?.includes('简历匹配'))).toBe(true)
    expect(linkTexts.some((t) => t?.includes('个人中心'))).toBe(true)
  })

  it('limits to 5 tabs max on mobile', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: { id: '1', username: 'admin', role: 'admin', permissions: [] },
      isAuthenticated: true,
    } as never)

    const { container } = renderWithRouter(<BottomNav />)
    const links = container.querySelectorAll('a')
    expect(links.length).toBeLessThanOrEqual(5)
  })

  it('active route is highlighted', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: null,
      isAuthenticated: false,
    } as never)

    const { container } = renderWithRouter(<BottomNav />, '/graph')
    const activeLink = container.querySelector('a.text-ink')
    expect(activeLink).toBeTruthy()
    expect(activeLink?.textContent).toContain('能力图谱')
  })
})
