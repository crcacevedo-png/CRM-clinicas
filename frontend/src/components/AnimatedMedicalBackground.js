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

    // Wave layers with heartbeat influence
    const waves = [
      { 
        amplitude: 80, 
        frequency: 0.002, 
        speed: 0.0002, 
        yOffset: 0.85, 
        colorStart: 'rgba(15, 42, 68, 0.95)',
        colorEnd: 'rgba(15, 42, 68, 0.98)',
        glowColor: 'rgba(46, 196, 182, 0.5)',
        glowWidth: 3,
        heartbeatInfluence: 0.3
      },
      { 
        amplitude: 60, 
        frequency: 0.0025, 
        speed: 0.00025, 
        yOffset: 0.72, 
        colorStart: 'rgba(19, 59, 92, 0.85)',
        colorEnd: 'rgba(19, 59, 92, 0.9)',
        glowColor: 'rgba(46, 196, 182, 0.4)',
        glowWidth: 2.5,
        heartbeatInfluence: 0.4
      },
      { 
        amplitude: 45, 
        frequency: 0.003, 
        speed: 0.0003, 
        yOffset: 0.58, 
        colorStart: 'rgba(26, 73, 113, 0.7)',
        colorEnd: 'rgba(26, 73, 113, 0.75)',
        glowColor: 'rgba(46, 196, 182, 0.35)',
        glowWidth: 2,
        heartbeatInfluence: 0.5
      },
      { 
        amplitude: 30, 
        frequency: 0.0035, 
        speed: 0.00035, 
        yOffset: 0.45, 
        colorStart: 'rgba(31, 90, 135, 0.5)',
        colorEnd: 'rgba(31, 90, 135, 0.55)',
        glowColor: 'rgba(46, 196, 182, 0.25)',
        glowWidth: 1.5,
        heartbeatInfluence: 0.6
      },
    ];

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

    // Light pulses
    const pulses = [];
    const maxPulses = 10;

    const createPulse = (width) => {
      if (pulses.length < maxPulses) {
        pulses.push({
          x: -30,
          waveIndex: Math.floor(Math.random() * waves.length),
          speed: 0.5 + Math.random() * 0.3,
          size: 2 + Math.random() * 2,
          opacity: 0.4 + Math.random() * 0.4,
          tail: [],
          maxTail: 12
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

    // Calculate wave Y with heartbeat rhythm
    const getWaveY = (x, wave, t, width, height, heartbeat) => {
      const baseY = height * wave.yOffset;
      const phase = t * wave.speed * 1000;
      
      // Apply heartbeat multiplier to amplitude
      const hbMultiplier = 1 + (heartbeat - 1) * wave.heartbeatInfluence;
      const adjustedAmplitude = wave.amplitude * hbMultiplier;
      
      const y = baseY + 
        Math.sin(x * wave.frequency + phase) * adjustedAmplitude +
        Math.sin(x * wave.frequency * 0.6 + phase * 0.8) * (adjustedAmplitude * 0.4) +
        Math.sin(x * wave.frequency * 1.5 + phase * 1.2) * (adjustedAmplitude * 0.15);
      return y;
    };

    // Draw wave with volumetric depth
    const drawWave = (wave, t, width, height, heartbeat) => {
      ctx.beginPath();
      ctx.moveTo(0, height);

      const points = [];
      for (let x = 0; x <= width; x += 3) {
        const y = getWaveY(x, wave, t, width, height, heartbeat);
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

      // Rim light with heartbeat glow intensity
      const glowIntensity = 0.7 + (heartbeat - 1) * 0.5;
      
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        if (i === 0) {
          ctx.moveTo(points[i].x, points[i].y);
        } else {
          ctx.lineTo(points[i].x, points[i].y);
        }
      }

      ctx.save();
      ctx.shadowColor = wave.glowColor;
      ctx.shadowBlur = 12 * glowIntensity;
      ctx.strokeStyle = wave.glowColor.replace('0.', `${0.3 * glowIntensity}.`);
      ctx.lineWidth = wave.glowWidth * glowIntensity;
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
      ctx.strokeStyle = `rgba(46, 196, 182, ${0.15 * glowIntensity})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    };

    // Draw ECG line across screen
    const drawEcgLine = (pulse, width, height, heartbeat) => {
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

    // Draw traveling light pulses
    const drawPulses = (t, width, height, heartbeat) => {
      pulses.forEach((pulse, index) => {
        const wave = waves[pulse.waveIndex];
        const y = getWaveY(pulse.x, wave, t, width, height, heartbeat);

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
          tailGradient.addColorStop(0, `rgba(46, 196, 182, ${pulse.opacity * 0.5})`);
          tailGradient.addColorStop(1, 'rgba(46, 196, 182, 0)');
          
          ctx.strokeStyle = tailGradient;
          ctx.lineWidth = pulse.size;
          ctx.lineCap = 'round';
          ctx.stroke();
        }

        // Pulse head with heartbeat-synced glow
        const pulseGlow = 0.8 + (heartbeat - 1) * 0.4;
        
        ctx.save();
        ctx.shadowColor = colors.teal;
        ctx.shadowBlur = 15 * pulseGlow;
        
        const headGradient = ctx.createRadialGradient(pulse.x, y, 0, pulse.x, y, pulse.size * 3);
        headGradient.addColorStop(0, `rgba(46, 196, 182, ${pulse.opacity * pulseGlow})`);
        headGradient.addColorStop(0.5, `rgba(46, 196, 182, ${pulse.opacity * 0.3 * pulseGlow})`);
        headGradient.addColorStop(1, 'rgba(46, 196, 182, 0)');

        ctx.beginPath();
        ctx.arc(pulse.x, y, pulse.size * 3, 0, Math.PI * 2);
        ctx.fillStyle = headGradient;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(pulse.x, y, pulse.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(46, 196, 182, ${pulse.opacity * pulseGlow})`;
        ctx.fill();
        
        ctx.restore();

        // Update position with slight heartbeat influence on speed
        pulse.x += pulse.speed * (0.8 + heartbeat * 0.2);

        if (pulse.x > width + 50) {
          pulses.splice(index, 1);
        }
      });
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

      // Draw waves with heartbeat
      for (let i = waves.length - 1; i >= 0; i--) {
        drawWave(waves[i], time, width, height, heartbeat);
      }

      // Draw ECG pulses
      ecgPulses.forEach((pulse, index) => {
        drawEcgLine(pulse, width, height, heartbeat);
        pulse.x += pulse.speed;
        pulse.phase += 0.012;
        
        if (pulse.x > width + 400) {
          ecgPulses.splice(index, 1);
        }
      });

      // Draw light pulses
      drawPulses(time, width, height, heartbeat);

      // Create new elements
      if (Math.random() < 0.02) createPulse(width);
      if (Math.random() < 0.005) createEcgPulse(width);

      animationFrameId = requestAnimationFrame(animate);
    };

    // Initialize
    for (let i = 0; i < 3; i++) {
      createPulse(canvas.offsetWidth);
    }
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
