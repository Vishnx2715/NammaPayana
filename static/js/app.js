/**
 * Namma Payana — Main Frontend Application Controller (v2)
 * Journey DNA wizard, results rendering, hero particle canvas,
 * budget simulator, toast notifications, and saved trips.
 */

// escapeHtml is defined in i18n.js (first loaded script). This stub guards against
// loading order issues in testing or standalone contexts.
if (typeof escapeHtml === 'undefined') {
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;');
  }
}

// CSRF token getter — reads the token stored by Auth.getCsrfToken() on init
function getCsrfToken() {
  return window._csrfToken || '';
}

const App = {
  currentView: 'login',
  currentStep: 1,
  activeTrip: null,
  activeEditToken: null,
  sliderDebounceTimer: null,
  allDestinations: [],

  dnaDraft: {
    start_city:   'Bengaluru',
    days:         3,
    travellers:   2,
    budget:       { amount: 8000, scope: 'total', currency: 'INR' },
    style:        'economical',
    interests:    ['heritage', 'food'],
    pace:         'relaxed',
    transport:    'bus',
    stay:         'budget',
    diet:         'vegetarian',
    accessibility:[],
    must_visit:   [],
    avoid:        [],
    start_date:   null
  },

  // ─── Init ────────────────────────────────────────────
  init() {
    this.bindEvents();
    this.initHeroCanvas();
    this.initEstimator();
    this.loadRegionalShowcase();
    this.renderStep(1);
    this.loadSavedTripList();
    this.animateCounters();
    this.bindEntryCardRipple();
    if (typeof I18n !== 'undefined') I18n.init();
    if (typeof Auth !== 'undefined') Auth.init();

    // Determine initial view from URL path or hash
    const rawPath = (window.location.pathname || '').replace(/^\//, '').toLowerCase();
    const rawHash = (window.location.hash || '').replace(/^#/, '').toLowerCase();
    const initialRoute = rawPath || rawHash;

    if (initialRoute === 'register') {
      this.switchView('login');
      if (typeof Auth !== 'undefined' && Auth.switchTab) Auth.switchTab('register');
    } else {
      this.switchView('login');
      if (typeof Auth !== 'undefined' && Auth.switchTab) Auth.switchTab('login');
    }

    window.addEventListener('popstate', () => {
      const p = (window.location.pathname || '').replace(/^\//, '').toLowerCase() || 'login';
      this.switchView(p);
    });
  },

  // ─── Event Binding ───────────────────────────────────
  bindEvents() {
    // Navigation
    document.querySelectorAll('[data-nav]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        const targetNav = el.getAttribute('data-nav');
        if (targetNav !== 'login' && (!Auth || !Auth.currentUser)) {
          if (typeof App !== 'undefined' && (App.toast || App.showToast)) {
            (App.toast || App.showToast)('Please sign in to access Namma Payana.', 'err');
          }
          this.switchView('login');
          return;
        }
        this.switchView(targetNav);
      });
    });

    // Keyboard support for entry cards
    document.querySelectorAll('.entry-card').forEach(card => {
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          card.click();
        }
      });
    });

    // Chip selections
    document.querySelectorAll('.chip-group').forEach(group => {
      const field = group.getAttribute('data-field');
      if (!field) return;
      group.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
          const val = chip.getAttribute('data-value');
          if (!val) return;
          if (group.classList.contains('multi-select')) {
            chip.classList.toggle('selected');
            const selected = [...group.querySelectorAll('.chip.selected')].map(c => c.getAttribute('data-value'));
            this.dnaDraft[field] = selected;
          } else {
            group.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
            chip.classList.add('selected');
            this.dnaDraft[field] = val;
          }
        });
      });
    });

    // Budget slider
    const slider = document.getElementById('budget-slider');
    if (slider) {
      slider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        const el = document.getElementById('slider-budget-val');
        if (el) el.textContent = `₹${val.toLocaleString('en-IN')}`;
        this.debounceValidateBudget(val);
      });
    }

    // Step dots direct click navigation
    for (let i = 1; i <= 4; i++) {
      const dot = document.getElementById(`step-dot-${i}`);
      if (dot) {
        dot.style.cursor = 'pointer';
        dot.addEventListener('click', () => {
          this.collectCurrentStepData();
          this.renderStep(i);
        });
      }
    }

    // Close destination modal on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const modal = document.getElementById('destination-detail-modal');
        if (modal && modal.classList.contains('active')) {
          modal.classList.remove('active');
          document.body.style.overflow = '';
        }
      }
    });

    // Replan form
    const replanForm = document.getElementById('replan-form');
    if (replanForm) {
      replanForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleReplan();
      });
    }

    // Wizard Navigation Buttons
    const nextBtn = document.getElementById('btn-step-next');
    if (nextBtn) {
      nextBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.nextStep();
      });
    }

    const prevBtn = document.getElementById('btn-step-prev');
    if (prevBtn) {
      prevBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.prevStep();
      });
    }

    // Hero Estimator Apply Button
    const heroApply = document.getElementById('btn-hero-apply');
    if (heroApply) {
      heroApply.addEventListener('click', (e) => {
        e.preventDefault();
        this.applyHeroEstimator();
      });
    }

    // Showcase Region Tabs
    document.querySelectorAll('.region-tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const region = btn.getAttribute('data-region');
        if (region) this.filterRegionTab(region, btn);
      });
    });

    // Must-Visit Destination Picker Drawer
    const mvToggleBtn = document.getElementById('btn-toggle-dest-picker');
    if (mvToggleBtn) {
      mvToggleBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.toggleMustVisitPicker();
      });
    }

    const mvClearBtn = document.getElementById('btn-clear-must-visit');
    if (mvClearBtn) {
      mvClearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.clearAllMustVisit();
      });
    }

    // Results Bar Action Buttons
    const resMapBtn = document.getElementById('btn-res-map');
    if (resMapBtn) {
      resMapBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.viewRouteOnMap();
      });
    }

    const resPrintBtn = document.getElementById('btn-res-print');
    if (resPrintBtn) {
      resPrintBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.printTrip();
      });
    }

    const resExportBtn = document.getElementById('btn-res-export');
    if (resExportBtn) {
      resExportBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.exportCSV();
      });
    }

    const resSaveBtn = document.getElementById('btn-res-save');
    if (resSaveBtn) {
      resSaveBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.saveActiveTrip();
      });
    }

    // Phrase search / filter
    const phraseSearch = document.getElementById('phrase-search');
    const scenarioFilter = document.getElementById('scenario-filter');
    if (phraseSearch) phraseSearch.addEventListener('input', () => KannadaCompanion.filterPhrases());
    if (scenarioFilter) scenarioFilter.addEventListener('change', () => KannadaCompanion.filterPhrases());

    // Universal Delegated Click Handler for all interactive buttons
    document.addEventListener('click', (e) => {
      // Hero Estimator Apply
      const hApply = e.target.closest('#btn-hero-apply, button[onclick*="applyHeroEstimator"]');
      if (hApply) {
        e.preventDefault();
        this.applyHeroEstimator();
        return;
      }

      // Region Tabs
      const rBtn = e.target.closest('.region-tab-btn');
      if (rBtn) {
        e.preventDefault();
        const reg = rBtn.getAttribute('data-region');
        if (reg) this.filterRegionTab(reg, rBtn);
        return;
      }

      // Kannada Companion quick chips & buttons
      const quickChip = e.target.closest('.quick-chip');
      if (quickChip) {
        e.preventDefault();
        const phrase = quickChip.textContent.trim().replace(/^['"]|['"]$/g, '');
        if (typeof KannadaCompanion !== 'undefined' && KannadaCompanion.applyQuickPhrase) {
          KannadaCompanion.applyQuickPhrase(phrase);
        }
        return;
      }
      const kcTranslate = e.target.closest('#kc-btn-translate');
      if (kcTranslate) {
        e.preventDefault();
        if (typeof KannadaCompanion !== 'undefined' && KannadaCompanion.translate) {
          KannadaCompanion.translate();
        }
        return;
      }
      const kcClear = e.target.closest('button[onclick*="clearText"]');
      if (kcClear) {
        e.preventDefault();
        if (typeof KannadaCompanion !== 'undefined' && KannadaCompanion.clearText) {
          KannadaCompanion.clearText();
        }
        return;
      }

      // Destination Modal Close
      const modalClose = e.target.closest('.dest-modal-close');
      if (modalClose) {
        e.preventDefault();
        this.closeDestinationModal();
        return;
      }
    });
  },

  // Mouse-tracking radial effect on entry cards
  bindEntryCardRipple() {
    document.querySelectorAll('.entry-card').forEach(card => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;
        card.style.setProperty('--mx', `${x}%`);
        card.style.setProperty('--my', `${y}%`);
      });
    });
  },

  // ─── Animated Hero Canvas ────────────────────────────
  initHeroCanvas() {
    const canvas = document.getElementById('hero-particle-canvas');
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Three types: dust (gold), ember (red), star (white)
    const particles = [];
    const count = 55;
    for (let i = 0; i < count; i++) {
      const type = i < 30 ? 'dust' : (i < 45 ? 'ember' : 'star');
      particles.push({
        x:     Math.random() * canvas.width,
        y:     Math.random() * canvas.height,
        r:     Math.random() * (type === 'star' ? 1.2 : 2) + 0.5,
        dx:    (Math.random() - 0.5) * 0.35,
        dy:    (Math.random() - 0.5) * 0.35,
        alpha: Math.random() * 0.45 + 0.15,
        dAlpha: (Math.random() - 0.5) * 0.003,
        type
      });
    }

    const COLORS = { dust: '201,162,75', ember: '139,46,31', star: '255,252,240' };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.x += p.dx;
        p.y += p.dy;
        p.alpha = Math.max(0.05, Math.min(0.65, p.alpha + p.dAlpha));
        if (Math.random() < 0.01) p.dAlpha *= -1;

        // Wrap
        if (p.x < 0)            p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0)            p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${COLORS[p.type]},${p.alpha})`;
        ctx.fill();
      });
      requestAnimationFrame(animate);
    };
    animate();
  },

  // ─── Stat Counters Animation ─────────────────────────
  animateCounters() {
    const els = document.querySelectorAll('[data-count]');
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const target = parseInt(el.getAttribute('data-count'));
        let current = 0;
        const step = Math.ceil(target / 40);
        const timer = setInterval(() => {
          current = Math.min(current + step, target);
          el.textContent = current;
          if (current >= target) clearInterval(timer);
        }, 30);
        observer.unobserve(el);
      });
    }, { threshold: 0.5 });
    els.forEach(el => observer.observe(el));
  },

  // ─── Hero Estimator ──────────────────────────────────
  initEstimator() {
    const cityEl  = document.getElementById('est-city');
    const daysEl  = document.getElementById('est-days');
    const styleEl = document.getElementById('est-style');
    const travEl  = document.getElementById('est-travellers');

    const update = () => {
      const days   = parseInt(daysEl.value)  || 3;
      const trav   = parseInt(travEl.value)  || 2;
      const style  = styleEl.value;
      const city   = cityEl.value;

      // Verified Karnataka per-person-per-day baselines
      const BASELINES = { economical: 1350, moderate: 2900, luxury: 7500 };
      const dailyPP   = BASELINES[style] || 1350;
      const transit   = days * 480; // avg transit cost per day per group

      const total = Math.round((dailyPP * days * trav + transit) * 1.10);

      const valEl = document.getElementById('est-result-val');
      if (valEl) valEl.textContent = `₹${total.toLocaleString('en-IN')}`;

      const corridorEl = document.getElementById('est-result-corridor');
      if (corridorEl) {
        if (typeof I18n !== 'undefined' && typeof I18n.getCorridor === 'function') {
          corridorEl.textContent = I18n.getCorridor(city);
        } else {
          const CORRIDORS = {
            'Bengaluru':   'Mysuru → Belur → Halebidu',
            'Mangaluru':   'Udupi → Gokarna → Jog Falls',
            'Mysuru':      'Srirangapatna → Coorg → Wayanad edge',
            'Hubballi':    'Hampi → Badami → Pattadakal',
            'default':     'Hampi → Aihole → Badami Heritage Belt'
          };
          corridorEl.textContent = CORRIDORS[city] || CORRIDORS['default'];
        }
      }
    };

    [cityEl, daysEl, styleEl, travEl].forEach(el => {
      if (el) el.addEventListener('change', update);
    });
    if (travEl) travEl.addEventListener('input', update);
    update();
  },

  applyHeroEstimator() {
    const cityEl  = document.getElementById('est-city');
    const daysEl  = document.getElementById('est-days');
    const styleEl = document.getElementById('est-style');
    const travEl  = document.getElementById('est-travellers');

    if (cityEl && cityEl.value)   this.dnaDraft.start_city   = cityEl.value;
    if (daysEl && daysEl.value)   this.dnaDraft.days         = parseInt(daysEl.value) || 3;
    if (travEl && travEl.value)   this.dnaDraft.travellers   = parseInt(travEl.value) || 2;
    if (styleEl && styleEl.value) this.dnaDraft.style        = styleEl.value;

    const valEl = document.getElementById('est-result-val');
    if (valEl) {
      const raw = parseInt((valEl.textContent || '').replace(/[^0-9]/g, '')) || 8000;
      this.dnaDraft.budget.amount = raw;
    }

    // Sync form fields
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    setVal('input-start-city', this.dnaDraft.start_city);
    setVal('input-days',       this.dnaDraft.days);
    setVal('input-travellers', this.dnaDraft.travellers);
    setVal('input-budget-amt', this.dnaDraft.budget.amount);

    this.switchView('journey');
  },

  // ─── Image Resolution Helper ─────────────────────────
  getImageUrl(dest) {
    if (!dest) return '/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';
    if (typeof dest === 'string') {
      return `/static/images/${encodeURIComponent(dest)}.jpg`;
    }
    if (dest.image && dest.image.url) {
      return dest.image.url;
    }
    if (dest.image && dest.image.file) {
      return `/static/images/${encodeURIComponent(dest.image.file)}`;
    }
    if (dest.name_en) {
      return '/static/images/' + encodeURIComponent(dest.name_en) + '.jpg';
    }
    if (dest.id) {
      return `/static/images/${encodeURIComponent(dest.id)}.jpg`;
    }
    return '/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';
  },

  // ─── Regional Showcase ───────────────────────────────
  async loadRegionalShowcase() {
    try {
      const res  = await fetch('/api/destinations');
      const json = await res.json();
      if (json.ok) {
        this.allDestinations = json.data.destinations;
        this.renderFeaturedLandmarks();
        this.renderRegionCards('North Karnataka');
        this.renderPopularDestinations();
        this.updateMustVisitDisplay();
      }
    } catch (err) {
      console.error('[App] Failed to load destinations:', err);
    }
  },

  renderFeaturedLandmarks() {
    const grid = document.getElementById('featured-landmarks-grid');
    if (!grid || !this.allDestinations || !this.allDestinations.length) return;

    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';
    const featuredIds = [
      'mysuru_palace',
      'hampi_virupaksha',
      'badami_caves',
      'jog_falls',
      'belur_chennakeshava',
      'coorg_madikeri',
      'om_beach_gokarna',
      'murudeshwar_temple'
    ];

    const featured = this.allDestinations.filter(d => featuredIds.includes(d.id));

    grid.innerHTML = featured.map(d => {
      const imgUrl = this.getImageUrl(d);
      const primaryTitle = escapeHtml((lang === 'kn') ? (d.name_kn || d.name_en) : d.name_en);
      const secondaryTitle = escapeHtml((lang === 'kn') ? d.name_en : (d.name_kn || ''));
      const isSelected = this.dnaDraft.must_visit.includes(d.id);
      const btnText = isSelected ? '✓ Selected' : '+ Must-Visit';
      const btnClass = isSelected ? 'btn-primary selected' : 'btn-primary';

      return `
        <div class="featured-landmark-card" onclick="App.openDestinationModal('${d.id}')" tabindex="0" role="button" title="View landmark details">
          <div class="featured-landmark-img-wrap">
            <img
              src="${escapeHtml(imgUrl)}"
              alt="${primaryTitle}"
              class="featured-landmark-img"
              loading="lazy"
              onerror="this.onerror=null;this.src='/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';"
            >
            <span class="atlas-dest-badge" style="color:var(--earth-red); border:1.5px solid var(--earth-red);">
              ${escapeHtml(d.region)}
            </span>
          </div>
          <div class="featured-landmark-content">
            <div class="featured-landmark-title">${primaryTitle}</div>
            <div class="featured-landmark-kn">${secondaryTitle}</div>
            <div style="font-size:12px; color:var(--charcoal-muted); margin-bottom:8px;">
              📍 ${escapeHtml(d.district)} &bull; ⏱ ${d.visit_hours}h
            </div>
            <div class="featured-landmark-footer" onclick="event.stopPropagation()">
              <button
                type="button"
                class="btn-secondary"
                style="padding:5px 10px; font-size:11px;"
                onclick="App.switchView('map'); setTimeout(() => { if (typeof KarnatakaMap !== 'undefined') KarnatakaMap.focusDestination('${d.id}'); }, 200);"
              >
                🗺️ Atlas
              </button>
              <button
                type="button"
                class="${btnClass}"
                style="padding:5px 12px; font-size:11px;"
                onclick="App.toggleMustVisit('${d.id}'); App.renderFeaturedLandmarks(); App.renderRegionCards();"
              >
                ${btnText}
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  },

  filterRegionTab(regionName, btnEl) {
    document.querySelectorAll('.region-tab-btn').forEach(b => b.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');
    this.renderRegionCards(regionName);
  },

  renderRegionCards(regionName) {
    this.currentRegion = regionName || this.currentRegion || 'North Karnataka';
    const grid = document.getElementById('region-cards-grid');
    if (!grid) return;

    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';
    const filtered = this.allDestinations.filter(d => d.region === this.currentRegion);
    if (filtered.length === 0) {
      const emptyMsg = typeof I18n !== 'undefined' ? I18n.t('general.no_dest_found', 'No destinations found for this region in the verified dataset.') : 'No destinations found for this region in the verified dataset.';
      grid.innerHTML = `<div style="color:var(--charcoal-muted);font-size:14px;padding:24px;text-align:center;">${emptyMsg}</div>`;
      return;
    }

    grid.innerHTML = filtered.map(d => {
      const freeLabel = typeof I18n !== 'undefined' ? I18n.t('general.free', 'Free') : 'Free';
      const feeVal = (d.entry_fee_inr && d.entry_fee_inr.value !== null) ? `₹${d.entry_fee_inr.value}` : freeLabel;
      const fee    = feeVal;
      const imgUrl = this.getImageUrl(d);
      const desc   = escapeHtml((d.description || '').slice(0, 105)) + ((d.description || '').length > 105 ? '…' : '');
      const primaryTitle = escapeHtml((lang === 'kn') ? (d.name_kn || d.name_en) : d.name_en);
      const secondaryTitle = escapeHtml((lang === 'kn') ? d.name_en : (d.name_kn || ''));
      const hoursStr = (lang === 'kn') ? `${d.visit_hours} ಗಂಟೆ` : `${d.visit_hours}h`;
      const isSelected = this.dnaDraft.must_visit.includes(d.id);
      const btnText = isSelected
        ? (typeof I18n !== 'undefined' ? I18n.t('general.added', '✓ Selected') : '✓ Selected')
        : (typeof I18n !== 'undefined' ? I18n.t('map.btn_must_visit', '+ Must-Visit') : '+ Must-Visit');
      const btnClass = isSelected ? 'btn-primary selected' : 'btn-primary';
      const btnTitle = isSelected ? 'Click to remove from must-visit' : 'Click to add to must-visit';

      return `
        <div class="dest-preview-card" onclick="App.openDestinationModal('${d.id}')" tabindex="0" role="button" title="Click to view details">
          <div class="dest-preview-img-wrap">
            <img
              src="${escapeHtml(imgUrl)}"
              alt="${primaryTitle}"
              class="dest-preview-img"
              loading="lazy"
              onerror="this.onerror=null;this.src='/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';"
            >
            <div class="dest-preview-overlay"></div>
          </div>
          <div class="dest-preview-content">
            <div class="dest-preview-title">${primaryTitle}</div>
            <div class="dest-preview-kn">${secondaryTitle}</div>
            <p class="dest-preview-desc">${desc}</p>
            <div class="dest-preview-footer">
              <span style="font-size:12px;font-weight:600;color:var(--forest);">⏱ ${hoursStr} &bull; 🎟 ${fee}</span>
              <button class="${btnClass}" style="padding:4px 12px;font-size:11px;" title="${btnTitle}" onclick="event.stopPropagation();App.toggleMustVisit('${d.id}');">
                ${btnText}
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  },

  // ─── View Navigation ─────────────────────────────────
  switchView(viewName) {
    this.closeDestinationModal();
    document.body.style.overflow = '';
    this.currentView = viewName;

    document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    const sec = document.getElementById(`view-${viewName}`);
    if (sec) sec.classList.add('active');

    const navBtn = document.querySelector(`.nav-btn[data-nav="${viewName}"]`);
    if (navBtn) navBtn.classList.add('active');

    if (window.history && window.history.pushState) {
      const targetUrl = viewName === 'landing' ? '/' : `/${viewName}`;
      if (window.location.pathname !== targetUrl && !['results'].includes(viewName)) {
        window.history.pushState({ view: viewName }, '', targetUrl);
      }
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (viewName === 'landing') {
      setTimeout(() => this.initHeroCanvas(), 60);
    } else if (viewName === 'journey') {
      this.renderStep(this.currentStep || 1);
    } else if (viewName === 'map') {
      KarnatakaMap.init();
      setTimeout(() => {
        KarnatakaMap.invalidate();
        if (this.activeTrip && this.activeTrip.itinerary) {
          KarnatakaMap.plotItineraryRoute(this.activeTrip.itinerary);
        }
      }, 80);
      setTimeout(() => {
        KarnatakaMap.invalidate();
      }, 250);
    } else if (viewName === 'kannada') {
      KannadaCompanion.init();
    } else if (viewName === 'saved') {
      this.loadSavedTripList();
    }
  },

  viewRouteOnMap() {
    this.switchView('map');
    setTimeout(() => {
      if (this.activeTrip && this.activeTrip.itinerary) {
        KarnatakaMap.plotItineraryRoute(this.activeTrip.itinerary);
      }
    }, 120);
  },

  // ─── Step Wizard ─────────────────────────────────────
  renderStep(stepNum) {
    this.currentStep = stepNum;
    for (let i = 1; i <= 4; i++) {
      const content = document.getElementById(`step-content-${i}`);
      const dot     = document.getElementById(`step-dot-${i}`);
      if (content) content.style.display = (i === stepNum) ? 'block' : 'none';
      if (dot) {
        dot.classList.remove('active', 'completed');
        if (i === stepNum) dot.classList.add('active');
        else if (i < stepNum) dot.classList.add('completed');
      }
    }

    // Update step indicator progress line
    const indicator = document.getElementById('step-indicator');
    if (indicator) {
      indicator.style.setProperty('--progress', `${(stepNum / 4) * 100}%`);
    }

    // Smoothly scroll the stepper into view on step change
    const stepper = document.querySelector('.stepper-wrap');
    if (stepper) {
      stepper.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Button labels
    const prevBtn = document.getElementById('btn-step-prev');
    const nextBtn = document.getElementById('btn-step-next');
    if (prevBtn) {
      prevBtn.style.visibility = (stepNum === 1) ? 'hidden' : 'visible';
      prevBtn.textContent = typeof I18n !== 'undefined' ? I18n.t('wizard.btn_prev', '← Previous') : '← Previous';
    }
    if (nextBtn) {
      if (stepNum === 4) {
        nextBtn.textContent = typeof I18n !== 'undefined' ? I18n.t('wizard.btn_generate', 'Generate My Plan →') : 'Generate My Plan →';
        this.renderPopularDestinations();
        this.updateMustVisitDisplay();
      } else {
        nextBtn.textContent = typeof I18n !== 'undefined' ? I18n.t('wizard.btn_next', 'Next Step →') : 'Next Step →';
      }
    }
  },

  nextStep() {
    const now = Date.now();
    if (this._lastStepNav && now - this._lastStepNav < 250) return;
    this._lastStepNav = now;
    this.collectCurrentStepData();
    if (this.currentStep < 4) {
      this.renderStep(this.currentStep + 1);
    } else {
      this.generateJourney();
    }
  },

  prevStep() {
    const now = Date.now();
    if (this._lastStepNav && now - this._lastStepNav < 250) return;
    this._lastStepNav = now;
    if (this.currentStep > 1) this.renderStep(this.currentStep - 1);
  },

  collectCurrentStepData() {
    if (this.currentStep === 1) {
      const city = document.getElementById('input-start-city');
      const days = document.getElementById('input-days');
      const trav = document.getElementById('input-travellers');
      if (city) this.dnaDraft.start_city  = city.value.trim() || 'Bengaluru';
      if (days) this.dnaDraft.days        = parseInt(days.value)  || 3;
      if (trav) this.dnaDraft.travellers  = parseInt(trav.value)  || 2;
    } else if (this.currentStep === 2) {
      const amt   = document.getElementById('input-budget-amt');
      const scope = document.getElementById('input-budget-scope');
      if (amt)   this.dnaDraft.budget.amount = parseFloat(amt.value)  || 8000;
      if (scope) this.dnaDraft.budget.scope  = scope.value;
    }
  },

  // ─── Generate Journey ────────────────────────────────
  async generateJourney() {
    this.collectCurrentStepData();
    const btn = document.getElementById('btn-step-next');
    if (btn) {
      btn.textContent = typeof I18n !== 'undefined' ? I18n.t('wizard.btn_validating', '⟳ Validating…') : '⟳ Validating…';
      btn.disabled = true;
    }

    try {
      const res  = await fetch('/api/trips/generate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(this.dnaDraft)
      });
      const json = await res.json();

      if (!json.ok) {
        const failPrefix = typeof I18n !== 'undefined' && I18n.currentLang === 'kn' ? 'ಯೋಜನೆ ರಚನೆ ವಿಫಲವಾಗಿದೆ: ' : 'Generation failed: ';
        this.toast(failPrefix + (json.error?.message || 'Unknown error'), 'err');
        return;
      }

      this.activeTrip = json.data;
      this.renderResults();
      this.switchView('results');
      this.toast(typeof I18n !== 'undefined' ? I18n.t('toast.itinerary_ready', 'Your verified itinerary is ready!') : 'Your verified itinerary is ready!', 'ok');
    } catch (err) {
      console.error('[App] generateJourney error:', err);
      this.toast(typeof I18n !== 'undefined' ? I18n.t('toast.error_connect', 'Could not connect to Namma Payana server.') : 'Could not connect to Namma Payana server.', 'err');
    } finally {
      if (btn) {
        btn.textContent = typeof I18n !== 'undefined' ? I18n.t('wizard.btn_generate', 'Generate My Plan →') : 'Generate My Plan →';
        btn.disabled = false;
      }
    }
  },

  // ─── Render Results ──────────────────────────────────
  renderResults() {
    if (!this.activeTrip) return;
    const { dna, itinerary, budget, feasibility, ai_meta } = this.activeTrip;
    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';

    // AI Meta notice
    const aiNotice = document.getElementById('ai-notice-banner');
    if (aiNotice) {
      aiNotice.textContent = typeof I18n !== 'undefined' ? I18n.t('res.engine_banner', 'Deterministic Engine') : (ai_meta?.notice || 'Deterministic Engine');
    }

    // Feasibility
    const scoreEl  = document.getElementById('res-feasibility-score');
    const statusEl = document.getElementById('res-feasibility-status');
    const barEl    = document.getElementById('res-feasibility-bar');

    if (scoreEl) scoreEl.textContent = Math.round(feasibility.score || 0);
    if (statusEl) {
      statusEl.className = `badge badge-${feasibility.status || 'feasible'}`;
      const statusLabel = typeof I18n !== 'undefined'
        ? I18n.getFeasibilityLabel(feasibility.status || 'feasible')
        : (feasibility.status || 'feasible');
      statusEl.textContent = statusLabel.toUpperCase();
    }
    if (barEl) {
      barEl.style.width = `${Math.min(100, feasibility.score || 0)}%`;
      const colors = { infeasible: 'var(--danger)', tight: 'var(--warn)' };
      barEl.style.background = colors[feasibility.status] || 'linear-gradient(90deg,var(--forest),#4A8F64)';
    }

    // Component list
    const compList = document.getElementById('res-feasibility-components');
    if (compList && feasibility.components) {
      compList.innerHTML = feasibility.components.map(c => {
        let name = c.name;
        if (lang === 'kn') {
          if (c.name.includes('Budget')) name = 'ಬಜೆಟ್ ಸಾಧ್ಯತೆ';
          else if (c.name.includes('Schedule')) name = 'ವೇಳಾಪಟ್ಟಿ ಸಾಧ್ಯತೆ';
          else if (c.name.includes('Route')) name = 'ಮಾರ್ಗ ತರ್ಕ';
          else if (c.name.includes('Preference')) name = 'ಆದ್ಯತೆಗಳ ಹೊಂದಾಣಿಕೆ';
          else if (c.name.includes('Data')) name = 'ದತ್ತಾಂಶ ವಿಶ್ವಾಸಾರ್ಹತೆ';
        } else if (lang === 'hi') {
          if (c.name.includes('Budget')) name = 'बजट व्यावहारिकता';
          else if (c.name.includes('Schedule')) name = 'समय सारणी व्यावहारिकता';
          else if (c.name.includes('Route')) name = 'मार्ग तर्क';
          else if (c.name.includes('Preference')) name = 'प्राथमिकता संरेखण';
          else if (c.name.includes('Data')) name = 'डेटा विश्वसनीयता';
        } else if (lang === 'te') {
          if (c.name.includes('Budget')) name = 'బడ్జెట్ సాధ్యత';
          else if (c.name.includes('Schedule')) name = 'సమయ పట్టిక సాధ్యత';
          else if (c.name.includes('Route')) name = 'రూట్ లాజిక్';
          else if (c.name.includes('Preference')) name = 'ప్రాధాన్యతల సమలేఖనం';
          else if (c.name.includes('Data')) name = 'డేటా విశ్వసనీయత';
        } else if (lang === 'ta') {
          if (c.name.includes('Budget')) name = 'பட்ஜெட் சாத்தியக்கூறு';
          else if (c.name.includes('Schedule')) name = 'அட்டவணை சாத்தியக்கூறு';
          else if (c.name.includes('Route')) name = 'பாதை தர்க்கம்';
          else if (c.name.includes('Preference')) name = 'விருப்பத்தேர்வு பொருத்தம்';
          else if (c.name.includes('Data')) name = 'தரவு நம்பகத்தன்மை';
        } else if (lang === 'ml') {
          if (c.name.includes('Budget')) name = 'ബജറ്റ് പ്രായോഗികത';
          else if (c.name.includes('Schedule')) name = 'സമയക്രമ പ്രായോഗികത';
          else if (c.name.includes('Route')) name = 'റൂട്ട് ലോജിക്';
          else if (c.name.includes('Preference')) name = 'മുൻഗണനാ ക്രമീകരണം';
          else if (c.name.includes('Data')) name = 'ഡാറ്റാ വിശ്വാസ്യത';
        }
        return `
        <div class="comp-score-item">
          <div>
            <strong style="font-size:13px;">${name}</strong><br>
            <span style="font-size:11px;color:var(--charcoal-muted);">${escapeHtml(c.explanation)}</span>
          </div>
          <div style="font-weight:700;color:${c.status==='fail'?'var(--danger)':'var(--forest)'};font-size:14px;">
            ${c.score}/${c.max_score}
          </div>
        </div>
      `;}).join('');
    }

    // Issues
    const issuesEl = document.getElementById('res-feasibility-issues');
    if (issuesEl) {
      if (feasibility.issues && feasibility.issues.length > 0) {
        const alertLabel = lang === 'kn' ? 'ನಿಯಮ ಎಚ್ಚರಿಕೆಗಳು:' : (lang === 'hi' ? 'बाध्यता चेतावनियाँ:' : (lang === 'te' ? 'నియమ హెచ్చరికలు:' : (lang === 'ta' ? 'கட்டுப்பாடு எச்சரிக்கைகள்:' : (lang === 'ml' ? 'നിയന്ത്രണ മുന്നറിയിപ്പുകൾ:' : 'Constraint Alerts:'))));
        const fixLabel = lang === 'kn' ? 'ಶಿಫಾರಸು ಮಾಡಿದ ಪರಿಹಾರಗಳು:' : (lang === 'hi' ? 'अनुशंसित सुधार:' : (lang === 'te' ? 'సిఫార్సు చేయబడిన పరిష్కారాలు:' : (lang === 'ta' ? 'பரிந்துரைக்கப்பட்ட தீர்வுகள்:' : (lang === 'ml' ? 'ശുപാർശ ചെയ്ത പരിഹാരങ്ങൾ:' : 'Recommended Fixes:'))));
        issuesEl.innerHTML = `
          <div class="alert-infeasible">
            <strong style="color:var(--danger);">${alertLabel}</strong>
            <ul style="margin-left:18px;margin-top:6px;line-height:1.55;">
              ${feasibility.issues.map(i => `<li>${escapeHtml(i)}</li>`).join('')}
            </ul>
            ${feasibility.suggestions && feasibility.suggestions.length > 0 ? `
              <div style="margin-top:10px;">
                <strong>${fixLabel}</strong>
                <ul style="margin-left:18px;margin-top:4px;line-height:1.55;">
                  ${feasibility.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
                </ul>
              </div>
            ` : ''}
          </div>
        `;
      } else {
        issuesEl.innerHTML = '';
      }
    }

    // Why This Plan
    const whyEl = document.getElementById('res-why-plan-items');
    if (whyEl && itinerary.why_this_plan) {
      whyEl.innerHTML = itinerary.why_this_plan.map(item => `
        <div class="why-plan-item">
          <div class="why-plan-input">→ ${escapeHtml(item.input)}</div>
          <div class="why-plan-effect">${escapeHtml(item.effect)}</div>
        </div>
      `).join('');
    }

    // Day Timeline
    const daysEl = document.getElementById('res-days-timeline');
    const dayWord = typeof I18n !== 'undefined' ? I18n.t('general.day', 'Day') : 'Day';
    const roadWord = typeof I18n !== 'undefined' ? I18n.t('general.road', 'road') : 'road';
    const freeWord = typeof I18n !== 'undefined' ? I18n.t('general.free', 'Free') : 'Free';
    const arriveWord = typeof I18n !== 'undefined' ? I18n.t('general.arrive', 'Arrive') : 'Arrive';
    const stayWord = typeof I18n !== 'undefined' ? I18n.t('general.stay', 'stay') : 'stay';

    if (daysEl && itinerary.days) {
      daysEl.innerHTML = itinerary.days.map(day => `
        <div class="day-timeline-card">
          <div class="day-timeline-title">
            <h3 style="font-size:20px;">${dayWord} ${day.day_number}: <em style="font-style:italic;color:var(--charcoal-muted);font-size:17px;">${escapeHtml(day.region_theme || '')}</em></h3>
            <span class="badge badge-sourced">~${day.travel_distance_km || 0} km ${roadWord}</span>
          </div>
          <div class="stops-list">
            ${(day.stops || []).map((stop, si) => {
              const d  = stop.destination;
              const fee = (d.entry_fee_inr && d.entry_fee_inr.value !== null) ? `₹${d.entry_fee_inr.value}` : freeWord;
              const img = this.getImageUrl(d);
              const primaryTitle = escapeHtml((lang === 'kn') ? (d.name_kn || d.name_en) : d.name_en);
              const secondaryTitle = escapeHtml((lang === 'kn') ? d.name_en : (d.name_kn || ''));
              const isFoodStop = stop.stop_type === 'food_stop' || (d.categories || []).includes('food');
              const stopBadge = isFoodStop
                ? `<span style="background:rgba(201,162,75,0.18);color:#7A5B15;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:6px;">🍲 Food Stop</span>`
                : '';
              const routeLine = si === 0
                ? `<div style="font-size:11px;color:var(--charcoal-muted);margin-bottom:8px;display:flex;align-items:center;gap:6px;">
                     <span style="color:var(--forest);font-weight:600;">📍 Start of Day ${day.day_number}</span>
                   </div>`
                : (stop.leg_distance_km > 0
                    ? `<div style="font-size:11px;color:var(--charcoal-muted);margin-bottom:8px;display:flex;align-items:center;gap:6px;">
                         <span style="color:var(--gold);font-size:14px;">↕</span>
                         <span><strong>${stop.leg_distance_km} km</strong> drive (≈${(stop.leg_duration_hours * 60).toFixed(0)} min)</span>
                       </div>`
                    : '');
              return `
                ${routeLine}
                <div class="stop-timeline-item" style="${isFoodStop ? 'border-left:3px solid var(--gold);' : ''}">
                  <img
                    src="${escapeHtml(img)}"
                    alt="${primaryTitle}"
                    class="stop-thumb-img"
                    loading="lazy"
                    onerror="this.onerror=null;this.src='/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';"
                  >
                  <div class="stop-detail-col">
                    <div class="stop-title-wrap">
                      <span class="stop-title">${primaryTitle}${stopBadge}</span>
                      <span class="kn-text" style="color:var(--gold);font-weight:700;font-size:14px;">${secondaryTitle}</span>
                    </div>
                    <div class="stop-meta-line">
                      <span>📍 ${escapeHtml(d.district)}</span>
                      <span>⏰ ${arriveWord} <strong>${escapeHtml(stop.arrival_hour_str || '—')}</strong></span>
                      <span>⏱ <strong>${stop.visit_hours}h ${stayWord}</strong></span>
                      <span>🎟 ${fee} <span class="badge badge-${d.entry_fee_inr ? escapeHtml(d.entry_fee_inr.basis) : 'unknown'}">${d.entry_fee_inr ? escapeHtml(d.entry_fee_inr.basis) : 'unknown'}</span></span>
                    </div>
                    <p style="font-size:13px;color:var(--charcoal-soft);margin-bottom:8px;line-height:1.55;">
                      ${escapeHtml(d.description || '')}
                    </p>
                    <div style="font-size:12px;color:var(--forest);font-weight:600;">
                      💡 ${(stop.why_matched || []).map(w => escapeHtml(w)).join(' · ')}
                    </div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `).join('');
    }

    this.renderBudget(budget);
    this.updateBudgetBanner(budget);
    // Slider setup — sync to current allocated budget, not cost
    const slider = document.getElementById('budget-slider');
    if (slider && budget) {
      slider.min   = Math.max(1000, Math.floor((budget.total_cost || 8000) * 0.5));
      slider.max   = Math.ceil((budget.total_cost || 8000) * 2.2);
      slider.value = budget.total_budget || budget.total_cost || 8000;
      const sliderVal = document.getElementById('slider-budget-val');
      if (sliderVal) sliderVal.textContent = `₹${(parseFloat(slider.value)).toLocaleString('en-IN')}`;
    }
  },

  renderBudget(budget) {
    if (!budget) return;
    const el = document.getElementById('res-budget-summary');
    if (!el) return;

    const cat   = budget.category_totals || {};
    const total = budget.total_cost || 1;
    const pct   = (v) => Math.max(0, ((v || 0) / total) * 100).toFixed(1);

    const segments = [
      { key: 'transport',        color: '#8B2E1F', label: typeof I18n !== 'undefined' ? I18n.t('general.transport', 'Transport') : 'Transport' },
      { key: 'accommodation',    color: '#C9A24B', label: typeof I18n !== 'undefined' ? I18n.t('general.accommodation', 'Stay') : 'Stay' },
      { key: 'food',             color: '#2F4F3A', label: typeof I18n !== 'undefined' ? I18n.t('general.food', 'Food') : 'Food' },
      { key: 'local_travel',     color: '#7A5B15', label: typeof I18n !== 'undefined' ? I18n.t('general.local', 'Local') : 'Local' },
      { key: 'entry_tickets',    color: '#2F7D4F', label: typeof I18n !== 'undefined' ? I18n.t('general.tickets', 'Tickets') : 'Tickets' },
      { key: 'emergency_reserve',color: '#B7791F', label: typeof I18n !== 'undefined' ? I18n.t('general.reserve', 'Reserve') : 'Reserve' }
    ];

    const barHtml = segments.map(s =>
      `<div class="bar-segment" style="width:${pct(cat[s.key])}%;background:${s.color};" title="${s.label}: ₹${(cat[s.key]||0).toLocaleString('en-IN')} (${pct(cat[s.key])}%)"></div>`
    ).join('');

    const overBudget = budget.total_cost > budget.total_budget;
    const diff = Math.abs((budget.total_cost || 0) - (budget.total_budget || 0));

    const allocatedLabel = typeof I18n !== 'undefined' ? I18n.t('res.allocated', 'Allocated:') : 'Allocated:';
    const overText = typeof I18n !== 'undefined' ? I18n.t('general.over_by', '▲ Over by') : '▲ Over by';
    const underText = typeof I18n !== 'undefined' ? I18n.t('general.under_by', '▼ Under by') : '▼ Under by';
    const diffText = overBudget
      ? `${overText} ₹${diff.toLocaleString('en-IN')}`
      : `${underText} ₹${diff.toLocaleString('en-IN')}`;

    const categoryNames = {
      'transport': typeof I18n !== 'undefined' ? I18n.t('general.transport', 'Transport') : 'Transport',
      'accommodation': typeof I18n !== 'undefined' ? I18n.t('general.accommodation', 'Accommodation') : 'Accommodation',
      'food': typeof I18n !== 'undefined' ? I18n.t('general.food', 'Food') : 'Food',
      'local_travel': typeof I18n !== 'undefined' ? I18n.t('general.local', 'Local travel') : 'Local travel',
      'entry_tickets': typeof I18n !== 'undefined' ? I18n.t('general.tickets', 'Entry tickets') : 'Entry tickets',
      'emergency_reserve': typeof I18n !== 'undefined' ? I18n.t('general.reserve', 'Emergency reserve') : 'Emergency reserve'
    };

    const spendPct = Math.min(100, ((budget.total_cost || 0) / (budget.total_budget || 1)) * 100);
    const meterColor = overBudget ? 'var(--danger)' : (spendPct > 85 ? 'var(--warn)' : 'var(--forest)');
    const statusPill = overBudget
      ? `<span style="background:var(--danger);color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:0.5px;">OVER BUDGET</span>`
      : (spendPct > 85
          ? `<span style="background:var(--warn);color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:0.5px;">TIGHT</span>`
          : `<span style="background:var(--forest);color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:0.5px;">WITHIN BUDGET</span>`);

    el.innerHTML = `
      <!-- Hero cost row -->
      <div style="background:${overBudget?'rgba(139,46,31,0.06)':'rgba(47,125,79,0.06)'};border:1px solid ${overBudget?'rgba(139,46,31,0.2)':'rgba(47,125,79,0.2)'};border-radius:10px;padding:14px 16px;margin-bottom:14px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
          <div>
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--charcoal-muted);font-weight:700;margin-bottom:3px;">Estimated Total Cost</div>
            <div style="font-size:32px;font-weight:800;color:${overBudget?'var(--danger)':'var(--earth-red)'};font-family:var(--font-serif);line-height:1;">₹${(budget.total_cost||0).toLocaleString('en-IN')}</div>
            <div style="font-size:11px;color:var(--charcoal-muted);margin-top:2px;">${escapeHtml(budget.cost_label || 'total trip cost')}</div>
          </div>
          <div style="text-align:right;">
            ${statusPill}
            <div style="font-size:11px;color:var(--charcoal-muted);margin-top:6px;">${allocatedLabel}</div>
            <div style="font-size:16px;font-weight:700;color:var(--charcoal);">₹${(budget.total_budget||0).toLocaleString('en-IN')}</div>
            <div style="font-size:12px;font-weight:600;color:${overBudget?'var(--danger)':'var(--forest)'};">${diffText}</div>
          </div>
        </div>
        <!-- Spend meter -->
        <div style="height:6px;background:var(--border-color);border-radius:3px;overflow:hidden;">
          <div style="height:100%;width:${spendPct.toFixed(1)}%;background:${meterColor};border-radius:3px;transition:width 0.6s ease;"></div>
        </div>
        <div style="font-size:10px;color:var(--charcoal-muted);margin-top:4px;">${spendPct.toFixed(0)}% of budget used</div>
      </div>

      <!-- Category bar -->
      <div class="budget-stacked-bar">${barHtml}</div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;font-size:10px;color:var(--charcoal-muted);margin-bottom:16px;">
        ${segments.map(s => `<span><span style="display:inline-block;width:10px;height:10px;background:${s.color};border-radius:2px;margin-right:4px;"></span>${s.label}</span>`).join('')}
      </div>

      <!-- Line items table -->
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr style="border-bottom:2px solid var(--border-color);text-align:left;">
            <th style="padding:6px 0;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;">${typeof I18n !== 'undefined' ? I18n.t('general.category', 'Category') : 'Category'}</th>
            <th style="padding:6px 0;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;">${typeof I18n !== 'undefined' ? I18n.t('general.amount', 'Amount') : 'Amount'}</th>
            <th style="padding:6px 0;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;">${typeof I18n !== 'undefined' ? I18n.t('general.source', 'Source') : 'Source'}</th>
          </tr>
        </thead>
        <tbody>
          ${(budget.cost_lines || []).map(line => {
            const catName = categoryNames[line.category] || (line.category || '').replace(/_/g, ' ');
            const pctOfTotal = total > 0 ? (((+line.amount)||0)/total*100).toFixed(0) : 0;
            const estUnavail = typeof I18n !== 'undefined' ? I18n.t('general.free', 'Estimate unavailable') : 'Estimate unavailable';
            return `
            <tr style="border-bottom:1px dashed var(--border-color);transition:background 0.15s;" onmouseover="this.style.background='rgba(139,46,31,0.04)'" onmouseout="this.style.background=''">
              <td style="padding:9px 0;">
                <strong>${catName}</strong><br>
                <span style="font-size:11px;color:var(--charcoal-muted);">${escapeHtml(line.assumption || '')}</span>
              </td>
              <td style="padding:9px 0;font-weight:700;">
                ${line.amount !== null && line.amount !== undefined
                  ? `₹${(+line.amount).toLocaleString('en-IN')} <span style="font-size:10px;color:var(--charcoal-muted);font-weight:400;">(${pctOfTotal}%)</span>`
                  : `<span style="color:var(--danger)">${estUnavail}</span>`}
              </td>
              <td style="padding:9px 0;">
                <span class="badge badge-${escapeHtml(line.basis)}">${escapeHtml(line.basis)}</span>
              </td>
            </tr>
          `;}).join('')}
        </tbody>
      </table>
    `;
  },

  // ─── Budget Banner (top of results) ─────────────────
  updateBudgetBanner(budget) {
    if (!budget) return;
    const overBudget = budget.total_cost > budget.total_budget;
    const spendPct = Math.min(100, ((budget.total_cost || 0) / (budget.total_budget || 1)) * 100);
    const diff = Math.abs((budget.total_cost || 0) - (budget.total_budget || 0));

    const costEl   = document.getElementById('banner-total-cost');
    const allocEl  = document.getElementById('banner-allocated');
    const pillEl   = document.getElementById('banner-status-pill');
    const fillEl   = document.getElementById('banner-mini-fill');
    const pctEl    = document.getElementById('banner-pct');

    if (costEl) costEl.textContent = `₹${(budget.total_cost || 0).toLocaleString('en-IN')}`;
    if (allocEl) allocEl.textContent = `₹${(budget.total_budget || 0).toLocaleString('en-IN')}`;
    if (pctEl)  pctEl.textContent = `${spendPct.toFixed(0)}%`;

    if (fillEl) {
      fillEl.style.width = `${spendPct.toFixed(1)}%`;
      fillEl.style.background = overBudget ? 'var(--danger)' : (spendPct > 85 ? 'var(--warn)' : 'var(--forest)');
    }

    if (pillEl) {
      if (overBudget) {
        pillEl.textContent = `▲ Over by ₹${diff.toLocaleString('en-IN')}`;
        pillEl.style.background = 'var(--danger)';
        pillEl.style.color = '#fff';
      } else if (spendPct > 85) {
        pillEl.textContent = `⚠ Tight — ₹${diff.toLocaleString('en-IN')} left`;
        pillEl.style.background = 'var(--warn)';
        pillEl.style.color = '#fff';
      } else {
        pillEl.textContent = `✓ ₹${diff.toLocaleString('en-IN')} remaining`;
        pillEl.style.background = 'rgba(47,125,79,0.12)';
        pillEl.style.color = 'var(--forest)';
      }
    }
  },

  // ─── Budget Slider Debounce ──────────────────────────
  debounceValidateBudget(newAmount) {
    clearTimeout(this.sliderDebounceTimer);
    this.sliderDebounceTimer = setTimeout(async () => {
      if (!this.activeTrip) return;
      const updatedDna = { ...this.activeTrip.dna, budget: { ...this.activeTrip.dna.budget, amount: newAmount } };
      try {
        const res  = await fetch('/api/trips/validate', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ dna: updatedDna, itinerary: this.activeTrip.itinerary })
        });
        const json = await res.json();
        if (json.ok) {
          this.activeTrip.dna         = updatedDna;
          this.activeTrip.budget      = json.data.budget;
          this.activeTrip.feasibility = json.data.feasibility;
          this.renderResults();
          this.updateBudgetBanner(json.data.budget);
        }
      } catch (err) { console.error('[App] budget validate error:', err); }
    }, 280);
  },

  // ─── Replanner ───────────────────────────────────────
  applyReplanPrompt(text) {
    const el = document.getElementById('replan-instruction-input');
    if (el) { el.value = text; this.handleReplan(); }
  },

  async handleReplan() {
    const inputEl = document.getElementById('replan-instruction-input');
    const instruction = inputEl ? inputEl.value.trim() : '';
    if (!instruction || !this.activeTrip) return;

    const diffBox = document.getElementById('replan-diff-output');
    if (diffBox) diffBox.innerHTML = `<div class="loading-overlay" style="padding:24px 0;"><div class="spinner"></div><span>Re-evaluating trip reality constraints…</span></div>`;

    try {
      const res  = await fetch('/api/trips/replan', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          dna: this.activeTrip.dna,
          itinerary: this.activeTrip.itinerary,
          budget: this.activeTrip.budget,
          instruction
        })
      });
      const json = await res.json();

      if (json.clarification_needed) {
        if (diffBox) diffBox.innerHTML = `
          <div style="background:#FEF7E0;padding:14px;border-radius:6px;border:1px solid #FEEFC3;font-size:13px;">
            <strong>Clarification needed:</strong> ${escapeHtml(json.question)}
          </div>`;
        return;
      }

      if (json.ok) {
        const data = json.data;
        this.activeTrip.dna         = data.dna;
        this.activeTrip.itinerary   = data.itinerary;
        this.activeTrip.budget      = data.budget;
        this.activeTrip.feasibility = data.feasibility;

        const diff = data.diff || {};
        if (diffBox) diffBox.innerHTML = `
          <div style="background:var(--ivory);padding:14px;border-radius:6px;border:1px solid var(--border-color);font-size:13px;">
            <strong>Plan Updated:</strong> ${escapeHtml(diff.explanation || 'Changes applied successfully.')}<br>
            ${diff.added && diff.added.length > 0 ? `<div style="color:var(--forest);margin-top:6px;">+ Added: ${diff.added.map(a => escapeHtml(a.name_en)).join(', ')}</div>` : ''}
            ${diff.removed && diff.removed.length > 0 ? `<div style="color:var(--danger);margin-top:4px;">– Removed: ${diff.removed.map(r => escapeHtml(r.name_en)).join(', ')}</div>` : ''}
            ${diff.cost_delta !== undefined && diff.cost_delta !== 0 ? `<div style="color:${diff.cost_delta > 0 ? 'var(--danger)' : 'var(--forest)'};margin-top:4px;">${diff.cost_delta > 0 ? '▲' : '▼'} Budget impact: ₹${Math.abs(diff.cost_delta).toLocaleString('en-IN')}</div>` : ''}
          </div>`;

        // Re-render results and sync the budget slider to new values
        this.renderResults();
        // Sync slider to new allocated budget
        const slider = document.getElementById('budget-slider');
        if (slider && data.budget) {
          slider.min   = Math.max(1000, Math.floor((data.budget.total_cost || 8000) * 0.5));
          slider.max   = Math.ceil((data.budget.total_cost || 8000) * 2.2);
          slider.value = data.budget.total_budget || data.budget.total_cost || 8000;
          const sliderVal = document.getElementById('slider-budget-val');
          if (sliderVal) sliderVal.textContent = `₹${(parseFloat(slider.value)).toLocaleString('en-IN')}`;
        }
        if (inputEl) inputEl.value = '';
        this.toast('Itinerary updated!', 'ok');
      } else {
        if (diffBox) diffBox.innerHTML = `<div style="color:var(--danger);font-size:13px;">${escapeHtml(json.error?.message || 'Replanning failed.')}</div>`;
      }
    } catch (err) {
      console.error('[App] replan error:', err);
      if (diffBox) diffBox.innerHTML = `<div style="color:var(--danger);font-size:13px;">Replanning failed to connect to server.</div>`;
    }
  },

  // ─── Must-Visit & Destination Catalog Picker ────────
  popularDestinationIds: [
    'hampi_virupaksha',
    'mysuru_palace',
    'jog_falls',
    'gokarna_beach',
    'badami_caves',
    'belur_chennakeshava',
    'coorg_madikeri',
    'murudeshwar_temple'
  ],

  isMustVisitPickerOpen: false,

  renderPopularDestinations() {
    const container = document.getElementById('quick-popular-destinations');
    if (!container || !this.allDestinations || !this.allDestinations.length) return;

    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';
    const populars = this.allDestinations.filter(d => this.popularDestinationIds.includes(d.id));

    container.innerHTML = populars.map(d => {
      const isSelected = this.dnaDraft.must_visit.includes(d.id);
      const name = escapeHtml((lang === 'kn') ? (d.name_kn || d.name_en) : d.name_en);
      return `
        <button type="button" class="quick-dest-chip ${isSelected ? 'selected' : ''}" onclick="App.toggleMustVisit('${d.id}')" title="${isSelected ? 'Click to remove' : 'Click to select'}">
          <span style="font-weight:700;">${isSelected ? '✓' : '+'}</span>
          <span>${name}</span>
        </button>
      `;
    }).join('');
  },

  toggleMustVisit(destId) {
    const idx = this.dnaDraft.must_visit.indexOf(destId);
    const dest = this.allDestinations.find(d => d.id === destId);
    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';
    const name = dest ? ((lang === 'kn') ? (dest.name_kn || dest.name_en) : dest.name_en) : destId;

    if (idx >= 0) {
      this.dnaDraft.must_visit.splice(idx, 1);
      const msg = typeof I18n !== 'undefined' ? I18n.t('toast.must_visit_removed', 'Removed from must-visit list') : 'Removed from must-visit list';
      this.toast(`${msg} (📍 ${name})`, '');
    } else {
      this.dnaDraft.must_visit.push(destId);
      const msg = typeof I18n !== 'undefined' ? I18n.t('toast.must_visit_added', 'Added to must-visit list!') : 'Added to must-visit list!';
      this.toast(`${msg} (📍 ${name})`, 'ok');
    }

    this.updateMustVisitDisplay();
    this.renderPopularDestinations();
    if (this.currentRegion) {
      this.renderRegionCards(this.currentRegion);
    }
    if (this.isMustVisitPickerOpen) {
      this.renderMustVisitPicker();
    }
  },

  addMustVisit(destId) {
    this.toggleMustVisit(destId);
  },

  removeMustVisit(index) {
    this.dnaDraft.must_visit.splice(index, 1);
    this.updateMustVisitDisplay();
    this.renderPopularDestinations();
    if (this.currentRegion) {
      this.renderRegionCards(this.currentRegion);
    }
    if (this.isMustVisitPickerOpen) {
      this.renderMustVisitPicker();
    }
  },

  clearAllMustVisit() {
    this.dnaDraft.must_visit = [];
    this.updateMustVisitDisplay();
    this.renderPopularDestinations();
    if (this.currentRegion) {
      this.renderRegionCards(this.currentRegion);
    }
    if (this.isMustVisitPickerOpen) {
      this.renderMustVisitPicker();
    }
    this.toast('Cleared all must-visit destinations.', '');
  },

  // ─── Destination Detail Modal ─────────────────────────
  openDestinationModal(destId) {
    const dest = this.allDestinations.find(d => d.id === destId);
    if (!dest) return;

    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';
    const primaryTitle = escapeHtml((lang === 'kn') ? (dest.name_kn || dest.name_en) : dest.name_en);
    const secondaryTitle = escapeHtml((lang === 'kn') ? dest.name_en : (dest.name_kn || ''));
    const imgUrl = this.getImageUrl(dest);
    const freeLabel = typeof I18n !== 'undefined' ? I18n.t('general.free', 'Free') : 'Free';
    const fee = (dest.entry_fee_inr && dest.entry_fee_inr.value !== null)
      ? `₹${dest.entry_fee_inr.value}`
      : freeLabel;
    const googleMapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${dest.lat},${dest.lng}`;
    const isSelected = this.dnaDraft.must_visit.includes(dest.id);
    const btnText = isSelected
      ? (typeof I18n !== 'undefined' ? I18n.t('general.added', '✓ Selected (Click to Remove)') : '✓ Selected (Click to Remove)')
      : (typeof I18n !== 'undefined' ? I18n.t('map.btn_must_visit', '+ Must-Visit') : '+ Must-Visit');
    const btnClass = isSelected ? 'btn-primary selected' : 'btn-primary';
    const btnTitle = isSelected ? 'Click to remove from must-visit list' : 'Click to add to must-visit list';

    const regionColor = (typeof NammaMap !== 'undefined' && NammaMap.REGION_COLORS)
      ? (NammaMap.REGION_COLORS[dest.region] || '#8B2E1F')
      : '#8B2E1F';

    const chips = (dest.categories || []).map(c => {
      const label = typeof I18n !== 'undefined' ? I18n.getCategoryName(c) : c;
      return `<span class="dest-modal-chip">${label}</span>`;
    }).join('');

    const accessNote = dest.accessibility_notes && dest.accessibility_notes.value
      ? `<div class="dest-modal-access">♿ ${escapeHtml(dest.accessibility_notes.value)}</div>`
      : '';

    const seasonVal = dest.best_season && dest.best_season.value ? escapeHtml(dest.best_season.value) : '';
    const seasonCard = seasonVal
      ? `<div class="dest-modal-stat-card"><div class="dest-modal-stat-label">🌤 Best Season</div><div class="dest-modal-stat-val">${seasonVal}</div></div>`
      : '';

    const credit = dest.image && dest.image.credit ? `<div style="font-size:10px;color:#999;padding:4px 20px;">📸 ${escapeHtml(dest.image.credit)}${dest.image.license ? ' — ' + escapeHtml(dest.image.license) : ''}</div>` : '';

    const html = `
      <div class="dest-modal-img-wrap">
        <img src="${escapeHtml(imgUrl)}" alt="${primaryTitle}" class="dest-modal-img"
          onerror="this.onerror=null;this.src='/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';">
        <div class="dest-modal-img-overlay"></div>
        <span class="dest-modal-region-badge" style="color:${regionColor};border:1.5px solid ${regionColor};">${escapeHtml(dest.region)}</span>
        <div class="dest-modal-title-overlay">
          <h2>${primaryTitle}</h2>
          ${secondaryTitle ? `<div class="dest-modal-kn">${secondaryTitle}</div>` : ''}
        </div>
      </div>
      ${credit}
      <div class="dest-modal-body">
        <div class="dest-modal-chips">${chips}</div>
        <div class="dest-modal-stats-grid">
          <div class="dest-modal-stat-card">
            <div class="dest-modal-stat-label">📍 District</div>
            <div class="dest-modal-stat-val">${escapeHtml(dest.district)}</div>
          </div>
          <div class="dest-modal-stat-card">
            <div class="dest-modal-stat-label">⏱ Visit Duration</div>
            <div class="dest-modal-stat-val">${dest.visit_hours}h</div>
          </div>
          <div class="dest-modal-stat-card">
            <div class="dest-modal-stat-label">🎟 Entry Fee</div>
            <div class="dest-modal-stat-val">${fee}</div>
          </div>
          ${seasonCard}
        </div>
        <p class="dest-modal-desc">${escapeHtml(dest.description || '')}</p>
        ${accessNote}
        <div class="dest-modal-actions">
          <button class="${btnClass}" title="${btnTitle}"
            onclick="App.toggleMustVisit('${dest.id}');App.openDestinationModal('${dest.id}');">
            ${btnText}
          </button>
          <a href="${googleMapsUrl}" target="_blank" rel="noopener noreferrer" class="btn-secondary">
            🧭 Directions
          </a>
        </div>
      </div>
    `;

    const modal = document.getElementById('destination-detail-modal');
    const content = document.getElementById('dest-modal-content');
    if (!modal || !content) return;
    content.innerHTML = html;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  },

  closeDestinationModal(e) {
    // When invoked from the backdrop onclick, only close if user clicked directly on backdrop
    if (e && e.target && !e.target.classList.contains('dest-modal-backdrop')) return;
    const modal = document.getElementById('destination-detail-modal');
    if (modal) modal.classList.remove('active');
    document.body.style.overflow = '';
  },


  toggleMustVisitPicker() {
    const panel = document.getElementById('must-visit-picker-panel');
    const toggleBtn = document.getElementById('btn-toggle-dest-picker');
    if (!panel) return;

    this.isMustVisitPickerOpen = !this.isMustVisitPickerOpen;
    panel.style.display = this.isMustVisitPickerOpen ? 'block' : 'none';

    if (this.isMustVisitPickerOpen) {
      if (toggleBtn) toggleBtn.classList.add('active');
      this.renderMustVisitPicker();
      setTimeout(() => {
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    } else {
      if (toggleBtn) toggleBtn.classList.remove('active');
    }
  },

  filterMustVisitPicker() {
    this.renderMustVisitPicker();
  },

  renderMustVisitPicker() {
    const grid = document.getElementById('picker-dest-grid');
    if (!grid) return;

    const searchInput = document.getElementById('picker-search-input');
    const catSelect = document.getElementById('picker-cat-filter');
    const q = searchInput ? searchInput.value.toLowerCase().trim() : '';
    const cat = catSelect ? catSelect.value : 'all';
    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';

    let list = this.allDestinations || [];
    if (cat !== 'all') {
      list = list.filter(d => (d.categories || []).includes(cat));
    }
    if (q) {
      list = list.filter(d =>
        d.name_en.toLowerCase().includes(q) ||
        (d.name_kn && d.name_kn.includes(q)) ||
        d.district.toLowerCase().includes(q) ||
        d.region.toLowerCase().includes(q)
      );
    }

    const countStatus = document.getElementById('picker-status-count');
    if (countStatus) {
      const selCount = this.dnaDraft.must_visit.length;
      countStatus.textContent = `${list.length} places available • ${selCount} selected`;
    }

    if (list.length === 0) {
      grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 30px; color: var(--charcoal-muted);">No destinations matching your search.</div>`;
      return;
    }

    const freeWord = typeof I18n !== 'undefined' ? I18n.t('general.free', 'Free') : 'Free';

    grid.innerHTML = list.map(d => {
      const isSelected = this.dnaDraft.must_visit.includes(d.id);
      const primaryTitle = escapeHtml((lang === 'kn') ? (d.name_kn || d.name_en) : d.name_en);
      const secondaryTitle = escapeHtml((lang === 'kn') ? d.name_en : (d.name_kn || ''));
      const fee = (d.entry_fee_inr && d.entry_fee_inr.value !== null) ? `₹${d.entry_fee_inr.value}` : freeWord;
      const imgUrl = this.getImageUrl(d);

      return `
        <div class="picker-dest-card ${isSelected ? 'selected' : ''}" onclick="App.openDestinationModal('${d.id}')" tabindex="0">
          <div class="picker-dest-img-wrap">
            <img src="${escapeHtml(imgUrl)}" alt="${primaryTitle}" class="picker-dest-img" loading="lazy" onerror="this.onerror=null;this.src='/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';">
            <span
              class="picker-check-badge ${isSelected ? 'checked' : ''}"
              onclick="event.stopPropagation();App.toggleMustVisit('${d.id}');App.renderMustVisitPicker();"
              title="${isSelected ? 'Remove from must-visit' : 'Add to must-visit'}"
            >${isSelected ? '✓ Selected' : '+ Must-Visit'}</span>
          </div>
          <div class="picker-dest-body">
            <div class="picker-dest-title">${primaryTitle}</div>
            <div style="font-size:11px; color:var(--gold); font-weight:600; margin-bottom:4px;">${secondaryTitle}</div>
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; color:var(--forest);">
              <span>📍 ${escapeHtml(d.district)}</span>
              <span>⏱ ${d.visit_hours}h • 🎟 ${fee}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');
  },

  updateMustVisitDisplay() {
    const listEl = document.getElementById('must-visit-list');
    const badge = document.getElementById('must-visit-count-badge');
    const clearBtn = document.getElementById('btn-clear-must-visit');

    const count = this.dnaDraft.must_visit.length;
    if (badge) {
      badge.textContent = `${count} selected`;
      badge.style.display = count > 0 ? 'inline-block' : 'none';
    }
    if (clearBtn) {
      clearBtn.style.display = count > 0 ? 'inline-block' : 'none';
    }

    if (!listEl) return;
    if (count === 0) {
      listEl.innerHTML = `<span style="font-size:12px; color:var(--charcoal-muted); font-style:italic;">No must-visit destinations selected yet. Tap iconic places above or browse catalog.</span>`;
      return;
    }

    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';
    const items = this.dnaDraft.must_visit.map((id, i) => {
      const dest = this.allDestinations.find(d => d.id === id);
      const name = escapeHtml(dest ? ((lang === 'kn') ? (dest.name_kn || dest.name_en) : dest.name_en) : id);
      const district = dest ? ` (${escapeHtml(dest.district)})` : '';
      return `
        <span class="must-visit-pill">
          <span>📍 ${name}${district}</span>
          <button type="button" onclick="event.stopPropagation(); App.removeMustVisit(${i})" title="Remove">×</button>
        </span>
      `;
    });
    listEl.innerHTML = items.join('');
  },

  // ─── Save / Load Trips ───────────────────────────────
  async saveActiveTrip() {
    if (!this.activeTrip) return;
    try {
      const res  = await fetch('/api/trips/save', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body:    JSON.stringify({
          trip_id:      this.activeTrip.id,
          edit_token:   this.activeEditToken,
          dna:          this.activeTrip.dna,
          itinerary:    this.activeTrip.itinerary,
          cost_summary: this.activeTrip.budget
        })
      });
      const json = await res.json();
      if (json.ok) {
        this.activeTrip.id   = json.data.id;
        this.activeEditToken = json.data.edit_token;
        this.storeTripLocally(json.data.id, this.activeEditToken, this.activeTrip.dna.start_city);
        const savedWord = typeof I18n !== 'undefined' ? I18n.t('toast.trip_saved', 'Journey saved!') : 'Journey saved!';
        this.toast(`${savedWord} ID: ${json.data.id.slice(0,8)}…`, 'ok');
        this.loadSavedTripList();
      } else {
        this.toast('Error saving trip: ' + (json.error?.message || 'Unknown'), 'err');
      }
    } catch (err) {
      this.toast('Error saving trip to database.', 'err');
    }
  },

  storeTripLocally(tripId, token, city) {
    const list = JSON.parse(localStorage.getItem('np_saved_trips') || '[]');
    const idx  = list.findIndex(i => i.id === tripId);
    const entry = { id: tripId, token, city, date: new Date().toLocaleDateString('en-IN') };
    if (idx >= 0) list[idx] = entry;
    else list.unshift(entry);
    localStorage.setItem('np_saved_trips', JSON.stringify(list));
  },

  async loadSavedTripList() {
    const el = document.getElementById('saved-trips-list');
    if (!el) return;
    let list = JSON.parse(localStorage.getItem('np_saved_trips') || '[]');

    // For logged-in users, also fetch server-side trips and merge (dedup by id)
    if (typeof Auth !== 'undefined' && Auth.currentUser && Auth.currentUser.id !== 'guest') {
      try {
        const res  = await fetch('/api/trips?limit=100');
        const json = await res.json();
        if (json.ok && json.data && json.data.trips) {
          const serverTrips = json.data.trips.map(t => ({
            id:    t.id,
            token: '', // server-side trips don't expose raw edit token
            city:  t.dna?.start_city || '',
            date:  new Date(t.created_at).toLocaleDateString('en-IN')
          }));
          // Merge: local entries first (they may have token), then any server trips not in local
          const localIds = new Set(list.map(i => i.id));
          serverTrips.forEach(st => {
            if (!localIds.has(st.id)) list.push(st);
          });
        }
      } catch (_) {}
    }

    // Hide stats bar initially
    const statsBar = document.getElementById('saved-stats-bar');

    if (list.length === 0) {
      if (statsBar) statsBar.style.display = 'none';
      const emptyTitle = typeof I18n !== 'undefined' ? I18n.t('saved.empty_title', 'No Saved Journeys Yet') : 'No Saved Journeys Yet';
      const emptySub   = typeof I18n !== 'undefined' ? I18n.t('saved.empty_sub', 'Create and save your first Karnataka trip to access it here anytime.') : 'Create and save your first Karnataka trip to access it here anytime.';
      const createBtn  = typeof I18n !== 'undefined' ? I18n.t('saved.btn_create', '+ Create My First Journey') : '+ Create My First Journey';
      el.innerHTML = `
        <div style="text-align:center;padding:48px 40px;background:var(--ivory-card);border:1px dashed var(--border-color);border-radius:var(--radius-lg);color:var(--charcoal-muted);">
          <div style="font-size:44px;margin-bottom:14px;">🗺️</div>
          <h3 style="color:var(--charcoal);margin-bottom:8px;font-size:20px;">${emptyTitle}</h3>
          <p style="font-size:14px;margin-bottom:24px;max-width:320px;margin-left:auto;margin-right:auto;">${emptySub}</p>
          <button class="btn-primary" data-nav="journey" onclick="App.switchView('journey')">${createBtn}</button>
        </div>`;
      return;
    }


    // Fetch server-side metadata to enrich cards (days, budget, dna)
    const enriched = await Promise.all(list.map(async item => {
      try {
        const res  = await fetch(`/api/trips/${item.id}`);
        const json = await res.json();
        if (json.ok) return { ...item, meta: json.data };
      } catch (_) {}
      return { ...item, meta: null };
    }));

    // Populate stats bar
    if (statsBar) {
      const withMeta    = enriched.filter(e => e.meta);
      const uniqueCities = [...new Set(withMeta.map(e => e.meta.dna?.start_city).filter(Boolean))];
      const costs       = withMeta.map(e => e.meta.cost_summary?.total_budget || e.meta.cost_summary?.total_cost || 0).filter(v => v > 0);
      const avgCost     = costs.length ? Math.round(costs.reduce((a,b) => a+b, 0) / costs.length) : 0;
      const tripsCountEl  = document.getElementById('stat-trips-count');
      const citiesCountEl = document.getElementById('stat-cities-count');
      const avgCostEl     = document.getElementById('stat-avg-cost');
      if (tripsCountEl)  tripsCountEl.textContent  = list.length;
      if (citiesCountEl) citiesCountEl.textContent = uniqueCities.length || '—';
      if (avgCostEl)     avgCostEl.textContent      = avgCost ? `₹${avgCost.toLocaleString('en-IN')}` : '—';
      statsBar.style.display = 'flex';
    }

    const openBtn   = typeof I18n !== 'undefined' ? I18n.t('saved.btn_open',   'Open')   : 'Open';
    const deleteBtn = typeof I18n !== 'undefined' ? I18n.t('saved.btn_delete', 'Delete') : 'Delete';
    const savedWord = typeof I18n !== 'undefined' ? I18n.t('saved.saved_label','Saved:') : 'Saved:';

    el.innerHTML = enriched.map(item => {
      const meta      = item.meta;
      const dna       = meta?.dna || {};
      const cost      = meta?.cost_summary || {};
      const cityName  = typeof I18n !== 'undefined' ? I18n.getCityName(dna.start_city || item.city) : (dna.start_city || item.city || '—');
      const tripTitle = `Journey from ${escapeHtml(cityName)}`;
      const savedDate = `${savedWord} ${item.date}`;
      const days      = dna.days ? `${dna.days} day${dna.days > 1 ? 's' : ''}` : null;
      const budget    = (cost.total_budget || dna.budget?.amount) ? `₹${((cost.total_budget || dna.budget?.amount)||0).toLocaleString('en-IN')}` : null;
      const pace      = dna.pace ? (dna.pace.charAt(0).toUpperCase() + dna.pace.slice(1)) : null;
      const overB     = cost.is_over_budget;
      const interests = (dna.interests || []).slice(0, 3);

      const chips = [
        days    ? `<span style="background:rgba(47,125,79,0.12);color:var(--forest);font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;">📅 ${days}</span>` : '',
        budget  ? `<span style="background:${overB?'rgba(139,46,31,0.12)':'rgba(201,162,75,0.18)'};color:${overB?'var(--danger)':'var(--gold-dark,#7A5B15)'};font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;">💰 ${budget}</span>` : '',
        pace    ? `<span style="background:rgba(47,47,47,0.07);color:var(--charcoal-soft);font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;">⏱ ${pace}</span>` : '',
        ...interests.map(i => `<span style="background:rgba(139,46,31,0.08);color:var(--earth-red);font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;">${i}</span>`)
      ].filter(Boolean).join('');

      return `
      <div style="background:var(--ivory-card);border:1px solid var(--border-color);border-radius:var(--radius-md);padding:20px 22px;margin-bottom:12px;box-shadow:var(--shadow-xs);transition:box-shadow 0.2s,transform 0.15s;cursor:default;"
           onmouseover="this.style.boxShadow='var(--shadow-md)';this.style.transform='translateY(-1px)'"
           onmouseout="this.style.boxShadow='var(--shadow-xs)';this.style.transform=''">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
          <div style="flex:1;min-width:0;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
              <span style="font-size:22px;">🧭</span>
              <strong style="color:var(--earth-red);font-size:17px;font-family:var(--font-serif);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${tripTitle}</strong>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;">${chips}</div>
            <div style="font-size:11px;color:var(--charcoal-muted);">${savedDate} &bull; <code style="font-size:10px;">${item.id.slice(0,12)}…</code></div>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px;flex-shrink:0;align-items:flex-end;">
            <div style="display:flex;gap:6px;">
              <button class="btn-primary"   style="padding:7px 14px;font-size:12px;" onclick="App.openSavedTrip('${item.id}','${item.token}')">${openBtn}</button>
              <button class="btn-secondary" style="padding:7px 14px;font-size:12px;" onclick="App.exportSavedTrip('${item.id}')" title="Export as CSV">⬇ CSV</button>
              <button class="btn-secondary" style="padding:7px 14px;font-size:12px;color:var(--danger);border-color:var(--danger);" onclick="App.deleteSavedTrip('${item.id}','${item.token}')">${deleteBtn}</button>
            </div>
          </div>
        </div>
      </div>
    `;}).join('');

  },

  async openSavedTrip(tripId, token) {
    try {
      const res  = await fetch(`/api/trips/${tripId}`);
      const json = await res.json();
      if (json.ok) {
        this.activeTrip = {
          id:          json.data.id,
          dna:         json.data.dna,
          itinerary:   json.data.itinerary,
          budget:      json.data.cost_summary,
          feasibility: { score: 85, status: 'feasible', components: [], issues: [], suggestions: [] },
          ai_meta:     { notice: 'Loaded from saved trip' }
        };
        this.activeEditToken = token;
        this.renderResults();
        this.switchView('results');
      } else {
        this.toast('Failed to load saved trip.', 'err');
      }
    } catch (err) {
      this.toast('Network error loading trip.', 'err');
    }
  },

  async deleteSavedTrip(tripId, token) {
    const confirmMsg = typeof I18n !== 'undefined' ? I18n.t('confirm.delete_trip', 'Delete this saved journey? This cannot be undone.') : 'Delete this saved journey? This cannot be undone.';
    if (!confirm(confirmMsg)) return;
    try {
      const res  = await fetch(`/api/trips/${tripId}`, {
        method:  'DELETE',
        headers: { 'X-Edit-Token': token, 'X-CSRFToken': getCsrfToken() }
      });
      const json = await res.json();
      if (json.ok) {
        let list = JSON.parse(localStorage.getItem('np_saved_trips') || '[]');
        list = list.filter(i => i.id !== tripId);
        localStorage.setItem('np_saved_trips', JSON.stringify(list));
        this.loadSavedTripList();
        this.toast(typeof I18n !== 'undefined' ? I18n.t('toast.trip_deleted', 'Journey deleted.') : 'Journey deleted.', '');
      } else {
        this.toast('Error deleting trip: ' + (json.error?.message || 'Unknown'), 'err');
      }
    } catch (err) {
      this.toast('Network error deleting trip.', 'err');
    }
  },

  // ─── Export ──────────────────────────────────────────
  exportCSV() {
    if (!this.activeTrip) { this.toast('No active trip to export.', 'err'); return; }
    if (!this.activeTrip.id) { this.toast('Save your trip first to export as CSV.', ''); return; }
    window.location.href = `/api/trips/${this.activeTrip.id}/export?format=csv`;
  },

  exportSavedTrip(tripId) {
    if (!tripId) { this.toast('Trip ID missing.', 'err'); return; }
    window.location.href = `/api/trips/${tripId}/export?format=csv`;
  },

  async printTrip() {
    if (!this.activeTrip) {
      window.print();
      return;
    }

    if (this.activeTrip.id) {
      window.open(`/api/trips/${this.activeTrip.id}/export?format=html`, '_blank');
      return;
    }

    // Auto-save unsaved trip to generate high-resolution print view
    try {
      this.toast('Opening verified PDF / print preview…', 'ok');
      const csrfToken = getCsrfToken();
      const res = await fetch('/api/trips/save', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body:    JSON.stringify({
          trip_id:      null,
          edit_token:   null,
          dna:          this.activeTrip.dna,
          itinerary:    this.activeTrip.itinerary,
          cost_summary: this.activeTrip.budget || this.activeTrip.cost_summary
        })
      });
      const json = await res.json();
      if (json.ok && json.data && json.data.id) {
        this.activeTrip.id   = json.data.id;
        this.activeEditToken = json.data.edit_token;
        this.storeTripLocally(json.data.id, this.activeEditToken, this.activeTrip.dna?.start_city);
        window.open(`/api/trips/${json.data.id}/export?format=html`, '_blank');
        return;
      }
    } catch (e) {
      console.warn('Auto-save for print fallback:', e);
    }

    window.print();
  },

  toast(message, type = '') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const t = document.createElement('div');
    // Normalize type aliases: 'warn' -> 'warn', 'error' -> 'err', 'success' -> 'ok', 'info' -> ''
    const typeMap = { 'error': 'err', 'success': 'ok', 'info': '', 'warn': 'warn', 'ok': 'ok', 'err': 'err' };
    const normType = typeMap[type] !== undefined ? typeMap[type] : (type || '');
    t.className = `toast ${normType ? `toast-${normType}` : ''}`;
    const icons = { ok: '✓', err: '✕', warn: '⚠', '': 'ℹ' };
    // Icon span is hardcoded; message is inserted as a text node to prevent XSS
    t.innerHTML = `<span>${icons[normType] !== undefined ? icons[normType] : 'ℹ'}</span> `;
    t.appendChild(document.createTextNode(message));
    container.appendChild(t);

    setTimeout(() => {
      t.style.opacity = '0';
      t.style.transform = 'translateX(10px)';
      t.style.transition = 'all 0.3s ease';
      setTimeout(() => t.remove(), 320);
    }, 3500);
  },

  // Alias for backward compatibility — auth.js and other modules call App.showToast()
  showToast(message, type = '') {
    return this.toast(message, type);
  }
};


// ─── Bootstrap ───────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => App.init());
