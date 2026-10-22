/* Auto Selection Mini App — клиент.
   Без сборки и зависимостей: один файл, ES2019, работает в WebView Telegram. */

(() => {
  'use strict';

  const API = '';
  const PAGE_SIZE = 12;

  const PHOTO_BY_BODY = {
    suv: '/assets/car-suv.svg',
    sedan: '/assets/car-sedan.svg',
    minivan: '/assets/car-minivan.svg',
  };

  const FUEL = { petrol: 'Бензин', diesel: 'Дизель', hybrid: 'Гибрид', electric: 'Электро', lpg: 'Газ' };
  const DRIVE = { '2wd': '2WD', '4wd': '4WD', awd: 'AWD', fwd: 'FWD', rwd: 'RWD' };
  const TRANSMISSION = { automatic: 'Автомат', manual: 'Механика', cvt: 'Вариатор', robot: 'Робот' };
  const COLOR = {
    black: 'Чёрный', white: 'Белый', grey: 'Серый', gray: 'Серый', silver: 'Серебристый',
    blue: 'Синий', red: 'Красный', green: 'Зелёный', brown: 'Коричневый', beige: 'Бежевый',
  };

  const state = {
    screen: 'catalog',
    tab: 'catalog',
    card: null,
    config: { bot_username: '', mode: '' },
    catalog: { items: [], total: 0, offset: 0, loaded: false },
    price: { min: '', max: '', chip: null, results: null, total: 0, asked: false },
    calc: { price: '', cc: '2000', year: '2022', region: 'ru', result: null, busy: false },
  };

  const el = {
    view: document.getElementById('view'),
    title: document.getElementById('pageTitle'),
    sub: document.getElementById('pageSub'),
    back: document.getElementById('backBtn'),
    badge: document.getElementById('modeBadge'),
    tabbar: document.getElementById('tabbar'),
    toast: document.getElementById('toast'),
  };

  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  // Вне Telegram SDK всё равно вставляет свои (светлые) переменные — не даём им
  // перекрасить приложение: палитра клиента применяется только внутри клиента.
  const inTelegram = !!(tg && tg.platform && tg.platform !== 'unknown');
  if (inTelegram) document.documentElement.dataset.intelegram = '1';

  // ------------------------------------------------------------------ утилиты

  const esc = (value) =>
    String(value == null ? '' : value).replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch]));

  const num = (value) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return '—';
    return new Intl.NumberFormat('ru-RU').format(Math.round(parsed));
  };

  const usdOf = (item) => {
    if (!item || item.price == null) return null;
    const price = Number(item.price);
    const currency = String(item.currency || 'USD').toUpperCase();
    if (currency === 'KRW') return Math.round(price / 1350);
    if (currency === 'EUR') return Math.round(price * 1.08);
    return Math.round(price);
  };

  const money = (item) => {
    if (!item || item.price == null) return 'цена не указана';
    const currency = String(item.currency || 'USD').toUpperCase();
    // Символ валюты только там, где он точно есть в системном шрифте.
    if (currency === 'USD') return `${num(item.price)} $`;
    if (currency === 'EUR') return `${num(item.price)} €`;
    if (currency === 'KRW') return `${num(item.price)} KRW`;
    return `${num(item.price)} ${currency}`;
  };

  const usdHint = (item) => {
    const currency = String((item && item.currency) || 'USD').toUpperCase();
    if (currency === 'USD') return '';
    const usd = usdOf(item);
    return usd ? `≈ ${num(usd)} $` : '';
  };

  const placeholder = (body) => PHOTO_BY_BODY[String(body || '').toLowerCase()] || PHOTO_BY_BODY.suv;

  const firstPhoto = (item) => {
    const images = (item && item.images) || [];
    const found = images.map(String).find((src) => /^https?:/i.test(src));
    return found || placeholder(item && item.body_type);
  };

  const titleOf = (item) => [item.make, item.model].filter(Boolean).join(' ') || 'Автомобиль';

  const metaOf = (item) =>
    [item.year, item.mileage_km ? `${num(item.mileage_km)} км` : '', FUEL[String(item.fuel || '').toLowerCase()] || '']
      .filter(Boolean)
      .join(' · ');

  function haptic(style) {
    try { tg && tg.HapticFeedback && tg.HapticFeedback.impactOccurred(style || 'light'); } catch (_) {}
  }

  let toastTimer = null;
  function toast(text) {
    el.toast.textContent = text;
    el.toast.hidden = false;
    requestAnimationFrame(() => el.toast.classList.add('is-visible'));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.toast.classList.remove('is-visible');
      setTimeout(() => { el.toast.hidden = true; }, 220);
    }, 2600);
  }

  async function api(path, options) {
    const init = Object.assign({ headers: { accept: 'application/json' } }, options || {});
    const response = await fetch(API + path, init);
    if (!response.ok) {
      let detail = '';
      try { detail = (await response.json()).detail || ''; } catch (_) {}
      const error = new Error(detail || `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }

  // ------------------------------------------------------------------ Telegram

  function initTelegram() {
    if (!inTelegram) { applyTheme(); return; }
    try { tg.ready(); tg.expand(); } catch (_) {}
    applyTheme();
    try {
      if (tg.BackButton) tg.BackButton.onClick(back);
      tg.onEvent('themeChanged', applyTheme);
    } catch (_) {}
  }

  function applyTheme() {
    // Вне Telegram всегда тёмная: SDK вставляет светлую палитру по умолчанию.
    document.documentElement.dataset.theme =
      inTelegram && tg.colorScheme === 'light' ? 'light' : 'dark';
  }

  function syncBackButton() {
    const canGoBack = state.screen === 'card';
    el.back.hidden = !canGoBack;
    try {
      if (tg && tg.BackButton) {
        if (canGoBack) tg.BackButton.show(); else tg.BackButton.hide();
      }
    } catch (_) {}
  }

  // ------------------------------------------------------------------ навигация

  function setTab(tab) {
    state.tab = tab;
    state.screen = tab;
    state.card = null;
    setHash(tab);
    render();
  }

  function openCard(item) {
    state.card = item;
    state.screen = 'card';
    setHash('card/' + item.id);
    render();
  }

  function back() {
    if (state.screen === 'card') {
      state.screen = state.tab;
      state.card = null;
      setHash(state.tab);
      render();
    }
  }

  // Адрес экрана в hash: `#/catalog`, `#/price`, `#/calc`, `#/card/12`.
  // Нужен для deep-link из бота (`/#/card/12`) и для проверки экранов.
  function setHash(value) {
    try {
      const next = '#/' + value;
      if (location.hash !== next) history.replaceState(null, '', next);
    } catch (_) {}
  }

  async function routeFromHash() {
    const raw = (location.hash || '').replace(/^#\/?/, '');
    if (!raw) return;
    const [name, arg] = raw.split('/');
    if (name === 'card' && arg) {
      try {
        const item = await api('/api/listings/' + encodeURIComponent(arg));
        state.card = item;
        state.screen = 'card';
        return;
      } catch (_) { return; }
    }
    if (name === 'price' || name === 'calc' || name === 'catalog') {
      state.tab = name;
      state.screen = name;
    }
  }

  function setChrome(title, sub) {
    el.title.textContent = title;
    el.sub.textContent = sub || '';
    syncBackButton();
    Array.prototype.forEach.call(el.tabbar.querySelectorAll('.tab'), (tab) => {
      tab.classList.toggle('is-active', tab.dataset.tab === state.tab);
    });
  }

  // ------------------------------------------------------------------ экраны

  function skeletons(count) {
    return `<div class="skeleton-list">${'<div class="skeleton skeleton--card"></div>'.repeat(count || 4)}</div>`;
  }

  function errorBlock(message) {
    return `<div class="empty">
      <div class="empty__icon">📡</div>
      <h3>Не удалось загрузить</h3>
      <p>${esc(message || 'Сервис временно недоступен')}</p>
      <button class="btn btn--secondary" type="button" data-action="retry">Повторить</button>
    </div>`;
  }

  function emptyBlock(icon, title, text, action) {
    return `<div class="empty">
      <div class="empty__icon">${icon}</div>
      <h3>${esc(title)}</h3>
      <p>${esc(text)}</p>
      ${action ? `<button class="btn btn--secondary" type="button" data-action="${action}">Изменить фильтры</button>` : ''}
    </div>`;
  }

  function cardMarkup(item) {
    const usd = usdHint(item);
    return `<button class="card" type="button" data-action="card" data-id="${item.id}">
      <span class="card__media">
        <img src="${esc(firstPhoto(item))}" alt="" loading="lazy"
             onerror="this.onerror=null;this.src='${placeholder(item.body_type)}'">
      </span>
      <span class="card__body">
        <span class="card__title">${esc(titleOf(item))}</span>
        <span class="card__meta">${esc(metaOf(item))}</span>
        <span class="card__price">${esc(money(item))}${usd ? `<small>${esc(usd)}</small>` : ''}</span>
      </span>
      <span class="card__chev" aria-hidden="true">›</span>
    </button>`;
  }

  async function renderCatalog() {
    setChrome('Каталог', state.catalog.loaded ? `${state.catalog.total} автомобилей в наличии` : 'Загружаю автомобили…');
    if (!state.catalog.loaded) el.view.innerHTML = skeletons(4);

    try {
      const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(state.catalog.offset), sort: 'new' });
      const data = await api(`/api/listings?${query.toString()}`);
      state.catalog.items = state.catalog.offset ? state.catalog.items.concat(data.items || []) : (data.items || []);
      state.catalog.total = data.total || 0;
      state.catalog.loaded = true;
    } catch (error) {
      el.view.innerHTML = errorBlock(error.message);
      return;
    }

    if (!state.catalog.items.length) {
      el.view.innerHTML = emptyBlock('🚗', 'Пока пусто', 'Как только появятся лоты с источников — они будут здесь.');
      return;
    }

    setChrome('Каталог', `${state.catalog.total} автомобилей в наличии`);
    const hasMore = state.catalog.items.length < state.catalog.total;
    el.view.innerHTML = [
      state.catalog.items.map(cardMarkup).join(''),
      hasMore
        ? '<button class="btn btn--secondary" type="button" data-action="more">Показать ещё</button>'
        : '<p class="note" style="text-align:center;padding:8px 0 4px">Это все лоты в каталоге</p>',
    ].join('');
  }

  function specRows(item) {
    const rows = [
      ['Год', item.year || '—'],
      ['Пробег', item.mileage_km ? `${num(item.mileage_km)} км` : '—'],
      ['Топливо', FUEL[String(item.fuel || '').toLowerCase()] || item.fuel || '—'],
      ['КПП', TRANSMISSION[String(item.transmission || '').toLowerCase()] || item.transmission || '—'],
      ['Привод', DRIVE[String(item.drive || '').toLowerCase()] || item.drive || '—'],
      ['Кузов', item.body_type || '—'],
      ['Объём', item.engine_volume ? `${Number(item.engine_volume).toFixed(1).replace('.', ',')} л` : '—'],
      ['Цвет', COLOR[String(item.color || '').toLowerCase()] || item.color || '—'],
    ];
    return rows
      .map(([label, value]) => `<div class="spec"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`)
      .join('');
  }

  function renderCardScreen(item) {
    if (!item) { setTab('catalog'); return; }
    setChrome(titleOf(item), [item.year, item.source ? String(item.source).toUpperCase() : ''].filter(Boolean).join(' · '));

    const images = ((item.images || []).map(String).filter((src) => /^https?:/i.test(src)));
    const shots = images.length ? images : [placeholder(item.body_type)];
    const usd = usdHint(item);
    const botLink = state.config.bot_username
      ? `https://t.me/${state.config.bot_username}?start=listing_${item.id}`
      : '';

    el.view.innerHTML = `
      <div class="gallery">
        ${shots.map((src, index) => `
          <div class="shot">
            <img src="${esc(src)}" alt="" loading="lazy"
                 onerror="this.onerror=null;this.src='${placeholder(item.body_type)}'">
            ${shots.length > 1 ? `<span class="shot__counter">📷 ${index + 1}/${shots.length}</span>` : ''}
          </div>`).join('')}
      </div>

      <h2 class="detail-head">${esc(titleOf(item))}</h2>
      <p class="detail-sub">${esc([item.year, metaOf(item).split(' · ').slice(1).join(' · ')].filter(Boolean).join(' · '))}</p>

      <div class="price-row">
        <b>${esc(money(item))}</b>
        <span>${esc(usd && String(item.currency || '').toUpperCase() !== 'USD' ? `${usd} по курсу` : 'в долларах')}</span>
      </div>

      <dl class="specs">${specRows(item)}</dl>

      <div class="actions">
        <button class="btn btn--primary" type="button" data-action="calc-from-card" data-id="${item.id}">
          🚚 Рассчитать доставку
        </button>
        ${botLink ? `<a class="btn btn--secondary" href="${esc(botLink)}" target="_blank" rel="noopener">🤖 AI-анализ в боте</a>` : ''}
        ${item.url ? `<a class="btn btn--ghost" href="${esc(item.url)}" target="_blank" rel="noopener">🔗 Открыть у источника</a>` : ''}
      </div>

      <p class="note">VIN ${esc(item.vin || 'не указан')} · источник ${esc(item.source || '—')}.</p>
    `;
  }

  function renderPriceScreen() {
    setChrome('Подбор по цене', 'Диапазон в долларах, как в боте');

    const chips = [
      ['до 30 000 $', '', '30000'],
      ['30 000–45 000 $', '30000', '45000'],
      ['45 000–60 000 $', '45000', '60000'],
      ['60 000+ $', '60000', ''],
    ];

    const resultsHtml = state.price.results === null
      ? ''
      : state.price.results.length
        ? `<div class="section-title">Найдено ${state.price.total}</div>${state.price.results.map(cardMarkup).join('')}`
        : emptyBlock('🔍', 'Ничего не нашлось', 'В этом диапазоне пока нет лотов. Попробуйте шире.', 'reset-price');

    el.view.innerHTML = `
      <div class="panel">
        <div class="chips">
          ${chips.map(([label, min, max], index) => `
            <button class="chip ${state.price.chip === index ? 'is-active' : ''}" type="button"
                    data-action="chip" data-index="${index}" data-min="${min}" data-max="${max}">${esc(label)}</button>`).join('')}
        </div>
        <div class="grid-2">
          <div class="field">
            <label for="minPrice">Цена от, $</label>
            <input id="minPrice" type="number" inputmode="numeric" min="0" placeholder="40000" value="${esc(state.price.min)}">
          </div>
          <div class="field">
            <label for="maxPrice">Цена до, $</label>
            <input id="maxPrice" type="number" inputmode="numeric" min="0" placeholder="70000" value="${esc(state.price.max)}">
          </div>
        </div>
        <button class="btn btn--primary" type="button" data-action="submit-price">Показать автомобили</button>
      </div>
      ${state.price.asked && state.price.results === null ? skeletons(2) : resultsHtml}
      ${!state.price.asked ? '<p class="note" style="text-align:center">Выберите диапазон или введите свой — покажу подходящие лоты.</p>' : ''}
    `;
  }

  function renderCalcScreen() {
    setChrome('Расчёт доставки', 'Корея → Владивосток, «под ключ»');

    const result = state.calc.result;
    const resultHtml = result
      ? `
        <div class="section-title">Смета</div>
        <div class="panel">
          <ul class="breakdown">
            ${(result.components || []).map((row) => `
              <li><span>${esc(row.label || '')}</span><b>${num(row.rub)} ₽</b></li>`).join('')}
          </ul>
        </div>
        <div class="total">
          <span>Итого</span>
          <b>~${num(result.total_rub)} ₽</b>
        </div>
        <p class="note">≈ ${num(result.total_usd)} $ · ${esc(result.age_group || '')} · ${esc(result.util_category || '')} утильсбор.
        ${esc(result.util_note || '')}</p>
        <p class="note" style="margin-top:8px">${esc(result.rates_note || '')}</p>
      `
      : `<p class="note">Укажите цену, объём и год — покажу пошлину, сборы и итог.</p>`;

    el.view.innerHTML = `
      <div class="panel">
        <div class="field">
          <label for="calcPrice">Цена авто, $</label>
          <input id="calcPrice" type="number" inputmode="numeric" min="1" placeholder="18000" value="${esc(state.calc.price)}">
        </div>
        <div class="grid-2">
          <div class="field">
            <label for="calcCc">Объём, см³</label>
            <input id="calcCc" type="number" inputmode="numeric" min="50" max="10000" value="${esc(state.calc.cc)}">
          </div>
          <div class="field">
            <label for="calcYear">Год</label>
            <input id="calcYear" type="number" inputmode="numeric" min="1980" max="2100" value="${esc(state.calc.year)}">
          </div>
        </div>
        <div class="field">
          <label>Юрисдикция</label>
          <div class="segmented">
            <button class="${state.calc.region === 'ru' ? 'is-active' : ''}" type="button" data-action="region" data-region="ru">Россия</button>
            <button class="${state.calc.region === 'by' ? 'is-active' : ''}" type="button" data-action="region" data-region="by">Беларусь</button>
          </div>
        </div>
        <button class="btn btn--primary" type="button" data-action="submit-calc" ${state.calc.busy ? 'disabled' : ''}>
          ${state.calc.busy ? 'Считаю…' : 'Рассчитать'}
        </button>
      </div>
      ${resultHtml}
    `;
  }

  // ------------------------------------------------------------------ рендер

  function render() {
    syncBackButton();
    // На карточке таббар скрыт: CTA иначе уходит под него и не нажимается.
    el.tabbar.hidden = state.screen === 'card';
    if (state.screen === 'catalog') { renderCatalog(); return; }
    if (state.screen === 'price') { renderPriceScreen(); return; }
    if (state.screen === 'calc') { renderCalcScreen(); return; }
    if (state.screen === 'card') { renderCardScreen(state.card); return; }
    setTab('catalog');
  }

  // ------------------------------------------------------------------ данные

  async function submitPrice() {
    const minInput = document.getElementById('minPrice');
    const maxInput = document.getElementById('maxPrice');
    const min = minInput ? minInput.value.trim() : state.price.min;
    const max = maxInput ? maxInput.value.trim() : state.price.max;

    if (min && max && Number(min) > Number(max)) {
      toast('Минимум больше максимума');
      return;
    }

    state.price.min = min;
    state.price.max = max;
    state.price.asked = true;
    state.price.results = null;

    const query = new URLSearchParams({ limit: '20', sort: 'price_asc' });
    if (min) query.set('price_min', min);
    if (max) query.set('price_max', max);

    renderPriceScreen();
    try {
      const data = await api(`/api/listings?${query.toString()}`);
      state.price.results = data.items || [];
      state.price.total = data.total || 0;
    } catch (error) {
      state.price.results = [];
      state.price.total = 0;
      toast(error.message);
    }
    if (state.screen === 'price') renderPriceScreen();
  }

  async function submitCalc(prefill) {
    const priceInput = document.getElementById('calcPrice');
    const ccInput = document.getElementById('calcCc');
    const yearInput = document.getElementById('calcYear');

    const price = Number(prefill != null ? prefill : (priceInput ? priceInput.value : state.calc.price));
    const cc = Number(ccInput ? ccInput.value : state.calc.cc) || 2000;
    const year = Number(yearInput ? yearInput.value : state.calc.year) || 2022;

    if (!price || price <= 0) { toast('Укажите цену автомобиля'); return; }

    state.calc.price = String(price);
    state.calc.cc = String(cc);
    state.calc.year = String(year);
    state.calc.busy = true;
    renderCalcScreen();

    try {
      const body = { price_usd: price, engine_cc: cc, year, region: state.calc.region };
      const result = await api('/api/calc/delivery', {
        method: 'POST',
        headers: { 'content-type': 'application/json', accept: 'application/json' },
        body: JSON.stringify(body),
      });
      state.calc.result = result;
    } catch (error) {
      toast(error.message);
    } finally {
      state.calc.busy = false;
    }
    if (state.screen === 'calc') renderCalcScreen();
  }

  async function loadMore() {
    state.catalog.offset = state.catalog.items.length;
    await renderCatalog();
  }

  async function loadConfig() {
    try {
      const config = await api('/config');
      state.config = Object.assign(state.config, config || {});
      if (state.config.mode) {
        el.badge.hidden = false;
        el.badge.textContent = state.config.mode;
      }
    } catch (_) { /* конфиг не критичен */ }
  }

  // ------------------------------------------------------------------ события

  function bind() {
    document.addEventListener('click', (event) => {
      const target = event.target.closest('[data-action]');
      if (!target) return;
      const action = target.dataset.action;
      haptic();

      if (action === 'tab') { setTab(target.dataset.tab); return; }
      if (action === 'card') {
        const id = Number(target.dataset.id);
        const item = state.catalog.items.find((row) => row.id === id)
          || (state.price.results || []).find((row) => row.id === id);
        if (item) openCard(item);
        return;
      }
      if (action === 'back') { back(); return; }
      if (action === 'more') { loadMore(); return; }
      if (action === 'retry') { state.catalog.loaded = false; render(); return; }
      if (action === 'chip') {
        state.price.chip = Number(target.dataset.index);
        state.price.min = target.dataset.min || '';
        state.price.max = target.dataset.max || '';
        renderPriceScreen();
        return;
      }
      if (action === 'submit-price') { submitPrice(); return; }
      if (action === 'reset-price') {
        state.price = { min: '', max: '', chip: null, results: null, total: 0, asked: false };
        renderPriceScreen();
        return;
      }
      if (action === 'region') {
        state.calc.region = target.dataset.region;
        renderCalcScreen();
        return;
      }
      if (action === 'submit-calc') { submitCalc(); return; }
      if (action === 'calc-from-card') {
        const item = state.card;
        const price = item ? usdOf(item) : null;
        state.screen = 'calc';
        state.tab = 'calc';
        state.calc.result = null;
        if (price) state.calc.price = String(price);
        if (item && item.engine_volume) state.calc.cc = String(Math.round(Number(item.engine_volume) * 1000));
        if (item && item.year) state.calc.year = String(item.year);
        state.card = null;
        setHash('calc');
        render();
        if (price) submitCalc(price);
        return;
      }
    });

    el.back.addEventListener('click', back);

    document.addEventListener('input', (event) => {
      const id = event.target && event.target.id;
      if (id === 'minPrice') state.price.min = event.target.value;
      if (id === 'maxPrice') state.price.max = event.target.value;
      if (id === 'calcPrice') state.calc.price = event.target.value;
      if (id === 'calcCc') state.calc.cc = event.target.value;
      if (id === 'calcYear') state.calc.year = event.target.value;
    });
  }

  // ------------------------------------------------------------------ старт

  initTelegram();
  bind();
  loadConfig();
  routeFromHash().finally(render);
})();
