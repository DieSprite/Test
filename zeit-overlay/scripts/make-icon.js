'use strict';
/* Erzeugt build/icon.png (256 × 256): schlichte Uhr auf Markengrün. Kein Logo. */
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const N = 256;
const px = Buffer.alloc(N * N * 4);
const GREEN = [0x06, 0x6c, 0x22];
const WHITE = [255, 255, 255];

function set(x, y, c, a) {
  const i = (y * N + x) * 4;
  const k = a;
  px[i] = Math.round(px[i] * (1 - k) + c[0] * k);
  px[i + 1] = Math.round(px[i + 1] * (1 - k) + c[1] * k);
  px[i + 2] = Math.round(px[i + 2] * (1 - k) + c[2] * k);
  px[i + 3] = 255;
}
function segDist(x, y, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(x - (ax + t * dx), y - (ay + t * dy));
}
const c = N / 2;
for (let y = 0; y < N; y++) {
  for (let x = 0; x < N; x++) {
    set(x, y, GREEN, 1);
    const px_ = x + 0.5, py = y + 0.5;
    const r = Math.hypot(px_ - c, py - c);
    const ring = 1 - Math.min(1, Math.max(0, Math.abs(r - 84) - 10));
    const hand1 = 1 - Math.min(1, Math.max(0, segDist(px_, py, c, c, c, c - 58) - 9));
    const hand2 = 1 - Math.min(1, Math.max(0, segDist(px_, py, c, c, c + 42, c + 24) - 9));
    const a = Math.max(ring, hand1, hand2);
    if (a > 0) set(x, y, WHITE, a);
  }
}
function crc32(buf) {
  let c2, crc = 0xffffffff;
  for (let n = 0; n < buf.length; n++) {
    c2 = (crc ^ buf[n]) & 0xff;
    for (let k = 0; k < 8; k++) c2 = c2 & 1 ? 0xedb88320 ^ (c2 >>> 1) : c2 >>> 1;
    crc = (crc >>> 8) ^ c2;
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}
const raw = Buffer.alloc(N * (N * 4 + 1));
for (let y = 0; y < N; y++) px.copy(raw, y * (N * 4 + 1) + 1, y * N * 4, (y + 1) * N * 4);
const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(N, 0); ihdr.writeUInt32BE(N, 4); ihdr[8] = 8; ihdr[9] = 6;
const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0)),
]);
const out = path.join(__dirname, '..', 'build', 'icon.png');
fs.writeFileSync(out, png);
console.log('geschrieben:', out);
