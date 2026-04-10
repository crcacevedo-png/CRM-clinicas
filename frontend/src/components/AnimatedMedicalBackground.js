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

    // Color palette - Medical grade
    const colors = {
      deepNavy: '#0A2540',
      darkBlue: '#0F2A44',
      midBlue: '#133B5C',
      teal: '#2EC4B6',
      tealDim: '#1A7A70',
    };

    // Wave layers - more defined waves
    const waves = [
      { 
        amplitude: 80, 
        frequency: 0.002, 
        speed: 0.0002, 
        yOffset: 0.85, 
        colorStart: 'rgba(15, 42, 68, 0.95)',
        colorEnd: 'rgba(15, 42, 68, 0.98)',
        glowColor: 'rgba(46, 196, 182, 0.4)',
        glowWidth: 3
      },
      { 
        amplitude: 60, 
        frequency: 0.0025, 
        speed: 0.00025, 
        yOffset: 0.72, 
        colorStart: 'rgba(19, 59, 92, 0.85)',
        colorEnd: 'rgba(19, 59, 92, 0.9)',
        glowColor: 'rgba(46, 196, 182, 0.35)',
        glowWidth: 2.5
      },
      { 
        amplitude: 45, 
        frequency: 0.003, 
        speed: 0.0003, 
        yOffset: 0.58, 
        colorStart: 'rgba(26, 73, 113, 0.7)',
        colorEnd: 'rgba(26, 73, 113, 0.75)',
        glowColor: 'rgba(46, 196, 182, 0.3)',
        glowWidth: 2
      },
      { 
        amplitude: 30, 
        frequency: 0.0035, 
        speed: 0.00035, 
        yOffset: 0.45, 
        colorStart: 'rgba(31, 90, 135, 0.5)',
        colorEnd: 'rgba(31, 90, 135, 0.55)',
        glowColor: 'rgba(46, 196, 182, 0.2)',
        glowWidth: 1.5
      },
    ];

    // Light pulses
    const pulses = [];
    const maxPulses = 12;

    const createPulse = () => {
      if (pulses.length < maxPulses) {
        pulses.push({
          x: Math.random() < 0.5 ? -30 : canvas.offsetWidth + 30,
          waveIndex: Math.floor(Math.random() * waves.length),
          speed: (Math.random() < 0.5 ? 1 : -1) * (0.4 + Math.random() * 0.4),
          size: 2 + Math.random() * 3,
          opacity: 0.5 + Math.random() * 0.5,
          tail: [],
          maxTail: 15
        });
      }
    };

    // Draw gradient background
    const drawBackground = (width, height) => {
      const gradient = ctx.createRadialGradient(
        width * 0.3, height * 0.3, 0,
        width * 0.5, height * 0.5, Math.max(width, height)
      );
      gradient.addColorStop(0, '#0F2A44');
      gradient.addColorStop(0.5, '#0A2540');
      gradient.addColorStop(1, '#071A2B');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);
    };

    // Calculate wave Y with multiple harmonics
    const getWaveY = (x, wave, t, width, height) => {
      const baseY = height * wave.yOffset;
      const phase = t * wave.speed * 1000;
      const y = baseY + 
        Math.sin(x * wave.frequency + phase) * wave.amplitude +
        Math.sin(x * wave.frequency * 0.6 + phase * 0.8) * (wave.amplitude * 0.4) +
        Math.sin(x * wave.frequency * 1.5 + phase * 1.2) * (wave.amplitude * 0.15);
      return y;
    };

    // Draw wave with volumetric depth
    const drawWave = (wave, t, width, height) => {
      // Main wave fill
      ctx.beginPath();
      ctx.moveTo(0, height);

      const points = [];
      for (let x = 0; x <= width; x += 3) {
        const y = getWaveY(x, wave, t, width, height);
        points.push({ x, y });
        ctx.lineTo(x, y);
      }

      ctx.lineTo(width, height);
      ctx.closePath();

      // Gradient fill
      const gradient = ctx.createLinearGradient(0, height * wave.yOffset - wave.amplitude, 0, height);
      gradient.addColorStop(0, wave.colorStart);
      gradient.addColorStop(1, wave.colorEnd);
      ctx.fillStyle = gradient;
      ctx.fill();

      // Rim light (teal glow on edge)
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        if (i === 0) {
          ctx.moveTo(points[i].x, points[i].y);
        } else {
          ctx.lineTo(points[i].x, points[i].y);
        }
      }

      // Glow effect with blur
      ctx.save();
      ctx.shadowColor = wave.glowColor;
      ctx.shadowBlur = 12;
      ctx.strokeStyle = wave.glowColor;
      ctx.lineWidth = wave.glowWidth;
      ctx.stroke();
      ctx.restore();

      // Sharp rim line
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        if (i === 0) {
          ctx.moveTo(points[i].x, points[i].y);
        } else {
          ctx.lineTo(points[i].x, points[i].y);
        }
      }
      ctx.strokeStyle = `rgba(46, 196, 182, ${wave.glowWidth * 0.15})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    };

    // Draw traveling light pulses
    const drawPulses = (t, width, height) => {
      pulses.forEach((pulse, index) => {
        const wave = waves[pulse.waveIndex];
        const y = getWaveY(pulse.x, wave, t, width, height);

        // Add to tail
        pulse.tail.unshift({ x: pulse.x, y });
        if (pulse.tail.length > pulse.maxTail) {
          pulse.tail.pop();
        }

        // Draw tail
        if (pulse.tail.length > 1) {
          ctx.beginPath();
          ctx.moveTo(pulse.tail[0].x, pulse.tail[0].y);
          
          for (let i = 1; i < pulse.tail.length; i++) {
            ctx.lineTo(pulse.tail[i].x, pulse.tail[i].y);
          }
          
          const tailGradient = ctx.createLinearGradient(
            pulse.tail[0].x, pulse.tail[0].y,
            pulse.tail[pulse.tail.length - 1].x, pulse.tail[pulse.tail.length - 1].y
          );
          tailGradient.addColorStop(0, `rgba(46, 196, 182, ${pulse.opacity * 0.6})`);
          tailGradient.addColorStop(1, 'rgba(46, 196, 182, 0)');
          
          ctx.strokeStyle = tailGradient;
          ctx.lineWidth = pulse.size;
          ctx.lineCap = 'round';
          ctx.stroke();
        }

        // Draw pulse head with glow
        ctx.save();
        ctx.shadowColor = colors.teal;
        ctx.shadowBlur = 15;
        
        const headGradient = ctx.createRadialGradient(pulse.x, y, 0, pulse.x, y, pulse.size * 3);
        headGradient.addColorStop(0, `rgba(46, 196, 182, ${pulse.opacity})`);
        headGradient.addColorStop(0.5, `rgba(46, 196, 182, ${pulse.opacity * 0.4})`);
        headGradient.addColorStop(1, 'rgba(46, 196, 182, 0)');

        ctx.beginPath();
        ctx.arc(pulse.x, y, pulse.size * 3, 0, Math.PI * 2);
        ctx.fillStyle = headGradient;
        ctx.fill();

        // Core
        ctx.beginPath();
        ctx.arc(pulse.x, y, pulse.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(46, 196, 182, ${pulse.opacity})`;
        ctx.fill();
        
        ctx.restore();

        // Update position
        pulse.x += pulse.speed;

        // Remove if off screen
        if (pulse.x < -50 || pulse.x > width + 50) {
          pulses.splice(index, 1);
        }
      });
    };

    // Draw subtle medical grid
    const drawGrid = (width, height) => {
      ctx.strokeStyle = 'rgba(46, 196, 182, 0.04)';
      ctx.lineWidth = 1;

      const gridSize = 50;

      // Horizontal lines
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Vertical lines
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
    };

    // Draw subtle "data flow" particles
    const particles = [];
    const maxParticles = 30;

    const createParticle = () => {
      if (particles.length < maxParticles) {
        particles.push({
          x: Math.random() * canvas.offsetWidth,
          y: Math.random() * canvas.offsetHeight,
          size: 1 + Math.random() * 1.5,
          opacity: 0.1 + Math.random() * 0.2,
          speedX: (Math.random() - 0.5) * 0.3,
          speedY: (Math.random() - 0.5) * 0.3,
        });
      }
    };

    const drawParticles = (width, height) => {
      particles.forEach((p, index) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(46, 196, 182, ${p.opacity})`;
        ctx.fill();

        p.x += p.speedX;
        p.y += p.speedY;

        if (p.x < 0 || p.x > width || p.y < 0 || p.y > height) {
          particles.splice(index, 1);
        }
      });
    };

    // Main animation loop
    const animate = () => {
      const width = canvas.offsetWidth;
      const height = canvas.offsetHeight;

      time += 16;

      // Clear and draw background
      ctx.clearRect(0, 0, width, height);
      drawBackground(width, height);

      // Draw grid
      drawGrid(width, height);

      // Draw particles
      drawParticles(width, height);

      // Draw waves (back to front)
      for (let i = waves.length - 1; i >= 0; i--) {
        drawWave(waves[i], time, width, height);
      }

      // Draw pulses on top
      drawPulses(time, width, height);

      // Create new pulses and particles
      if (Math.random() < 0.015) createPulse();
      if (Math.random() < 0.05) createParticle();

      animationFrameId = requestAnimationFrame(animate);
    };

    // Initialize some pulses
    for (let i = 0; i < 4; i++) {
      createPulse();
    }

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
