import { useMemo, useRef } from "react";
import gsap from "gsap";

export function PixelTransition({
  firstContent,
  secondContent,
  gridSize = 12,
  className = ""
}) {
  const rootRef = useRef(null);
  const frontRef = useRef(null);
  const backRef = useRef(null);
  const pixelsRef = useRef([]);
  const pixelIndexes = useMemo(
    () => Array.from({ length: gridSize * gridSize }, (_, index) => index),
    [gridSize]
  );

  const animateToBack = () => {
    const pixels = pixelsRef.current.filter(Boolean);

    gsap.killTweensOf([frontRef.current, backRef.current, pixels]);
    gsap.set(backRef.current, { opacity: 1 });
    gsap.set(frontRef.current, { opacity: 1 });
    gsap.set(pixels, { opacity: 0, scale: 0.64 });

    gsap
      .timeline()
      .to(pixels, {
        opacity: 1,
        scale: 1,
        duration: 0.12,
        ease: "steps(1)",
        stagger: {
          amount: 0.28,
          from: "random",
          grid: [gridSize, gridSize]
        }
      })
      .to(frontRef.current, { opacity: 0, duration: 0.01 }, "-=0.18")
      .to(
        pixels,
        {
          opacity: 0,
          duration: 0.1,
          ease: "steps(1)",
          stagger: {
            amount: 0.18,
            from: "random",
            grid: [gridSize, gridSize]
          }
        },
        "-=0.06"
      );
  };

  const animateToFront = () => {
    const pixels = pixelsRef.current.filter(Boolean);

    gsap.killTweensOf([frontRef.current, backRef.current, pixels]);
    gsap.set(frontRef.current, { opacity: 1 });
    gsap.set(backRef.current, { opacity: 1 });
    gsap.set(pixels, { opacity: 0, scale: 0.64 });

    gsap
      .timeline()
      .to(pixels, {
        opacity: 1,
        scale: 1,
        duration: 0.1,
        ease: "steps(1)",
        stagger: {
          amount: 0.2,
          from: "random",
          grid: [gridSize, gridSize]
        }
      })
      .to(backRef.current, { opacity: 0, duration: 0.01 }, "-=0.14")
      .to(
        pixels,
        {
          opacity: 0,
          duration: 0.08,
          ease: "steps(1)",
          stagger: {
            amount: 0.14,
            from: "random",
            grid: [gridSize, gridSize]
          }
        },
        "-=0.04"
      );
  };

  return (
    <div
      className={`pixel-transition ${className}`.trim()}
      ref={rootRef}
      onMouseEnter={animateToBack}
      onMouseLeave={animateToFront}
      onFocus={animateToBack}
      onBlur={animateToFront}
      tabIndex={0}
    >
      <div className="pixel-transition__layer pixel-transition__back" ref={backRef}>
        {secondContent}
      </div>
      <div className="pixel-transition__layer pixel-transition__front" ref={frontRef}>
        {firstContent}
      </div>
      <div
        className="pixel-transition__pixels"
        aria-hidden="true"
        style={{
          gridTemplateColumns: `repeat(${gridSize}, 1fr)`,
          gridTemplateRows: `repeat(${gridSize}, 1fr)`
        }}
      >
        {pixelIndexes.map((index) => (
          <span
            className="pixel-transition__pixel"
            key={index}
            ref={(element) => {
              pixelsRef.current[index] = element;
            }}
          />
        ))}
      </div>
    </div>
  );
}
