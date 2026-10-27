/**
 * Namma Payana — Karnataka Atlas Map Controller (v2)
 * Rich photo popups, smooth animations, region/category filtering,
 * route polyline overlay, and robust viewport invalidation.
 */

const KarnatakaMap = {
  map: null,
  markersLayer: null,
  routeLayer: null,
  allDestinations: [],
  currentFilter: { region: 'all', category: 'all' },
  isInitialized: false,

  // Fallback image URLs for key destinations
  FALLBACK_IMAGES: {
    'mysuru_palace':      '/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg',
    'hampi_virupaksha':   '/static/images/Hampi%20%28Virupaksha%20Temple%20%26%20Bazaar%29.jpg',
    'belur_chennakeshava':'/static/images/Belur%20Chennakeshava%20Temple.jpg',
    'jog_falls':          '/static/images/Jog%20Falls%20%28Gerosoppa%29.jpg',
    'coorg_madikeri':     '/static/images/Madikeri%20Fort%20%26%20Raja%27s%20Seat.jpg',
    'default':            '/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg'
  },

  // Region → color mapping
  REGION_COLORS: {
    'South Karnataka':   '#8B2E1F',
    'North Karnataka':   '#C9A24B',
    'Coastal Karnataka': '#2F7D4F',
    'Malnad':            '#1F3528',
    'Central Karnataka': '#A63A28'
  },

  markerMap: {},

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
      return `/static/images/${encodeURIComponent(dest.name_en)}.jpg`;
    }
    if (dest.id) {
      return `/static/images/${encodeURIComponent(dest.id)}.jpg`;
    }
    return this.FALLBACK_IMAGES['default'];
  },

  getPinColor(region) {
    return this.REGION_COLORS[region] || '#8B2E1F';
  },

  init() {
    const mapEl = document.getElementById('leaflet-map');
    if (!mapEl) return;

    if (!this.map) {
      this.map = L.map('leaflet-map', {
        center: [14.6, 75.9],
        zoom: 7,
        minZoom: 6,
        maxZoom: 18,
        zoomControl: true,
        scrollWheelZoom: false
      });
      mapEl.addEventListener('click', () => { if (this.map) this.map.scrollWheelZoom.enable(); });
      mapEl.addEventListener('mouseleave', () => { if (this.map) this.map.scrollWheelZoom.disable(); });

      // Primary: OpenStreetMap Standard with multi-subdomain balancing
      const osmLayer = L.tileLayer(
        'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        {
          subdomains: ['a', 'b', 'c'],
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
          maxZoom: 19
        }
      );

      // Voyager layer: crisp topography and warm colors matching Karnataka tourism
      const cartoLayer = L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        {
          subdomains: 'abcd',
          maxZoom: 20,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        }
      );

      // Alternative: Esri Street Map
      const esriLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        {
          attribution: 'Tiles &copy; Esri &mdash; OpenStreetMap contributors',
          maxZoom: 18
        }
      );

      // Auto-fallback: if OSM fails or is slow, seamlessly fall back to Voyager
      osmLayer.on('tileerror', () => {
        if (!this._hasTileFallback && this.map) {
          this._hasTileFallback = true;
          cartoLayer.addTo(this.map);
        }
      });

      // Add primary layer and layers switcher control
      osmLayer.addTo(this.map);
      const baseMaps = {
        "OpenStreetMap": osmLayer,
        "Karnataka Voyager": cartoLayer,
        "Esri Topography": esriLayer
      };
      L.control.layers(baseMaps, null, { position: 'topright' }).addTo(this.map);

      this.markersLayer = L.featureGroup().addTo(this.map);
      this.routeLayer   = L.featureGroup().addTo(this.map);

      this.bindFilters();
      this.isInitialized = true;

      window.addEventListener('resize', () => this.invalidate());
    }

    this.invalidate();

    if (this.allDestinations.length === 0) {
      this.loadDestinations();
    } else {
      this.applyFilters();
    }
  },

  invalidate() {
    if (!this.map) return;
    // Multiple invalidation passes to accommodate CSS transitions / tab switching
    this.map.invalidateSize(true);
    setTimeout(() => { if (this.map) this.map.invalidateSize(true); }, 120);
    setTimeout(() => { if (this.map) this.map.invalidateSize(true); }, 380);
    setTimeout(() => { if (this.map) this.map.invalidateSize(true); }, 700);
  },

  bindFilters() {
    const regionSel   = document.getElementById('map-region-filter');
    const categorySel = document.getElementById('map-category-filter');
    if (regionSel)   regionSel.addEventListener('change',   (e) => { this.currentFilter.region   = e.target.value; this.applyFilters(); });
    if (categorySel) categorySel.addEventListener('change', (e) => { this.currentFilter.category = e.target.value; this.applyFilters(); });
  },

  async loadDestinations() {
    try {
      const res = await fetch('/api/destinations');
      const json = await res.json();
      if (json.ok) {
        this.allDestinations = json.data.destinations;
        this.applyFilters();
      } else {
        console.error('[NammaMap] Failed to load destinations:', json.error);
      }
    } catch (err) {
      console.error('[NammaMap] Network error loading destinations:', err);
    }
  },

  applyFilters() {
    let filtered = [...this.allDestinations];
    if (this.currentFilter.region !== 'all') {
      filtered = filtered.filter(d => d.region === this.currentFilter.region);
    }
    if (this.currentFilter.category !== 'all') {
      filtered = filtered.filter(d =>
        d.categories && d.categories.includes(this.currentFilter.category)
      );
    }

    const countEl = document.getElementById('map-pins-count');
    if (countEl) {
      const shownLabel = typeof I18n !== 'undefined' ? I18n.t('map.landmarks_shown', 'landmarks shown') : 'landmarks shown';
      countEl.textContent = `${filtered.length} ${shownLabel}`;
    }

    this.plotDestinations(filtered);
  },

  plotDestinations(destinations) {
    if (!this.markersLayer || !this.map) return;
    this.markersLayer.clearLayers();

    if (!destinations || destinations.length === 0) return;

    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';

    destinations.forEach(dest => {
      const pinColor = this.getPinColor(dest.region);
      const imgUrl   = this.getImageUrl(dest);

      // Circle marker (pin)
      const marker = L.circleMarker([dest.lat, dest.lng], {
        radius: 10,
        fillColor: pinColor,
        color: '#FFFFFF',
        weight: 2.5,
        opacity: 1,
        fillOpacity: 0.92
      });

      // Build popup HTML
      const freeLabel = typeof I18n !== 'undefined' ? I18n.t('general.free', 'Free / unavailable') : 'Free / unavailable';
      let fee = (dest.entry_fee_inr && dest.entry_fee_inr.value !== null)
        ? `₹${dest.entry_fee_inr.value}`
        : freeLabel;
      const feeBasis = dest.entry_fee_inr ? dest.entry_fee_inr.basis : 'unknown';
      const googleMapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${dest.lat},${dest.lng}`;
      const descShort = escapeHtml((dest.description || '').slice(0, 120)) + ((dest.description || '').length > 120 ? '…' : '');
      const categories = (dest.categories || []).slice(0, 2).map(c => {
        const catLabel = typeof I18n !== 'undefined' ? I18n.getCategoryName(c) : c;
        return `<span style="background: rgba(201,162,75,0.15); color: #7A5B15; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700; text-transform: uppercase;">${catLabel}</span>`;
      }).join('');

      const primaryTitle = escapeHtml((lang === 'kn') ? (dest.name_kn || dest.name_en) : dest.name_en);
      const secondaryTitle = escapeHtml((lang === 'kn') ? dest.name_en : (dest.name_kn || ''));
      const regionLabel = typeof I18n !== 'undefined' ? I18n.getRegionName(dest.region) : dest.region;
      const stayWord = typeof I18n !== 'undefined' ? I18n.t('general.stay', 'stay') : 'stay';
      const stayLabel = (lang === 'kn') ? `${dest.visit_hours} ಗಂ ವಾಸ್ತವ್ಯ` : `${dest.visit_hours}h ${stayWord}`;
      const btnMustVisit = typeof I18n !== 'undefined' ? I18n.t('map.btn_must_visit', '+ Must-Visit') : '+ Must-Visit';
      const btnAdded = typeof I18n !== 'undefined' ? I18n.t('general.added', '✓ Selected') : '✓ Selected';
      const btnDirections = typeof I18n !== 'undefined' ? I18n.t('map.btn_directions', '🧭 Directions') : '🧭 Directions';
      const isSelected = (typeof App !== 'undefined' && App.dnaDraft && App.dnaDraft.must_visit) ? App.dnaDraft.must_visit.includes(dest.id) : false;
      const initialBtnText = isSelected ? btnAdded : btnMustVisit;
      const initialBtnClass = isSelected ? 'btn-primary selected' : 'btn-primary';

      const popupHtml = `
        <div class="map-popup-card">
          <div class="map-popup-img-wrap">
            <img
              src="${imgUrl}"
              alt="${escapeHtml(dest.name_en)}"
              class="map-popup-img"
              loading="lazy"
              onerror="this.onerror=null;this.src='/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';"
            >
            <div class="map-popup-img-overlay"></div>
            <span style="position:absolute;top:10px;left:10px;background:rgba(255,255,255,0.96);color:${pinColor};border:1.5px solid ${pinColor};padding:3px 10px;border-radius:10px;font-size:10px;font-weight:700;text-transform:uppercase;box-shadow:0 2px 6px rgba(0,0,0,0.15);">
              ${regionLabel}
            </span>
          </div>
          <div class="map-popup-body">
            <div class="map-popup-title">${primaryTitle}</div>
            <div class="map-popup-kn">${secondaryTitle}</div>
            <div style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap;">${categories}</div>
            <div class="map-popup-meta">
              📍 <strong>${escapeHtml(dest.district)}</strong> &bull;
              ⏱️ <strong>${stayLabel}</strong> &bull;
              🎟️ <strong>${fee}</strong>
              <span style="background:rgba(47,79,58,0.1);color:#2F4F3A;padding:1px 6px;border-radius:4px;font-size:9px;font-weight:700;margin-left:4px;">${feeBasis}</span>
            </div>
            <p class="map-popup-desc">${descShort}</p>
            <div class="map-popup-actions">
              <button
                class="${initialBtnClass}"
                style="padding:6px 12px;font-size:12px;flex:1;justify-content:center;"
                onclick="App.toggleMustVisit('${dest.id}'); if (App.dnaDraft.must_visit.includes('${dest.id}')) { this.textContent='${btnAdded}'; this.classList.add('selected'); } else { this.textContent='${btnMustVisit}'; this.classList.remove('selected'); }"
              >
                ${initialBtnText}
              </button>
              <a
                href="${googleMapsUrl}"
                target="_blank"
                rel="noopener noreferrer"
                class="btn-secondary"
                style="padding:6px 12px;font-size:12px;flex:1;justify-content:center;text-align:center;"
              >
                ${btnDirections}
              </a>
            </div>
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml, {
        maxWidth: 310,
        className: 'custom-leaflet-popup'
      });

      // Tooltip on hover (shows name quickly)
      marker.bindTooltip(
        `<strong>${escapeHtml(dest.name_en)}</strong><br><span style="font-size:11px;color:#555;">${escapeHtml(dest.district)} · ${escapeHtml(dest.region)}</span>`,
        { direction: 'top', offset: [0, -12] }
      );

      this.markersLayer.addLayer(marker);
      this.markerMap[dest.id] = marker;
    });

    // Render interactive Landmark Photography Directory
    this.renderAtlasGallery(destinations);

    // Fit bounds to show all visible markers (preserve bounds if route is plotted)
    try {
      const hasActiveRoute = this.routeLayer && this.routeLayer.getLayers().length > 0;
      if (!hasActiveRoute && this.markersLayer.getLayers().length > 0) {
        this.map.fitBounds(this.markersLayer.getBounds(), {
          padding: [40, 40],
          maxZoom: 9
        });
      }
    } catch (e) {
      console.warn('[NammaMap] fitBounds failed:', e);
    }
  },

  resetView() {
    this.currentFilter = { region: 'all', category: 'all' };
    const regionEl   = document.getElementById('map-region-filter');
    const categoryEl = document.getElementById('map-category-filter');
    if (regionEl)   regionEl.value   = 'all';
    if (categoryEl) categoryEl.value = 'all';
    if (this.routeLayer) this.routeLayer.clearLayers();
    this.applyFilters();
    this.invalidate();
    if (this.markersLayer && this.markersLayer.getLayers().length > 0) {
      try {
        this.map.fitBounds(this.markersLayer.getBounds(), { padding: [40, 40], maxZoom: 9 });
      } catch (e) {}
    }
  },

  plotItineraryRoute(itinerary) {
    if (!this.routeLayer || !this.map || !itinerary || !itinerary.days) return;
    this.routeLayer.clearLayers();

    const latlngs = [];
    let stopCounter = 0;

    itinerary.days.forEach(day => {
      (day.stops || []).forEach(stop => {
        const dest = stop.destination;
        if (!dest || dest.lat === undefined) return;

        latlngs.push([dest.lat, dest.lng]);
        stopCounter++;

        // Numbered stop marker
        const dayMarker = L.marker([dest.lat, dest.lng], {
          icon: L.divIcon({
            className: '',
            html: `<div style="
              width:32px;height:32px;border-radius:50%;
              background:linear-gradient(135deg,#8B2E1F,#A63A28);
              color:#fff;font-weight:700;font-size:13px;
              display:flex;align-items:center;justify-content:center;
              border:2.5px solid #C9A24B;box-shadow:0 2px 8px rgba(139,46,31,0.5);
              font-family:'Inter',sans-serif;
            ">${stopCounter}</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
          })
        });

        dayMarker.bindTooltip(
          `<strong>Day ${day.day_number} — Stop ${stop.stop_number}</strong><br>${escapeHtml(dest.name_en)}`,
          { direction: 'top', offset: [0, -16] }
        );
        this.routeLayer.addLayer(dayMarker);
      });
    });

    if (latlngs.length > 1) {
      const polyline = L.polyline(latlngs, {
        color: '#C9A24B',
        weight: 5,
        opacity: 0.85,
        dashArray: '10, 8',
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(this.routeLayer);

      this.map.fitBounds(polyline.getBounds(), { padding: [60, 60] });
    }
  },

  focusDestination(destId) {
    const marker = this.markerMap[destId];
    if (marker && this.map) {
      const latlng = marker.getLatLng();
      this.map.setView(latlng, 12, { animate: true });
      marker.openPopup();
      const mapEl = document.getElementById('leaflet-map');
      if (mapEl) {
        mapEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  },

  renderAtlasGallery(destinations) {
    const grid = document.getElementById('atlas-landmarks-grid');
    const countEl = document.getElementById('atlas-gallery-count');
    if (!grid) return;

    if (countEl) {
      countEl.textContent = `${destinations.length} verified landmarks`;
    }

    if (!destinations || destinations.length === 0) {
      grid.innerHTML = '<div style="color:var(--charcoal-muted);font-size:14px;padding:30px;text-align:center;grid-column:1/-1;">No landmarks match current filters.</div>';
      return;
    }

    const lang = typeof I18n !== 'undefined' ? I18n.currentLang : 'en';

    grid.innerHTML = destinations.map(d => {
      const imgUrl = this.getImageUrl(d);
      const pinColor = this.getPinColor(d.region);
      const primaryTitle = escapeHtml((lang === 'kn') ? (d.name_kn || d.name_en) : d.name_en);
      const secondaryTitle = escapeHtml((lang === 'kn') ? d.name_en : (d.name_kn || ''));
      const freeLabel = typeof I18n !== 'undefined' ? I18n.t('general.free', 'Free') : 'Free';
      const fee = (d.entry_fee_inr && d.entry_fee_inr.value !== null) ? `₹${d.entry_fee_inr.value}` : freeLabel;
      const hoursStr = `${d.visit_hours}h stay`;
      const isSelected = (typeof App !== 'undefined' && App.dnaDraft && App.dnaDraft.must_visit) ? App.dnaDraft.must_visit.includes(d.id) : false;
      const btnMustVisit = typeof I18n !== 'undefined' ? I18n.t('map.btn_must_visit', '+ Must-Visit') : '+ Must-Visit';
      const btnAdded = typeof I18n !== 'undefined' ? I18n.t('general.added', '✓ Selected') : '✓ Selected';
      const btnText = isSelected ? btnAdded : btnMustVisit;
      const btnClass = isSelected ? 'btn-primary selected' : 'btn-primary';

      return `
        <div class="atlas-dest-card" onclick="App.openDestinationModal('${d.id}')" tabindex="0" role="button" title="Click to view full details">
          <div class="atlas-dest-img-wrap">
            <img
              src="${escapeHtml(imgUrl)}"
              alt="${primaryTitle}"
              class="atlas-dest-img"
              loading="lazy"
              onerror="this.onerror=null;this.src='/static/images/Mysuru%20Palace%20%28Amba%20Vilas%29.jpg';"
            >
            <span class="atlas-dest-badge" style="color:${pinColor};border:1.5px solid ${pinColor};">
              ${escapeHtml(d.region)}
            </span>
          </div>
          <div class="atlas-dest-body">
            <div class="atlas-dest-title">${primaryTitle}</div>
            <div class="atlas-dest-kn">${secondaryTitle}</div>
            <p class="atlas-dest-desc">${escapeHtml(d.description || '')}</p>
            <div style="font-size:12px;color:var(--forest);font-weight:600;margin-bottom:12px;">
              📍 ${escapeHtml(d.district)} &bull; ⏱ ${hoursStr} &bull; 🎟 ${fee}
            </div>
            <div class="atlas-dest-actions" onclick="event.stopPropagation()">
              <button
                type="button"
                class="btn-secondary"
                style="padding:6px 12px;font-size:12px;flex:1;"
                onclick="KarnatakaMap.focusDestination('${d.id}')"
                title="Focus this destination on the map"
              >
                📍 Locate
              </button>
              <button
                type="button"
                class="${btnClass}"
                style="padding:6px 12px;font-size:12px;flex:1;"
                onclick="App.toggleMustVisit('${d.id}'); if (App.dnaDraft.must_visit.includes('${d.id}')) { this.textContent='${btnAdded}'; this.classList.add('selected'); } else { this.textContent='${btnMustVisit}'; this.classList.remove('selected'); }"
              >
                ${btnText}
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }
};
