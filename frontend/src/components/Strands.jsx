import { useEffect, useRef } from "react";
import { Mesh, Program, Renderer, Triangle } from "ogl";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion.js";
import "./Strands.css";

const vertex = `
attribute vec2 position;

void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const fragment = `
precision highp float;

uniform vec2 uResolution;
uniform float uTime;
uniform float uCount;
uniform float uSpeed;
uniform float uAmplitude;
uniform float uWaviness;
uniform float uThickness;
uniform float uGlow;
uniform float uOpacity;
uniform float uScale;
uniform vec3 uColor0;
uniform vec3 uColor1;
uniform vec3 uColor2;

vec3 pickColor(int index) {
  if (index == 1 || index == 4 || index == 7) {
    return uColor1;
  }
  if (index == 2 || index == 5) {
    return uColor2;
  }
  return uColor0;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution.xy;
  uv.x = (uv.x - 0.5) * (uResolution.x / max(uResolution.y, 1.0)) + 0.5;

  vec3 color = vec3(0.0);
  float alpha = 0.0;

  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    if (fi >= uCount) {
      continue;
    }

    float band = (fi + 1.0) / (uCount + 1.0);
    float phase = uTime * uSpeed + fi * 1.73;
    float waveA = sin((uv.x * uScale + phase) * (3.2 + uWaviness * 2.4) + fi);
    float waveB = sin((uv.x * uScale * 1.7 - phase * 0.62) * (2.0 + uWaviness) + fi * 0.7);
    float y = 0.18 + band * 0.64 + (waveA * 0.09 + waveB * 0.035) * uAmplitude;
    float dist = abs(uv.y - y);
    float line = exp(-pow(dist / max(uThickness * 0.018, 0.002), 2.0));
    float glow = exp(-pow(dist / max(uGlow * 0.038, 0.004), 2.0)) * 0.36;
    float strength = (line + glow) * uOpacity;
    vec3 strandColor = pickColor(i);

    color += strandColor * strength;
    alpha = max(alpha, strength);
  }

  gl_FragColor = vec4(color, clamp(alpha, 0.0, 0.82));
}
`;

function hexToRgb(hexColor) {
  const normalized = hexColor.replace("#", "");
  const value = Number.parseInt(normalized, 16);

  return [
    ((value >> 16) & 255) / 255,
    ((value >> 8) & 255) / 255,
    (value & 255) / 255
  ];
}

function canUseWebGL(canvas) {
  if (
    typeof window.WebGLRenderingContext === "undefined" &&
    typeof window.WebGL2RenderingContext === "undefined"
  ) {
    return false;
  }

  try {
    return Boolean(
      canvas.getContext("webgl2", { alpha: true }) ||
        canvas.getContext("webgl", { alpha: true }) ||
        canvas.getContext("experimental-webgl", { alpha: true })
    );
  } catch {
    return false;
  }
}

export function Strands({
  colors = ["#F97316", "#7C3AED", "#06B6D4"],
  count = 3,
  speed = 0.35,
  amplitude = 0.8,
  waviness = 0.9,
  thickness = 0.55,
  glow = 2.0,
  opacity = 0.65,
  scale = 1.4,
  glass = false
}) {
  const canvasRef = useRef(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;

    if (!canvas || prefersReducedMotion || !canUseWebGL(canvas)) {
      return undefined;
    }

    const renderer = new Renderer({
      canvas,
      alpha: true,
      antialias: true,
      dpr: Math.min(window.devicePixelRatio || 1, 2)
    });
    const gl = renderer.gl;
    gl.clearColor(0, 0, 0, 0);

    const geometry = new Triangle(gl);
    const program = new Program(gl, {
      vertex,
      fragment,
      transparent: true,
      uniforms: {
        uResolution: { value: [1, 1] },
        uTime: { value: 0 },
        uCount: { value: count },
        uSpeed: { value: speed },
        uAmplitude: { value: amplitude },
        uWaviness: { value: waviness },
        uThickness: { value: thickness },
        uGlow: { value: glow },
        uOpacity: { value: opacity },
        uScale: { value: scale },
        uColor0: { value: hexToRgb(colors[0] || "#F97316") },
        uColor1: { value: hexToRgb(colors[1] || "#7C3AED") },
        uColor2: { value: hexToRgb(colors[2] || "#06B6D4") }
      }
    });
    const mesh = new Mesh(gl, { geometry, program });
    let animationFrame = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(Math.floor(rect.width), 1);
      const height = Math.max(Math.floor(rect.height), 1);

      renderer.setSize(width, height);
      program.uniforms.uResolution.value = [width, height];
    };

    const render = (time) => {
      program.uniforms.uTime.value = time * 0.001;
      renderer.render({ scene: mesh });
      animationFrame = requestAnimationFrame(render);
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    resize();
    animationFrame = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
    };
  }, [
    amplitude,
    colors,
    count,
    glow,
    opacity,
    prefersReducedMotion,
    scale,
    speed,
    thickness,
    waviness
  ]);

  if (prefersReducedMotion) {
    return null;
  }

  return (
    <div className={`strands${glass ? " strands--glass" : ""}`} aria-hidden="true">
      <canvas className="strands__canvas" ref={canvasRef} />
    </div>
  );
}
