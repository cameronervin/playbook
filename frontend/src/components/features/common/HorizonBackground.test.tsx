import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'
import { HorizonBackground } from '@/src/components/features/common/HorizonBackground'

interface MockCanvasContext {
  beginPath: ReturnType<typeof vi.fn>
  clearRect: ReturnType<typeof vi.fn>
  lineTo: ReturnType<typeof vi.fn>
  moveTo: ReturnType<typeof vi.fn>
  setTransform: ReturnType<typeof vi.fn>
  stroke: ReturnType<typeof vi.fn>
  lineWidth: number
  strokeStyle: string
}

function createContext(): MockCanvasContext {
  return {
    beginPath: vi.fn(),
    clearRect: vi.fn(),
    lineTo: vi.fn(),
    moveTo: vi.fn(),
    setTransform: vi.fn(),
    stroke: vi.fn(),
    lineWidth: 0,
    strokeStyle: '',
  }
}

describe('HorizonBackground', () => {
  const originalUserAgent = window.navigator.userAgent
  let context: MockCanvasContext

  beforeEach(() => {
    context = createContext()
    Object.defineProperty(window.navigator, 'userAgent', {
      configurable: true,
      value: 'vitest',
    })
    Object.defineProperty(window, 'devicePixelRatio', {
      configurable: true,
      value: 3,
    })
    Object.defineProperty(HTMLCanvasElement.prototype, 'clientWidth', {
      configurable: true,
      value: 800,
    })
    Object.defineProperty(HTMLCanvasElement.prototype, 'clientHeight', {
      configurable: true,
      value: 600,
    })
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as unknown as CanvasRenderingContext2D)
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      addEventListener: vi.fn(),
      addListener: vi.fn(),
      dispatchEvent: vi.fn(),
      matches: false,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      removeEventListener: vi.fn(),
      removeListener: vi.fn(),
    })
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1)
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => undefined)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    Object.defineProperty(window.navigator, 'userAgent', {
      configurable: true,
      value: originalUserAgent,
    })
  })

  it('draws the horizon canvas and schedules animation when motion is enabled', () => {
    render(<HorizonBackground />)

    expect(context.setTransform).toHaveBeenCalledWith(2, 0, 0, 2, 0, 0)
    expect(context.clearRect).toHaveBeenCalledWith(0, 0, 800, 600)
    expect(context.lineTo).toHaveBeenCalled()
    expect(window.requestAnimationFrame).toHaveBeenCalled()
  })

  it('freezes after the first frame when reduced motion is requested', () => {
    vi.mocked(window.matchMedia).mockReturnValue({
      addEventListener: vi.fn(),
      addListener: vi.fn(),
      dispatchEvent: vi.fn(),
      matches: true,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      removeEventListener: vi.fn(),
      removeListener: vi.fn(),
    })

    const { unmount } = render(<HorizonBackground />)

    expect(context.lineTo).toHaveBeenCalled()
    expect(window.requestAnimationFrame).not.toHaveBeenCalled()

    unmount()
    expect(window.cancelAnimationFrame).toHaveBeenCalledWith(0)
  })
})
