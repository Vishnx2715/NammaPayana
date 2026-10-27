/**
 * Namma Payana — Kannada Companion & Speech Studio (v2.0)
 * Features:
 * 1. Live Multilingual Translator to authentic spoken Kannada.
 * 2. Human-like Speech Synthesis Engine with speed tuning (0.75x, 0.9x, 1.1x) and audio visualizer.
 * 3. 42 verified daily expressions with search, scenario filters, and favorites.
 * 4. Interactive situational dialogue practice.
 */

const KannadaCompanion = {
  allPhrases: [],
  dialogues: [],
  favorites: new Set(JSON.parse(localStorage.getItem("np_kannada_favs") || "[]")),
  currentDialogueIdx: 0,
  currentStepIdx: 0,
  speechRate: 0.88,
  speechPitch: 1.02,
  isSpeaking: false,
  lastTranslatedResult: null,

  async init() {
    try {
      const res = await fetch("/api/phrases");
      const json = await res.json();
      if (json.ok) {
        this.allPhrases = json.data.phrases;
        this.dialogues = json.data.dialogues;
        this.renderPhrases(this.allPhrases);
        this.renderDialogue();
      }
    } catch (err) {
      console.error("[KannadaCompanion] Failed to load phrases:", err);
    }

    this.bindEvents();
    this.initVoiceEngine();
  },

  bindEvents() {
    const searchInput = document.getElementById("phrase-search");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => this.handleSearch(e.target.value));
    }

    const scenarioSelect = document.getElementById("scenario-filter");
    if (scenarioSelect) {
      scenarioSelect.addEventListener("change", (e) => this.handleScenario(e.target.value));
    }

    // Enter key triggers translation in translator input
    const transInput = document.getElementById("kc-translate-input");
    if (transInput) {
      transInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.translateText();
        }
      });
    }
  },

  initVoiceEngine() {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.onvoiceschanged = () => {
        this.getBestVoice();
      };
    }
  },

  getBestVoice() {
    if (!("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;

    // 1. Look for native Kannada voice
    const knVoice = voices.find(v => {
      const l = (v.lang || "").toLowerCase();
      return l.includes("kn") || l.includes("kan") || v.name.toLowerCase().includes("kannada");
    });
    if (knVoice) return knVoice;

    // 2. Look for Indian English or Indian Hindi voice (natural phonetics for Indian languages)
    const indianVoice = voices.find(v => {
      const l = (v.lang || "").toLowerCase();
      const n = (v.name || "").toLowerCase();
      return (l.includes("hi-in") || l.includes("en-in") || n.includes("india") || n.includes("heera") || n.includes("ravi") || n.includes("google हिन्दी"));
    });
    if (indianVoice) return indianVoice;

    return null;
  },

  setSpeechSpeed(speedRate, btnEl) {
    this.speechRate = parseFloat(speedRate) || 0.88;
    document.querySelectorAll(".voice-speed-pill").forEach(p => p.classList.remove("active"));
    if (btnEl) btnEl.classList.add("active");
  },

  speakText(text, onStartCb = null, onEndCb = null) {
    if (!("speechSynthesis" in window)) {
      if (typeof App !== "undefined" && App.toast) {
        App.toast("Speech synthesis is not supported on this browser.", "err");
      } else {
        alert("Speech synthesis is not supported on this browser.");
      }
      return;
    }

    window.speechSynthesis.cancel();

    // Natural sentence pauses & cadence
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "kn-IN";
    utterance.rate = this.speechRate;
    utterance.pitch = this.speechPitch;
    utterance.volume = 1.0;

    const voice = this.getBestVoice();
    if (voice) {
      utterance.voice = voice;
      // If falling back to non-Kannada voice, speak cleanly
      if (!utterance.voice.lang.includes("kn") && !utterance.voice.lang.includes("kan")) {
        utterance.lang = voice.lang;
      }
    }

    this.isSpeaking = true;
    this.setWaveAnimation(true);

    utterance.onstart = () => {
      this.isSpeaking = true;
      this.setWaveAnimation(true);
      if (onStartCb) onStartCb();
    };

    utterance.onend = () => {
      this.isSpeaking = false;
      this.setWaveAnimation(false);
      if (onEndCb) onEndCb();
    };

    utterance.onerror = () => {
      this.isSpeaking = false;
      this.setWaveAnimation(false);
      if (onEndCb) onEndCb();
    };

    window.speechSynthesis.speak(utterance);
  },

  setWaveAnimation(active) {
    const waves = document.querySelectorAll(".audio-wave-bars");
    waves.forEach(w => {
      if (active) w.classList.add("active");
      else w.classList.remove("active");
    });
  },

  // ─── Live Multilingual Translator ─────────────────────
  applyQuickPhrase(phraseText) {
    const input = document.getElementById("kc-translate-input");
    if (input) {
      input.value = phraseText;
      this.translateText();
    }
  },

  async translateText() {
    const input = document.getElementById("kc-translate-input");
    const langSelect = document.getElementById("kc-source-lang");
    const resultBox = document.getElementById("kc-translator-result");
    const transBtn = document.getElementById("kc-btn-translate");

    if (!input) return;
    const text = input.value.trim();
    if (!text) {
      if (typeof App !== "undefined" && App.toast) {
        App.toast(typeof I18n !== "undefined" ? I18n.t("kc.toast_enter_text", "Please type a word or sentence to translate.") : "Please type a word or sentence to translate.", "");
      }
      return;
    }

    const sourceLang = langSelect ? langSelect.value : (typeof I18n !== "undefined" ? I18n.currentLang : "en");

    // UI Loading state
    if (transBtn) {
      transBtn.disabled = true;
      transBtn.innerHTML = `⟳ <span data-i18n="kc.translating">Translating…</span>`;
    }

    try {
      const res = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source_lang: sourceLang })
      });
      const json = await res.json();

      if (json.ok && json.data) {
        this.lastTranslatedResult = json.data;
        this.renderTranslationResult(json.data);
      } else {
        if (resultBox) {
          resultBox.innerHTML = `
            <div style="padding:16px;background:rgba(183,121,31,0.08);border-radius:10px;color:var(--earth-red);font-size:14px;">
              ${escapeHtml(json.error?.message || "Could not complete translation.")}
            </div>`;
        }
      }
    } catch (err) {
      console.error("[KannadaCompanion] translate error:", err);
      if (resultBox) {
        resultBox.innerHTML = `
          <div style="padding:16px;background:rgba(183,121,31,0.08);border-radius:10px;color:var(--earth-red);font-size:14px;">
            Connection error. Please try again.
          </div>`;
      }
    } finally {
      if (transBtn) {
        transBtn.disabled = false;
        transBtn.innerHTML = `✨ <span data-i18n="kc.btn_translate">Translate to Kannada</span>`;
      }
    }
  },

  renderTranslationResult(data) {
    const box = document.getElementById("kc-translator-result");
    if (!box) return;

    const safeKn = JSON.stringify(data.kannada || "");
    const verifiedBadge = data.verified
      ? `<span class="badge badge-sourced" style="background:#2F7D4F;color:#fff;">✓ Verified Authentic</span>`
      : `<span class="badge badge-approximate">⚡ Contextual</span>`;

    box.style.display = "block";
    box.innerHTML = `
      <div class="trans-result-card" style="position:relative;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;">
          <div>
            <span style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--charcoal-muted);">KANNADA EXPRESSION</span>
            <div class="trans-result-kn">${escapeHtml(data.kannada)}</div>
          </div>
          <div style="display:flex;gap:6px;align-items:center;">
            ${verifiedBadge}
            <button class="icon-tool-btn" onclick="KannadaCompanion.copyToClipboard(${safeKn}, this)" title="Copy Kannada text">
              📋
            </button>
          </div>
        </div>

        ${data.meaning ? `
          <div class="trans-result-meaning">
            <span class="trans-result-meaning-label">📖 Meaning:</span>
            <span class="trans-result-meaning-text">"${escapeHtml(data.meaning)}"</span>
          </div>
        ` : ""}

        <div class="trans-result-meta">
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:12px;color:var(--forest);font-weight:600;">🗣️ Spoken:</span>
            <strong style="color:var(--forest);font-size:15px;letter-spacing:0.3px;">${escapeHtml(data.transliteration)}</strong>
          </div>
          ${data.syllables ? `
            <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
              <span style="font-size:11px;color:var(--charcoal-muted);">Pronounce:</span>
              <span class="syllable-pill">${escapeHtml(data.syllables)}</span>
            </div>
          ` : ""}
        </div>

        ${data.context ? `
          <div class="trans-result-tip">
            <strong>💡 Context &amp; Tone:</strong> ${data.tone ? `<span style="font-weight:700;color:var(--earth-red);">${escapeHtml(data.tone)}</span> &bull; ` : ""}${escapeHtml(data.context)}
          </div>
        ` : ""}

        <!-- Speech controls bar -->
        <div class="trans-audio-controls">
          <button class="btn-primary" style="padding:10px 22px;display:inline-flex;align-items:center;gap:8px;font-size:14px;" onclick="KannadaCompanion.speakText(${JSON.stringify(data.kannada)})">
            🔊 Listen (Read Out)
          </button>
          <button class="btn-secondary" style="padding:10px 18px;font-size:13px;" onclick="KannadaCompanion.speakText(${JSON.stringify(data.kannada)})" title="Repeat speech">
            🔁 Repeat
          </button>

          <!-- Animated Audio Waveform -->
          <div class="audio-wave-bars" title="Speaking audio waveform">
            <span class="bar"></span>
            <span class="bar"></span>
            <span class="bar"></span>
            <span class="bar"></span>
            <span class="bar"></span>
          </div>

          <div class="speed-control-group">
            <span style="font-size:12px;color:var(--charcoal-muted);margin-right:4px;">Speed:</span>
            <button class="voice-speed-pill" onclick="KannadaCompanion.setSpeechSpeed(0.75, this)" title="Slow pace for learners">🐢 0.75x</button>
            <button class="voice-speed-pill active" onclick="KannadaCompanion.setSpeechSpeed(0.88, this)" title="Natural human conversation">👤 0.9x</button>
            <button class="voice-speed-pill" onclick="KannadaCompanion.setSpeechSpeed(1.1, this)" title="Native fluent pace">🐇 1.1x</button>
          </div>
        </div>
      </div>
    `;
  },

  copyToClipboard(text, btnEl) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        if (typeof App !== "undefined" && App.toast) {
          App.toast("Copied Kannada text! 📋", "ok");
        }
        if (btnEl) {
          const original = btnEl.innerHTML;
          btnEl.innerHTML = "✓";
          setTimeout(() => { btnEl.innerHTML = original; }, 1500);
        }
      });
    }
  },

  clearTranslator() {
    const input = document.getElementById("kc-translate-input");
    const resultBox = document.getElementById("kc-translator-result");
    if (input) input.value = "";
    if (resultBox) {
      resultBox.style.display = "none";
      resultBox.innerHTML = "";
    }
    this.lastTranslatedResult = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  },

  // ─── Filter & Search Phrases ──────────────────────────
  handleSearch(query) {
    const q = query.toLowerCase().trim();
    const filtered = this.allPhrases.filter(p =>
      p.english.toLowerCase().includes(q) ||
      p.transliteration.toLowerCase().includes(q) ||
      p.kannada.includes(q)
    );
    this.renderPhrases(filtered);
  },

  handleScenario(scenario) {
    if (!scenario || scenario === "all") {
      this.renderPhrases(this.allPhrases);
    } else {
      const filtered = this.allPhrases.filter(p => p.scenario.toLowerCase() === scenario.toLowerCase());
      this.renderPhrases(filtered);
    }
  },

  toggleFavorite(phraseId) {
    if (this.favorites.has(phraseId)) {
      this.favorites.delete(phraseId);
    } else {
      this.favorites.add(phraseId);
    }
    localStorage.setItem("np_kannada_favs", JSON.stringify([...this.favorites]));
    this.renderPhrases(this.allPhrases);
  },

  renderPhrases(phrases) {
    const grid = document.getElementById("phrases-grid");
    if (!grid) return;

    if (phrases.length === 0) {
      grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--charcoal-muted);">No matching Kannada phrases found.</div>`;
      return;
    }

    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';
    const pronounceLabel = typeof I18n !== 'undefined' ? I18n.t('kc.btn_pronounce', '🔊 Pronounce') : '🔊 Pronounce';
    const reviewLabel = lang === 'kn' ? 'ಪರಿಶೀಲನೆ ಅಗತ್ಯವಿದೆ' : (lang === 'hi' ? 'समीक्षा आवश्यक' : (lang === 'te' ? 'సమీక్ష అవసరం' : (lang === 'ta' ? 'மதிப்பாய்வு தேவை' : (lang === 'ml' ? 'പരിശോധന ആവശ്യമാണ്' : 'Needs review'))));

    grid.innerHTML = phrases.map(p => {
      const isFav = this.favorites.has(p.id);
      return `
        <div class="phrase-card">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div class="phrase-kn">${escapeHtml(p.kannada)}</div>
            <button onclick="KannadaCompanion.toggleFavorite('${p.id}')" style="background:none; border:none; cursor:pointer; font-size:18px; color: ${isFav ? 'var(--gold)' : 'var(--border-color)'};" title="Save favorite">
              ${isFav ? '★' : '☆'}
            </button>
          </div>
          <div class="phrase-tr">🗣️ ${escapeHtml(p.transliteration)}</div>
          <div class="phrase-en">${escapeHtml(p.english)}</div>
          <div class="phrase-context">${escapeHtml(p.context)}</div>
          ${!p.reviewed ? `<div style="margin-top: 6px;"><span class="badge badge-unknown">${reviewLabel}</span></div>` : ''}
          <div class="phrase-actions">
            <span class="badge badge-sourced">${escapeHtml(p.scenario)}</span>
            <button class="speak-btn" onclick="KannadaCompanion.speakText(${JSON.stringify(p.kannada)})">
              ${pronounceLabel}
            </button>
          </div>
        </div>
      `;
    }).join("");
  },

  renderDialogue() {
    const container = document.getElementById("dialogue-practice-container");
    if (!container || !this.dialogues.length) return;

    const cur = this.dialogues[this.currentDialogueIdx];
    const steps = cur.steps;
    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';

    const convWord = lang === 'kn' ? 'ಸಂಭಾಷಣೆ' : (lang === 'hi' ? 'संवाद' : (lang === 'te' ? 'సంభాషణ' : (lang === 'ta' ? 'உரையாடல்' : (lang === 'ml' ? 'സംഭാഷണം' : 'Conversation'))));
    const ofWord = lang === 'en' ? 'of' : '/';
    const convLabel = `${convWord} ${this.currentDialogueIdx + 1} ${ofWord} ${this.dialogues.length}`;
    const nextLineLabel = typeof I18n !== 'undefined' ? I18n.t('kc.btn_next_line', 'Next Line') : 'Next Line';
    const nextDialLabel = typeof I18n !== 'undefined' ? I18n.t('kc.btn_next_dialogue', 'Next Dialogue') : 'Next Dialogue';
    const repeatLabel = typeof I18n !== 'undefined' ? I18n.t('kc.btn_repeat', 'Repeat') : 'Repeat';
    const tapHint = lang === 'kn' ? '(ಅನುವಾದ ನೋಡಲು \'ಮುಂದಿನ ಸಾಲು\' ಕ್ಲಿಕ್ ಮಾಡಿ)' : (lang === 'hi' ? '(अनुवाद देखने के लिए अगला क्लिक करें)' : (lang === 'te' ? '(అనువాదాన్ని చూడటానికి తదుపరి క్లిక్ చేయండి)' : (lang === 'ta' ? '(மொழிபெயர்ப்பைக் காண அடுத்து என்பதைக் கிளிக் செய்க)' : (lang === 'ml' ? '(വിവർത്തനം കാണാൻ അടുത്തത് ക്ലിക്കുചെയ്യുക)' : '(Tap Next to reveal translation)'))));

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h4 style="font-size: 18px; color: var(--forest);">${escapeHtml(cur.title)}</h4>
        <div style="font-size: 13px; color: var(--charcoal-muted);">
          ${convLabel}
        </div>
      </div>
      <div>
        ${steps.map((st, i) => `
          <div class="dialogue-step" style="opacity: ${i <= this.currentStepIdx ? 1 : 0.4}; transition: opacity 0.3s ease;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <div style="font-size: 12px; font-weight: 700; color: var(--earth-red); margin-bottom: 2px;">
                ${escapeHtml(st.speaker)}:
              </div>
              <button class="icon-tool-btn" style="font-size:12px;padding:2px 8px;" onclick="KannadaCompanion.speakText(${JSON.stringify(st.kannada)})" title="Pronounce line">
                🔊
              </button>
            </div>
            <div class="kn-text" style="font-size: 16px; font-weight: 600; color: var(--charcoal); margin-bottom: 2px;">
              ${escapeHtml(st.kannada)}
            </div>
            <div style="font-size: 13px; color: var(--forest); font-weight: 500;">
              ${escapeHtml(st.transliteration)}
            </div>
            <div style="font-size: 13px; color: var(--charcoal-muted); margin-top: 2px;">
              ${i <= this.currentStepIdx ? escapeHtml(st.english) : `<em style="color:#999;">${tapHint}</em>`}
            </div>
          </div>
        `).join("")}
      </div>
      <div style="display: flex; gap: 12px; margin-top: 16px;">
        ${this.currentStepIdx < steps.length - 1 ? `
          <button class="btn-primary" style="padding: 7px 16px; font-size: 13px;" onclick="KannadaCompanion.nextStep()">${nextLineLabel}</button>
        ` : `
          <button class="btn-primary" style="padding: 7px 16px; font-size: 13px;" onclick="KannadaCompanion.nextDialogue()">${nextDialLabel}</button>
          <button class="btn-secondary" style="padding: 7px 16px; font-size: 13px;" onclick="KannadaCompanion.restartDialogue()">${repeatLabel}</button>
        `}
      </div>
    `;
  },

  nextStep() {
    this.currentStepIdx++;
    this.renderDialogue();
  },

  restartDialogue() {
    this.currentStepIdx = 0;
    this.renderDialogue();
  },

  nextDialogue() {
    this.currentDialogueIdx = (this.currentDialogueIdx + 1) % this.dialogues.length;
    this.currentStepIdx = 0;
    this.renderDialogue();
  }
};
