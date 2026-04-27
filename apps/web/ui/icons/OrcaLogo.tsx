import React from "react";

export function OrcaLogo({ className = "w-8 h-8", animated = true }: { className?: string; animated?: boolean }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" className={className}>
      {animated && (
        <style>
          {`
            @keyframes slashCut {
              0% { stroke-dashoffset: 160; opacity: 0; }
              10% { opacity: 1; }
              25% { stroke-dashoffset: 0; opacity: 1; }
              35% { stroke-dashoffset: -160; opacity: 0; }
              100% { stroke-dashoffset: -160; opacity: 0; }
            }
            @keyframes revealOrca {
              0%, 15% { opacity: 0; transform: scale(0.9) translate(-10px, 10px); filter: blur(4px); }
              30%, 85% { opacity: 1; transform: scale(1) translate(0, 0); filter: blur(0px); }
              95%, 100% { opacity: 0; transform: scale(1.05) translate(5px, -5px); filter: blur(2px); }
            }
            .slash-line {
              stroke-dasharray: 160;
              stroke-dashoffset: 160;
              animation: slashCut 4s cubic-bezier(0.19, 1, 0.22, 1) infinite;
            }
            .orca-body {
              animation: revealOrca 4s cubic-bezier(0.19, 1, 0.22, 1) infinite;
              transform-origin: center;
            }
          `}
        </style>
      )}
      
      <g className={animated ? "orca-body" : ""}>
        {/* Premium Minimalist Orca Silhouette - Negative Space Style */}
        <path 
          d="M 85 45 
             C 80 30 65 20 45 25 
             C 25 30 10 40 5 50 
             C 10 60 25 75 50 75 
             C 70 75 80 65 85 45 Z" 
          fill="currentColor" 
        />
        {/* Dorsal Fin */}
        <path d="M 45 25 C 45 5 55 0 60 0 C 55 10 60 20 55 28 Z" fill="currentColor" />
        {/* Pectoral Fin */}
        <path d="M 40 68 C 30 85 20 90 15 85 C 20 80 25 75 35 65 Z" fill="currentColor" />
        
        {/* Distinctive Eye Patch (Cut out effect using background color) */}
        <path d="M 60 38 C 65 35 75 38 75 42 C 75 46 65 44 60 42 Z" fill="#000000" />
        
        {/* Belly Accent (Cut out effect) */}
        <path d="M 25 58 C 35 68 55 68 65 62 C 55 65 40 62 30 55 Z" fill="#000000" opacity="0.9" />
      </g>
      
      {/* High-speed Anime Slash Effect */}
      {animated && (
        <line 
          x1="5" y1="95" x2="95" y2="5" 
          stroke="#0A84FF" strokeWidth="5" strokeLinecap="round" 
          className="slash-line" 
        />
      )}
    </svg>
  );
}
