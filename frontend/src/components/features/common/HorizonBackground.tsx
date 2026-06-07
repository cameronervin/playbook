'use client'

import { useEffect, useRef } from 'react'

export function HorizonBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    if (window.navigator.userAgent.toLowerCase().includes('jsdom')) return
    const canvas = canvasRef.current
    if (!canvas) return
    let context: CanvasRenderingContext2D | null = null
    try {
      context = canvas.getContext('2d')
    } catch {
      return
    }
    if (!context) return

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let animationFrame = 0
    let tick = 0

    const resize = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio
      canvas.height = window.innerHeight * window.devicePixelRatio
      canvas.style.width = `${window.innerWidth}px`
      canvas.style.height = `${window.innerHeight}px`
      context.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0)
    }

    const draw = () => {
      const width = window.innerWidth
      const height = window.innerHeight
      context.clearRect(0, 0, width, height)
      context.strokeStyle = 'rgba(255, 115, 0, 0.16)'
      context.lineWidth = 1
      const horizon = height * 0.58
      for (let row = 0; row < 20; row += 1) {
        const y = horizon + row * row * 1.55
        context.beginPath()
        context.moveTo(0, y + Math.sin(tick + row * 0.4) * 4)
        context.lineTo(width, y + Math.cos(tick + row * 0.3) * 4)
        context.stroke()
      }
      for (let col = -12; col <= 12; col += 1) {
        const x = width / 2 + col * 38
        context.beginPath()
        context.moveTo(x, horizon)
        context.lineTo(width / 2 + col * 140, height)
        context.stroke()
      }
      tick += 0.015
      if (!reduceMotion) animationFrame = requestAnimationFrame(draw)
    }

    resize()
    draw()
    window.addEventListener('resize', resize)
    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animationFrame)
    }
  }, [])

  return <canvas ref={canvasRef} className="pointer-events-none fixed inset-0 opacity-70" aria-hidden="true" />
}
