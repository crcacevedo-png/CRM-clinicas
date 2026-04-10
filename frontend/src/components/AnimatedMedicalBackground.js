import { useEffect, useRef } from 'react';

export default function AnimatedMedicalBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let time = 0;

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };

    resize();
    window.addEventListener('resize', resize);

    // Draw gradient background
    const drawBackground = (width, height) => {
      const gradient = ctx.createRadialGradient(
        width * 0.5, height * 0.5, 0,
        width * 0.5, height * 0.5, Math.max(width, height) * 0.8
      );
      gradient.addColorStop(0, '#0F2A44');
      gradient.addColorStop(0.5, '#0A2540');
      gradient.addColorStop(1, '#071A2B');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);
    };

    // Color palette for grid - different blue tones
    const getGridColor = (x, y, t, width, height) => {
      // Create slow wave patterns across the grid
      const waveSpeed = 0.0003;
      const spatialFreqX = 0.003;
      const spatialFreqY = 0.004;
      
      // Multiple overlapping waves for organic feel
      const wave1 = Math.sin(x * spatialFreqX + t * waveSpeed) * 0.5 + 0.5;
      const wave2 = Math.sin(y * spatialFreqY + t * waveSpeed * 0.7) * 0.5 + 0.5;
      const wave3 = Math.sin((x + y) * 0.002 + t * waveSpeed * 0.5) * 0.5 + 0.5;
      
      // Combine waves
      const combined = (wave1 + wave2 + wave3) / 3;
      
      // Color variations in blue spectrum
      // Base teal: rgb(46, 196, 182) - #2EC4B6
      // Dark blue: rgb(10, 37, 64) - #0A2540
      // Cyan accent: rgb(56, 189, 248) - #38BDF8
      
      const r = Math.floor(20 + combined * 30);  // 20-50
      const g = Math.floor(140 + combined * 60); // 140-200
      const b = Math.floor(160 + combined * 40); // 160-200
      
      // Opacity also varies subtly
      const opacity = 0.04 + combined * 0.04; // 0.04-0.08
      
      return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    };

    // Draw animated grid with color variations
    const drawGrid = (width, height, t) => {
      const gridSize = 40;
      
      ctx.lineWidth = 1;

      // Horizontal lines with varying colors
      for (let y = 0; y < height; y += gridSize) {
        for (let x = 0; x < width; x += gridSize) {
          const color = getGridColor(x, y, t, width, height);
          ctx.strokeStyle = color;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(Math.min(x + gridSize, width), y);
          ctx.stroke();
        }
      }

      // Vertical lines with varying colors
      for (let x = 0; x < width; x += gridSize) {
        for (let y = 0; y < height; y += gridSize) {
          const color = getGridColor(x, y, t, width, height);
          ctx.strokeStyle = color;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x, Math.min(y + gridSize, height));
          ctx.stroke();
        }
      }

      // Add subtle glow at intersections that pulse
      for (let x = 0; x < width; x += gridSize) {
        for (let y = 0; y < height; y += gridSize) {
          const pulsePhase = Math.sin(x * 0.01 + y * 0.01 + t * 0.0002);
          const glowOpacity = 0.02 + pulsePhase * 0.02;
          
          if (glowOpacity > 0.02) {
            const gradient = ctx.createRadialGradient(x, y, 0, x, y, 8);
            gradient.addColorStop(0, `rgba(46, 196, 182, ${glowOpacity})`);
            gradient.addColorStop(1, 'rgba(46, 196, 182, 0)');
            
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
    };

    // Main animation loop
    const animate = () => {
      const width = canvas.offsetWidth;
      const height = canvas.offsetHeight;

      time += 16; // ~60fps

      ctx.clearRect(0, 0, width, height);
      drawBackground(width, height);
      drawGrid(width, height, time);

      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full"
      style={{ background: '#0A2540' }}
    />
  );
}
