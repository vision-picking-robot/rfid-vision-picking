// The reply is spoken while the microphone keeps listening (barge-in): as soon as the user starts
// talking, the announcement stops and the new words are processed. Recognised text that is just our
// own announcement coming back through the speakers is ignored (echo), unless it is a short command.
const ECHO_MIN = 3;  // shorter utterances ("네", "멈춰", "정지") are never treated as echo
const ECHO_TAIL_MS = 2500;  // the recogniser may finish an echo shortly after the announcement ended
const POLL_MS = 1000;  // server announcements ("피킹 로봇 가동" progress) are picked up this often

function squash(text) {
  return String(text || "").toLowerCase().replace(/[^가-힣a-z0-9]/g, "");
}

export function isEcho(heard, spoken) {
  const h = squash(heard), s = squash(spoken);
  return h.length >= ECHO_MIN && s.length > 0 && (s.includes(h) || h.includes(s));
}

export class BrowserVoice {
  constructor(update, scope = window) {
    this.scope = scope; this.update = update; this.generation = 0; this.active = false;
    this.speech = null;  // {text, utterance, status} while an announcement is playing
    this.lastSpoken = null;  // {text, until}: echo window after an announcement ends
    this.announceSeq = null;
    this.keepAlive = false;  // server runs the robot ("피킹 로봇 가동"): never end on silence
  }
  echoOf(text) {
    const now = this.scope.performance?.now?.() ?? Date.now();
    const ref = this.speech?.text || (this.lastSpoken && now < this.lastSpoken.until ? this.lastSpoken.text : null);
    return ref !== null && isEcho(text, ref);
  }
  follow(status) {
    // Server state: keep listening during a robot run, speak a new announcement once.
    this.keepAlive = Boolean(status?.auto?.active);
    if (status?.announce_seq === undefined || status.announce_seq === this.announceSeq) return false;
    this.announceSeq = status.announce_seq;
    if (!status.announcement) return false;
    this.speak(status.announcement, status);
    return true;
  }
  async poll(generation) {
    if (!this.active || generation !== this.generation) return;
    try {
      const response = await this.scope.fetch('/api/voice/status', {cache: 'no-store'});
      const status = await response.json();
      if (!this.active || generation !== this.generation) return;
      const spoke = this.follow(status);
      const key = JSON.stringify([status.auto, status.announcement]);
      if (!spoke && key !== this.lastKey && !this.speech) this.update(status);
      this.lastKey = key;
    } catch { /* server restarting: keep the last state */ }
  }
  async api(action, body) {
    const response = await this.scope.fetch('/api/voice/' + action, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: body ? JSON.stringify(body) : undefined, cache: 'no-store'
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '음성 서버 연결을 확인하세요.');
    return data;
  }
  speak(text, status) {
    const synth = this.scope.speechSynthesis, Utterance = this.scope.SpeechSynthesisUtterance;
    if (!text || !synth || !Utterance) return;
    const utterance = new Utterance(text);
    utterance.lang = 'ko-KR';
    const speech = this.speech = {text, utterance, status};
    utterance.onend = utterance.onerror = () => {
      if (this.speech !== speech) return;
      this.speech = null;
      this.lastSpoken = {text, until: (this.scope.performance?.now?.() ?? Date.now()) + ECHO_TAIL_MS};
      if (this.active) this.update({...status, state: 'listening'});
    };
    this.update({...status, state: 'speaking', barge_in: true});
    synth.speak(utterance);
  }
  bargeIn() {
    const speech = this.speech;
    if (!speech) return;
    this.speech = null;
    this.scope.speechSynthesis?.cancel();
    this.update({...speech.status, state: 'listening'});
  }
  async start() {
    const Recognition = this.scope.SpeechRecognition || this.scope.webkitSpeechRecognition;
    if (!Recognition) throw new Error('이 브라우저는 음성 인식을 지원하지 않습니다. Chrome 또는 Edge에서 실행하세요.');
    if (!this.scope.isSecureContext) throw new Error('마이크 사용에는 localhost 또는 HTTPS 접속이 필요합니다.');
    if (this.active || this.starting) return;
    this.starting = true;
    const generation = ++this.generation;
    let status;
    try { status = await this.api('wake'); } finally { this.starting = false; }
    if (generation !== this.generation) { await this.api('stop'); return; }
    this.session = status.session; this.turn = status.turn; this.active = true;
    this.keepAlive = Boolean(status?.auto?.active);
    this.announceSeq = status.announce_seq ?? 0;  // baseline: an older announcement is not replayed
    this.update(status);
    clearInterval(this.pollTimer);
    this.pollTimer = setInterval(() => void this.poll(generation), POLL_MS);
    const live = () => this.active && generation === this.generation;
    const listen = () => {
      if (!live()) return;
      const recognition = this.recognition = new Recognition();
      recognition.lang = 'ko-KR'; recognition.interimResults = true;
      recognition.continuous = false; recognition.maxAlternatives = 1;
      let handled = false;
      const again = () => { handled = true; try { recognition.stop(); } catch { /* already ended */ } listen(); };
      recognition.onresult = async event => {
        if (handled || !live()) return;
        const result = event.results[event.resultIndex];
        const text = result?.[0]?.transcript || '';
        if (this.echoOf(text)) {  // our own announcement coming back through the speakers
          if (result?.isFinal) again();
          return;
        }
        if (this.speech && squash(text)) this.bargeIn();  // the user is talking: stop the announcement now
        if (!result?.isFinal || !squash(text)) return;
        handled = true; recognition.stop();
        try {
          const next = await this.api('transcript', {session: this.session, turn: this.turn, text});
          if (!live()) return;
          this.turn = next.turn; this.update(next);
          if (!next.can_stop) { this.active = false; clearInterval(this.pollTimer); return; }
          if (!this.follow(next)) this.speak(next.reply, next);  // a new announcement replaces the reply
          listen();  // keep listening while the reply plays
        } catch (error) { await this.fail(error, generation); }
      };
      recognition.onerror = event => {
        if (event.error === 'aborted' || generation !== this.generation) return;
        // Silence while an announcement plays (or a dropped echo) is not the end of the conversation.
        if ((this.speech || this.keepAlive) && event.error === 'no-speech') { again(); return; }
        handled = true; void this.fail(new Error('마이크 입력 오류: ' + event.error), generation);
      };
      recognition.onend = () => {
        if (handled || !live()) return;
        if (this.speech || this.keepAlive) { listen(); return; }
        void this.stop().catch(error => this.update({state:'error',can_stop:false,error:error.message}));
      };
      try { recognition.start(); } catch (error) { void this.fail(error, generation); }
    };
    listen();
  }
  async fail(error, generation) {
    if (generation !== this.generation) return;
    await this.stop().catch(() => {});
    this.update({state: 'error', can_stop: false, error: error.message});
  }
  async stop() {
    this.active = false; ++this.generation;
    this.speech = null; this.keepAlive = false;
    clearInterval(this.pollTimer);
    this.recognition?.abort(); this.scope.speechSynthesis?.cancel();
    const status = await this.api('stop'); this.update(status); return status;
  }
}
