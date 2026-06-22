import { useEffect, useRef } from "react";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion.js";
import "./DotField.css";

function colorWithAlpha(color, alpha) {
  if (color.startsWith("rgba(")) {
    return color;
  }

  if (color.startsWith("#")) {
    const normalized = color.slice(1);
    const value = Number.parseInt(normalized, 16);
    const r = (value >> 16) & 255;
    const g = (value >> 8) & 255;
    const b = value & 255;

    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  return color;
}

export function DotField({
  dotRadius = 1.2,
  dotSpacing = 18,
  bulgeStrength = 35,
  glowRadius = 120,
  sparkle = false,
  waveAmplitude = 0,
  gradientFrom = "rgba(168, 85, 247, 0.18)",
  gradientTo = "rgba(6, 182, 212, 0.12)",
  glowColor = "#111827"
}) {
  const canvasRef = useRef(null);
  const pointerRef = useRef({ x: -1000, y: -1000 });
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;

    if (!canvas || prefersReducedMotion) {
      return undefined;
    }

    if (typeof window.CanvasRenderingContext2D === "undefined") {
      return undefined;
    }

    let context;
    try {
      context = canvas.getContext("2d");
    } catch {
      return undefined;
    }

    if (!context) {
      return undefined;
    }

    let animationFrame = 0;
    let startedAt = performance.now();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const draw = (time = startedAt) => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const cssWidth = Math.max(width, 1);
      const cssHeight = Math.max(height, 1);

      if (canvas.width !== Math.floor(cssWidth * dpr) || canvas.height !== Math.floor(cssHeight * dpr)) {
        canvas.width = Math.floor(cssWidth * dpr);
        canvas.height = Math.floor(cssHeight * dpr);
        canvas.style.width = `${cssWidth}px`;
        canvas.style.height = `${cssHeight}px`;
      }

      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, cssWidth, cssHeight);

      const gradient = context.createLinearGradient(0, 0, cssWidth, cssHeight);
      gradient.addColorStop(0, gradientFrom);
      gradient.addColorStop(1, gradientTo);
      context.fillStyle = gradient;

      const pointer = pointerRef.current;
      const elapsed = (time - startedAt) * 0.001;

      for (let y = -dotSpacing; y <= cssHeight + dotSpacing; y += dotSpacing) {
        for (let x = -dotSpacing; x <= cssWidth + dotSpacing; x += dotSpacing) {
          const dx = x - pointer.x;
          const dy = y - pointer.y;
          const distance = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const influence = Math.max(0, 1 - distance / glowRadius);
          const offset = influence * bulgeStrength;
          const directionX = dx / distance;
          const directionY = dy / distance;
          const wave = waveAmplitude ? Math.sin(elapsed + x * 0.015 + y * 0.01) * waveAmplitude : 0;
          const radius = dotRadius + influence * 0.55 + (sparkle ? Math.sin(elapsed * 2.1 + x) * 0.16 : 0);

          context.beginPath();
          context.arc(
            x + directionX * offset,
            y + directionY * offset + wave,
            Math.max(radius, 0.7),
            0,
            Math.PI * 2
          );
          context.fill();
        }
      }

      if (pointer.x >= 0 && pointer.y >= 0) {
        const glow = context.createRadialGradient(
          pointer.x,
          pointer.y,
          0,
          pointer.x,
          pointer.y,
          glowRadius
        );
        glow.addColorStop(0, colorWithAlpha(glowColor, 0.08));
        glow.addColorStop(1, colorWithAlpha(glowColor, 0));
        context.fillStyle = glow;
        context.fillRect(0, 0, cssWidth, cssHeight);
      }

      if (sparkle || waveAmplitude > 0) {
        animationFrame = requestAnimationFrame(draw);
      }
    };

    const scheduleDraw = () => {
      cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(draw);
    };

    const onPointerMove = (event) => {
      pointerRef.current = { x: event.clientX, y: event.clientY };
      scheduleDraw();
    };

    const onPointerLeave = () => {
      pointerRef.current = { x: -1000, y: -1000 };
      scheduleDraw();
    };

    const onResize = () => {
      scheduleDraw();
    };

    startedAt = performance.now();
    draw(startedAt);

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("pointerleave", onPointerLeave);
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerleave", onPointerLeave);
      window.removeEventListener("resize", onResize);
    };
  }, [
    bulgeStrength,
    dotRadius,
    dotSpacing,
    glowColor,
    glowRadius,
    gradientFrom,
    gradientTo,
    prefersReducedMotion,
    sparkle,
    waveAmplitude
  ]);

  if (prefersReducedMotion) {
    return null;
  }

  return (
    <div className="dot-field" aria-hidden="true">
      <canvas className="dot-field__canvas" ref={canvasRef} />
    </div>
  );
}
