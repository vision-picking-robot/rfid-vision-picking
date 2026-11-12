// Double-clap wake word for the dashboard voice assistant.
// The microphone level is sampled every ~10 ms; a clap is a short, loud spike well above the room's
// background level. Two claps 0.18-0.8 s apart wake the assistant.

export const CLAP = {
  minPeak: 0.3,        // absolute peak (0..1) a clap must reach
  overFloor: 4,        // and this many times the background level
  refractoryMs: 120,   // one clap rings for a while: ignore spikes this soon after it
  minGapMs: 180,       // second clap at least this long after the first …
  maxGapMs: 800,       // … and at most this long
  floorAlpha: 0.02,    // background level follows quiet frames slowly
};

export class ClapDetector {
  constructor(options = {}) {
    this.o = { ...CLAP, ...options };
    this.floor = 0.02;
    this.lastClap = -Infinity;
    this.firstClap = null;
  }
  // peak: max |sample| of the latest frame; now: ms. Returns true on the second clap of a pair.
  feed(peak, now) {
    const o = this.o;
    const spike = peak >= o.minPeak && peak >= this.floor * o.overFloor;
    if (!spike) {
      if (now - this.lastClap > o.refractoryMs) this.floor += (peak - this.floor) * o.floorAlpha;
      if (this.firstClap !== null && now - this.firstClap > o.maxGapMs) this.firstClap = null;
      return false;
    }
    if (now - this.lastClap < o.refractoryMs) return false;  // still the same clap ringing
    this.lastClap = now;
    if (this.firstClap !== null) {
      const gap = now - this.firstClap;
      if (gap >= o.minGapMs && gap <= o.maxGapMs) {
        this.firstClap = null;
        return true;
      }
    }
    this.firstClap = now;
    return false;
  }
  reset() { this.firstClap = null; this.lastClap = -Infinity; }
}

export class ClapWake {
  constructor(onDoubleClap, scope = window) {
    this.onDoubleClap = onDoubleClap;
    this.scope = scope;
    this.detector = new ClapDetector();
    this.listening = false;
  }
  async arm() {
    if (!this.stream) {
      if (!this.scope.isSecureContext) throw new Error("마이크 사용에는 localhost 또는 HTTPS 접속이 필요합니다.");
      // Raw level: the browser's noise suppression and gain control would flatten claps.
      this.stream = await this.scope.navigator.mediaDevices.getUserMedia(
        { audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      const Context = this.scope.AudioContext || this.scope.webkitAudioContext;
      this.context = new Context();
      const source = this.context.createMediaStreamSource(this.stream);
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 512;
      source.connect(this.analyser);
      this.buffer = new Float32Array(this.analyser.fftSize);
    }
    await this.context.resume?.();
    this.detector.reset();
    this.listening = true;
    clearInterval(this.timer);
    this.timer = setInterval(() => this.sample(), 10);
  }
  sample() {
    if (!this.listening) return;
    this.analyser.getFloatTimeDomainData(this.buffer);
    let peak = 0;
    for (const v of this.buffer) peak = Math.max(peak, Math.abs(v));
    if (this.detector.feed(peak, this.scope.performance.now())) {
      this.pause();
      this.onDoubleClap();
    }
  }
  pause() { this.listening = false; clearInterval(this.timer); }
  disarm() {
    this.pause();
    this.stream?.getTracks().forEach(track => track.stop());
    this.context?.close?.();
    this.stream = this.context = this.analyser = null;
  }
}
