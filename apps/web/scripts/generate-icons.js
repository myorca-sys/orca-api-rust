const fs = require('fs');
const sharp = require('sharp');
const path = require('path');

const cleanOrcaFile = path.join(__dirname, '../public/clean-orca.txt');
const lines = fs.readFileSync(cleanOrcaFile, 'utf8').split('\n').filter(Boolean);
const pathMain = lines[0] || "";
const pathAccent = lines[1] || "";

// The viewBox of the SVG is 940.5 x 940.5
// We will pad it slightly to make sure it fits perfectly
const svgBuffer = Buffer.from(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -50 1040 1040">
  <rect width="100%" height="100%" fill="#000000"/>
  <path d="${pathMain}" fill="#ffffff" />
  <path d="${pathAccent}" fill="#ffffff" opacity="0.8" />
</svg>
`);

// The favicon doesn't need the black background, we can just render the transparent one
const svgTransparent = Buffer.from(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -50 1040 1040">
  <path d="${pathMain}" fill="#ffffff" />
  <path d="${pathAccent}" fill="#ffffff" opacity="0.8" />
</svg>
`);

async function generate() {
  const publicDir = path.join(__dirname, '../public');
  
  // Icon 192 (with black background for better PWA visibility)
  await sharp(svgBuffer)
    .resize(192, 192)
    .png()
    .toFile(path.join(publicDir, 'icon-192x192.png'));

  // Icon 512 (with black background)
  await sharp(svgBuffer)
    .resize(512, 512)
    .png()
    .toFile(path.join(publicDir, 'icon-512x512.png'));

  // Favicon 32x32 (transparent)
  // .ico format can just be a .png renamed for modern browsers, or we can use sharp's raw png
  await sharp(svgTransparent)
    .resize(64, 64) // double size for retina
    .png()
    .toFile(path.join(publicDir, 'favicon.ico')); // browsers accept png data in .ico
    
  console.log("Icons generated!");
}

generate().catch(console.error);
