import { useEffect, useRef } from 'react';

export default function AnimatedMedicalBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let time = 0;
    let heartbeatPhase = 0;

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

    // Heartbeat rhythm pattern (normalized 0-1)
    // Simulates P-QRS-T wave pattern
    const getHeartbeatMultiplier = (phase) => {
      const p = phase % 1;
      
      // P wave (small bump)
      if (p < 0.1) {
        return 1 + Math.sin(p * Math.PI / 0.1) * 0.15;
      }
      // PR segment (flat)
      else if (p < 0.15) {
        return 1;
      }
      // Q dip
      else if (p < 0.18) {
        return 1 - (p - 0.15) / 0.03 * 0.1;
      }
      // R spike (main peak)
      else if (p < 0.25) {
        const rPhase = (p - 0.18) / 0.07;
        if (rPhase < 0.5) {
          return 0.9 + rPhase * 2 * 0.8; // Up to 1.7
        } else {
          return 1.7 - (rPhase - 0.5) * 2 * 0.9; // Down to 0.8
        }
      }
      // S dip
      else if (p < 0.30) {
        return 0.8 + (p - 0.25) / 0.05 * 0.2;
      }
      // ST segment (flat)
      else if (p < 0.45) {
        return 1;
      }
      // T wave (medium bump)
      else if (p < 0.65) {
        return 1 + Math.sin((p - 0.45) * Math.PI / 0.2) * 0.25;
      }
      // Rest (flat until next beat)
      else {
        return 1;
      }
    };

    // ECG line pulses
    const ecgPulses = [];
    const maxEcgPulses = 3;

    const createEcgPulse = (width) => {
      if (ecgPulses.length < maxEcgPulses) {
        ecgPulses.push({
          x: -100,
          speed: 2.5,
          opacity: 0.8,
          width: width,
          phase: 0
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

    // Draw ECG line across screen
    const drawEcgLine = (pulse, width, height) => {
      const y = height * 0.35;
      const ecgHeight = 40;
      
      ctx.beginPath();
      
      for (let i = 0; i < 200; i++) {
        const x = pulse.x + i * 2;
        if (x < 0 || x > width) continue;
        
        const localPhase = (pulse.phase + i * 0.008) % 1;
        const ecgY = y - (getHeartbeatMultiplier(localPhase) - 1) * ecgHeight * 2;
        
        if (i === 0 || x - 2 < 0) {
          ctx.moveTo(x, ecgY);
        } else {
          ctx.lineTo(x, ecgY);
        }
      }
      
      // Glow effect
      ctx.save();
      ctx.shadowColor = colors.teal;
      ctx.shadowBlur = 15;
      ctx.strokeStyle = `rgba(46, 196, 182, ${pulse.opacity * 0.6})`;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.restore();
      
      // Core line
      ctx.strokeStyle = `rgba(46, 196, 182, ${pulse.opacity})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    };

    // Draw subtle medical grid with heartbeat pulse
    const drawGrid = (width, height, heartbeat) => {
      const gridOpacity = 0.03 + (heartbeat - 1) * 0.02;
      ctx.strokeStyle = `rgba(46, 196, 182, ${gridOpacity})`;
      ctx.lineWidth = 1;

      const gridSize = 50;

      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
    };

    // Floating particles
    const particles = [];
    const maxParticles = 20;

    const createParticle = (width, height) => {
      if (particles.length < maxParticles) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          size: 1 + Math.random() * 2,
          opacity: 0.1 + Math.random() * 0.2,
          speedX: (Math.random() - 0.5) * 0.2,
          speedY: (Math.random() - 0.5) * 0.2,
        });
      }
    };

    const drawParticles = (width, height, heartbeat) => {
      const pulseGlow = 0.8 + (heartbeat - 1) * 0.3;
      
      particles.forEach((p, index) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * pulseGlow, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(46, 196, 182, ${p.opacity * pulseGlow})`;
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
      
      // Heartbeat timing: ~30 BPM = 1 beat per 2 seconds
      heartbeatPhase += 0.008; // Increment phase (half speed for 30 BPM)
      const heartbeat = getHeartbeatMultiplier(heartbeatPhase);

      ctx.clearRect(0, 0, width, height);
      drawBackground(width, height);
      drawGrid(width, height, heartbeat);

      // Draw particles
      drawParticles(width, height, heartbeat);

      // Draw ECG pulses
      ecgPulses.forEach((pulse, index) => {
        drawEcgLine(pulse, width, height);
        pulse.x += pulse.speed;
        pulse.phase += 0.012;
        
        if (pulse.x > width + 400) {
          ecgPulses.splice(index, 1);
        }
      });

      // Create new elements
      if (Math.random() < 0.03) createParticle(width, height);
      if (Math.random() < 0.005) createEcgPulse(width);

      animationFrameId = requestAnimationFrame(animate);
    };

    // Initialize
    createEcgPulse(canvas.offsetWidth);

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
