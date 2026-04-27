import React from "react";

export function OrcaLogo({ className = "w-8 h-8", animated = true }: { className?: string; animated?: boolean }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" className={className}>
      {/* Ocean/Water base */}
      <circle 
        cx="50" cy="50" r="46" 
        fill="currentColor" opacity="0.05" 
        className={animated ? "animate-[pulse_3s_ease-in-out_infinite]" : ""} 
      />
      
      {/* Animated Orca Silhouette leaping */}
      <g className={animated ? "animate-[bounce_2.5s_ease-in-out_infinite]" : ""} style={{ transformOrigin: 'center' }}>
        {/* Main Body (S-curve leaping motion) */}
        <path 
          fill="currentColor" 
          d="M 85 45 C 80 30 65 20 45 25 C 25 30 15 45 10 55 C 15 65 30 75 55 70 C 75 65 85 55 85 45 Z" 
        />
        
        {/* Dorsal Fin */}
        <path 
          fill="currentColor" 
          d="M 45 25 C 45 10 52 5 55 5 C 52 15 54 20 50 25 Z" 
        />
        
        {/* Pectoral Fin */}
        <path 
          fill="currentColor" 
          d="M 40 68 C 35 80 25 85 20 80 C 25 75 30 70 35 68 Z" 
        />
        
        {/* Tail Fin */}
        <path 
          fill="currentColor" 
          d="M 10 55 C 5 50 0 45 5 40 C 5 48 10 52 15 52 Z" 
        />
        
        {/* Eye Patch (White oval) */}
        <ellipse 
          cx="68" cy="40" rx="7" ry="3.5" 
          fill="#ffffff" 
          transform="rotate(-15 68 40)" 
        />
        
        {/* Underbelly Patch (White) */}
        <path 
          fill="#ffffff" opacity="0.9"
          d="M 25 58 C 35 68 55 68 65 62 C 55 65 40 62 30 55 Z" 
        />
      </g>

      {/* Yin-Yang / Dynamic Accent Dot */}
      <circle 
        cx="75" cy="35" r="3" 
        fill="#0A84FF" 
        className={animated ? "animate-pulse" : ""} 
      />
    </svg>
  );
}
