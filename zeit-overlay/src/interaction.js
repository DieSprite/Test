'use strict';
/*
 * Entscheidet, ob das Overlay Mausklicks annimmt oder durchlässt.
 * Rein logisch, ohne Electron – dadurch testbar.
 *
 * Regeln:
 *  - Strg gedrückt halten          → anklickbar.
 *  - Strg + andere Taste (Strg+C …) → zählt nicht, das war ein normaler Shortcut.
 *  - Strg loslassen, Maus über dem Overlay → bleibt anklickbar, bis die Maus es verlässt.
 *  - Projektauswahl geöffnet       → bleibt anklickbar, bis sie geschlossen wird.
 *  - Umschalt-Shortcut (angeheftet) → dauerhaft anklickbar, bis erneut gedrückt.
 */
class Interaction {
  constructor(onChange) {
    this.onChange = onChange || (() => {});
    this.ctrlHeld = false;   // Strg ist unten und es kam keine andere Taste dazu
    this.hover = false;      // nach dem Loslassen über dem Overlay geblieben
    this.picker = false;     // Auswahl offen
    this.pinned = false;     // per Shortcut angeheftet
    this.last = false;
  }

  get interactive() {
    return this.pinned || this.ctrlHeld || this.hover || this.picker;
  }

  _emit() {
    const now = this.interactive;
    if (now !== this.last) {
      this.last = now;
      this.onChange(now);
    }
  }

  ctrlDown() {
    if (this.ctrlHeld) return;     // Tastenwiederholung
    this.ctrlHeld = true;
    this._emit();
  }

  otherKey() {
    if (!this.ctrlHeld) return;
    this.ctrlHeld = false;
    this._emit();
  }

  ctrlUp(cursorInside) {
    if (this.ctrlHeld && cursorInside) this.hover = true;
    this.ctrlHeld = false;
    this._emit();
  }

  cursor(inside) {
    if (!inside && this.hover) {
      this.hover = false;
      this._emit();
    }
  }

  setPicker(open) {
    this.picker = !!open;
    // Nach dem Schließen der Auswahl nicht sofort wegklappen, wenn die Maus noch drauf ist.
    if (!open) this.hover = true;
    this._emit();
  }

  togglePin() {
    this.pinned = !this.pinned;
    if (!this.pinned) this.hover = false;
    this._emit();
    return this.pinned;
  }
}

module.exports = { Interaction };
