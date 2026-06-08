'use client'

import { useEffect, useRef } from 'react'

interface HorizonBackgroundProps {
  motion?: boolean
}

export function HorizonBackground({ motion = true }: HorizonBackgroundProps) {
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

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches || !motion
    let animationFrame = 0
    let width = 0
    let height = 0
    let time = 0
    const columns = 22
    const rows = 22
    const step = 1
    const near = 2.0
    const waveAmplitude = 0.2
    const waveFrequency = 0.95
    const zFrequency = 0.5
    const timeSpeed = 0.9

    const resize = () => {
      const devicePixelRatio = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = Math.round(width * devicePixelRatio)
      canvas.height = Math.round(height * devicePixelRatio)
      context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0)
    }

    const draw = () => {
      context.clearRect(0, 0, width, height)
      const horizonY = height * 0.6
      const centerX = width / 2
      const focal = height * 0.92
      const cameraHeight = 1.0
      const offset = (time * 0.45) % step

      const project = (worldX: number, z: number): [number, number] => {
        const perspectiveScale = focal / z
        const elevation = waveAmplitude * Math.sin(worldX * waveFrequency + z * zFrequency + time * timeSpeed)
        return [centerX + worldX * perspectiveScale, horizonY + (cameraHeight - elevation) * perspectiveScale]
      }

      for (let column = -columns; column <= columns; column += 1) {
        context.strokeStyle = 'rgba(255, 120, 10, 0.10)'
        context.lineWidth = 1
        context.beginPath()
        let isFirstPoint = true
        for (let row = 0; row < rows; row += 1) {
          const z = near + row * step - offset
          if (z <= 0.25) continue
          const point = project(column * 0.5, z)
          if (isFirstPoint) {
            context.moveTo(point[0], point[1])
            isFirstPoint = false
          } else {
            context.lineTo(point[0], point[1])
          }
        }
        context.stroke()
      }

      for (let row = 0; row < rows; row += 1) {
        const z = near + row * step - offset
        if (z <= 0.25) continue
        const fade = Math.max(0, 1 - (z - near) / (rows * step))
        context.strokeStyle = `rgba(255, 120, 10, ${(0.55 * fade * fade).toFixed(3)})`
        context.lineWidth = 1
        context.beginPath()
        for (let column = -columns; column <= columns; column += 1) {
          const point = project(column * 0.5, z)
          if (column === -columns) {
            context.moveTo(point[0], point[1])
          } else {
            context.lineTo(point[0], point[1])
          }
        }
        context.stroke()
      }

      if (!reduceMotion) {
        time += 0.016
        animationFrame = requestAnimationFrame(draw)
      }
    }

    resize()
    draw()
    const handleResize = () => {
      resize()
      if (reduceMotion) draw()
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      cancelAnimationFrame(animationFrame)
    }
  }, [motion])

  return (
    <canvas
      ref={canvasRef}
      className="pb-horizon-canvas"
      aria-hidden="true"
      data-testid="horizon-background"
    />
  )
}
