const globalPhotoSelection = new Set();
﻿const apiBase = "/api/v1";
let previewUrls = [];
let uploadedQueryFiles = [];
let selectedUploadedQueryFileSigns = new Set();
let gpsCenter = null;
let standardPhotoPool = [];
let selectedStandardPhotoIds = new Set();
let searchBusy = false;
let gpsBusy = false;
let gpsElementBusy = false;
let downloadBusy = false;
let trashBusy = false;
let logoutBusy = false;
let currentAuthState = null;
let adminPolicyConfigToken = "";
let adminPolicyConfigStore = null;
let adminPolicyConfigPath = "";
let adminPolicyConfigBusy = false;
let adminPolicyConfigDirty = false;
let policyEditorEscBound = false;
let searchRequestActive = false;
let searchRequestStartedAt = 0;
let searchRequestTimer = 0;
let searchWarmReady = false;
let searchWarmMessage = "系统预热中，请稍候...";
let latestScanProgress = null;
let indexCompactBusy = false;
let latestIndexCompactState = null;
let scanTriggerBusy = false;
let activeScanTrigger = "";
// 部署时改成自己的参考点坐标，用于「距参考点」排序
const REFERENCE_GPS = { lat: 0, lon: 0 };
const RESULT_SORT_DEFAULT = "exif_desc";
const FILE_NAME_COLLATOR = new Intl.Collator("zh-CN", { numeric: true, sensitivity: "base" });
let currentResultsData = { stage: 0, total: 0, results: [], debug: null };
let searchSessionState = {
  searchId: "",
  batch: 1,
  totalBatches: 1,
  total: 0,
  batchSize: 55,
};
const SEARCH_BATCH_CACHE_LIMIT_DESKTOP = 8;
const SEARCH_BATCH_CACHE_LIMIT_MOBILE = 5;
const SEARCH_BATCH_PREFETCH_AHEAD_DESKTOP = 2;
const SEARCH_BATCH_PREFETCH_AHEAD_MOBILE = 1;
const SEARCH_BATCH_NAV_COOLDOWN_MS = 90;
let searchBatchCache = new Map();
let searchBatchInflight = new Map();
let searchBatchNavToken = 0;
let searchBatchQueuedTarget = 0;
let searchBatchLastNavTs = 0;
let resultLightboxItems = [];
let resultLightboxActive = false;
let resultLightboxIndex = 0;
let resultLightboxTouchStartX = 0;
let resultLightboxTouchStartY = 0;
let resultLightboxTouchLastX = 0;
let resultLightboxTouchLastY = 0;
let resultLightboxTouchStartTs = 0;
let resultLightboxTouchMoved = false;
let resultLightboxTouchHorizontal = false;
let resultLightboxTouchAxis = "";
let resultLightboxTouchBlockClickUntil = 0;
let resultLightboxPinchActive = false;
let resultLightboxPinchStartDistance = 0;
let resultLightboxPinchStartScale = 1;
let resultLightboxPinchStartCenterX = 0;
let resultLightboxPinchStartCenterY = 0;
let resultLightboxPinchStartOffsetX = 0;
let resultLightboxPinchStartOffsetY = 0;
let resultLightboxPanActive = false;
let resultLightboxPanStartX = 0;
let resultLightboxPanStartY = 0;
let resultLightboxPanStartOffsetX = 0;
let resultLightboxPanStartOffsetY = 0;
let resultLightboxZoomScale = 1;
let resultLightboxZoomOffsetX = 0;
let resultLightboxZoomOffsetY = 0;
let resultLightboxRenderToken = 0;
let resultLightboxClosingUntil = 0;
let resultLightboxLastStep = 1;
let resultLightboxLastMoveTs = 0;
let resultLightboxFastMoveStreak = 0;
let resultLightboxPendingOffsetX = 0;
let resultLightboxPendingOffsetY = 0;
let resultLightboxPendingAnimate = false;
let resultLightboxOffsetRaf = 0;
let resultLightboxTrackAnimateState = null;
const SYSTEM_SETTINGS_OPEN_KEY = "photo_search_system_settings_open";
const LIGHTBOX_TRIGGER_KEY = "photo_search_lightbox_trigger";
const LIGHTBOX_QUALITY_KEY = "photo_search_lightbox_quality";
const LIGHTBOX_QUALITY_DEFAULT = 720;
const LIGHTBOX_QUALITY_OPTIONS = [512, 720, 896, 1024];
const SYSTEM_STATUS_OPEN_KEY = "photo_search_system_status_open";
const USAGE_GUIDE_OPEN_KEY = "photo_search_usage_guide_open";
const SEARCH_RESULTS_OPEN_KEY = "photo_search_results_open";
const PC_SIDEBAR_COLLAPSED_KEY = "photo_search_pc_sidebar_collapsed";
const PC_MAIN_HIDDEN_KEY = "photo_search_pc_main_hidden";
const PC_SYSTEM_SETTINGS_FULLSCREEN_KEY = "photo_search_pc_system_settings_fullscreen";
const PANEL_AUTO_COLLAPSE_DISABLED_KEY = "photo_search_panel_auto_collapse_disabled";
const PANEL_AUTO_COLLAPSE_SECONDS_KEY = "photo_search_panel_auto_collapse_idle_ms";
const PANEL_AUTO_COLLAPSE_IDLE_MS_DEFAULT = 30000;
const PANEL_AUTO_COLLAPSE_IDLE_OPTIONS = [15000, 30000, 40000, 60000];
const MOBILE_UI_FONT_SIZE_KEY = "photo_search_mobile_ui_font_size";
const MOBILE_UI_FONT_SIZE_DEFAULT = "md";
const MOBILE_UI_FONT_SIZE_OPTIONS = ["sm", "smd", "md", "lg", "xl"];
const LIGHTBOX_PRELOAD_RADIUS_DESKTOP = 2;
const LIGHTBOX_PRELOAD_RADIUS_MOBILE = 1;
const LIGHTBOX_CACHE_MB_DESKTOP = 128;
const LIGHTBOX_CACHE_MB_MOBILE = 64;
const LIGHTBOX_CACHE_PROTECTED_RADIUS = 2;
const LIGHTBOX_PRELOAD_CONCURRENCY = 2;
const LIGHTBOX_PRELOAD_QUICK_WINDOW_MS = 280;
const LIGHTBOX_PRELOAD_QUICK_STREAK = 2;
const LIGHTBOX_PRELOAD_PRIORITY = {
  current: 120,
  next: 100,
  near: 80,
  far: 60,
};
const LIGHTBOX_ZOOM_MIN = 1;
const LIGHTBOX_ZOOM_MAX = 4;
const RESULT_ACTION_FLASH_MS = 1300;
const RESULT_ACTION_ERROR_FLASH_MS = 1700;
let lightboxImageCache = new Map();
let lightboxCacheBytes = 0;
let lightboxPreloadQueue = [];
let lightboxPreloadActive = new Map();
let elementHeaderFitTimer = 0;
let elementGridFitTimer = 0;
let mobileSortBarResizeTimer = 0;
let panelAutoCollapseTimer = 0;
let panelAutoCollapseBound = false;
let resultActionPendingKeys = new Set();
let resultActionFlashMap = new Map();
let faceModeState = "or";
let textModeState = "and";
const SUPPORTED_IMAGE_SUFFIXES = ["jpg", "jpeg", "png", "bmp", "webp", "heic", "heif"];
const SUPPORTED_IMAGE_SUFFIX_QUERY = SUPPORTED_IMAGE_SUFFIXES.join(" ");
const SERVER_GLOBAL_SORT_MODES = new Set(["face_count_desc", "face_count_asc", "face_count_exact"]);
const FACE_COUNT_EXACT_DEFAULT = 1;
const PRE_DELETED_DIR = "pre_deleted";
let exifRepairDirs = [];
let exifRepairTargetDir = "";
let exifRepairTaskId = "";
const DIR_PICKER_MODE_EXIF_REPAIR = "exif_repair";
let dirPickerState = {
  open: false,
  mode: "",
  path: "",
  parent: "",
  roots: [],
  subdirs: [],
};
let dirPickerEscBound = false;
let textAllTypesPrevQuery = "";
let textAllTypesPrevMode = "and";
let lightboxRotationMap = new Map();
let pcSidebarCollapsed = false;
let pcMainHidden = false;
let pcSystemSettingsFullscreen = false;
let panelAutoCollapseIdleMs = PANEL_AUTO_COLLAPSE_IDLE_MS_DEFAULT;
let panelAutoCollapseDisabled = false;
let mobileUiFontSize = MOBILE_UI_FONT_SIZE_DEFAULT;
let mobileViewportInsetRaf = 0;
let mobileViewportInsetBound = false;
const MOBILE_VV_INSET_MAX_PX = 96;
const MOBILE_VV_KEYBOARD_INSET_MIN_PX = 150;
const MOBILE_VV_KEYBOARD_HEIGHT_RATIO = 0.74;
const INPUT_NON_TEXT_TYPES = new Set(["button", "submit", "reset", "checkbox", "radio", "file", "image", "range", "color", "hidden"]);

function setSearchStatusText(text) {
  const mainEl = document.getElementById("searchStatus");
  if (!mainEl) return;

  const raw = text == null ? "" : String(text);
  let summary = raw.trim();
  let debug = "";

  const debugFlag = "调试[";
  const bar = "｜";
  const debugFlagIndex = raw.indexOf(debugFlag);
  if (debugFlagIndex > 0) {
    const sepIndex = raw.lastIndexOf(bar, debugFlagIndex);
    if (sepIndex > -1) {
      summary = raw.slice(0, sepIndex).trim();
      debug = raw.slice(sepIndex).trim().replace(/^｜\s*/, "");
    }
  }

  mainEl.textContent = summary;

  const debugWrap = document.getElementById("searchStatusDebugWrap");
  const debugTitle = document.getElementById("searchStatusDebugTitle");
  const debugTextEl = document.getElementById("searchStatusDebug");
  if (!debugWrap || !debugTextEl) return;

  if (!debug) {
    debugWrap.hidden = true;
    debugWrap.open = false;
    debugTextEl.textContent = "";
    if (debugTitle) debugTitle.textContent = "查看调试详情";
    return;
  }

  debugTextEl.textContent = debug;
  if (debugTitle) {
    const firstPart = String(debug).split(` ${bar} `)[0] || "调试";
    debugTitle.textContent = `查看调试详情（${firstPart}）`;
  }
  debugWrap.hidden = false;
}

function setText(id, text) {
  if (id === "searchStatus") {
    setSearchStatusText(text);
    return;
  }
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function getSearchElapsedSeconds() {
  if (!searchRequestActive || !searchRequestStartedAt) return 0;
  return Math.max(0, Math.floor((Date.now() - searchRequestStartedAt) / 1000));
}

function formatSearchRunningStatus() {
  return `正在搜索，总用时：${getSearchElapsedSeconds()}秒`;
}

function formatSearchRunningButtonText() {
  return `搜索中 ${getSearchElapsedSeconds()}秒`;
}

function refreshSearchRunningUi() {
  if (!searchRequestActive) return;
  setSearchStatusText(formatSearchRunningStatus());
  updateActionButtons();
}

function stopSearchElapsedTicker() {
  searchRequestActive = false;
  searchRequestStartedAt = 0;
  if (searchRequestTimer) {
    window.clearInterval(searchRequestTimer);
    searchRequestTimer = 0;
  }
}

function startSearchElapsedTicker() {
  stopSearchElapsedTicker();
  searchRequestActive = true;
  searchRequestStartedAt = Date.now();
  refreshSearchRunningUi();
  searchRequestTimer = window.setInterval(() => {
    if (!searchRequestActive) {
      stopSearchElapsedTicker();
      return;
    }
    refreshSearchRunningUi();
  }, 1000);
}

function today() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function initMainTitleToday() {
  const el = document.getElementById("mainTitle");
  if (!el) return;
  const baseTitle = (el.dataset.baseTitle || el.textContent || "").trim() || "Sofia照片多要素搜索器";
  el.dataset.baseTitle = baseTitle;
  el.innerHTML = `${escapeHtml(baseTitle)}<sub class="title-today-sub">${today()}</sub>`;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let idx = 0;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  const fixed = size >= 100 || idx === 0 ? 0 : size >= 10 ? 1 : 2;
  return `${size.toFixed(fixed)} ${units[idx]}`;
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function scrollToBottom() {
  const doc = document.documentElement;
  const body = document.body;
  const maxHeight = Math.max(
    doc ? doc.scrollHeight : 0,
    body ? body.scrollHeight : 0,
  );
  window.scrollTo({ top: maxHeight, behavior: "smooth" });
}

function initBackToTopButton() {
  const topBtn = document.getElementById("btnBackToTop");
  const bottomBtn = document.getElementById("btnBackToBottom");
  const desktopBar = document.getElementById("pcBottomQuickBar");
  const topDesktopBtn = document.getElementById("btnBackToTopDesktop");
  const bottomDesktopBtn = document.getElementById("btnBackToBottomDesktop");
  if (!topBtn && !bottomBtn && !desktopBar) return;
  const update = () => {
    const doc = document.documentElement;
    const body = document.body;
    const y = window.scrollY || (doc ? doc.scrollTop : 0) || 0;
    const viewportHeight = window.innerHeight || (doc ? doc.clientHeight : 0) || 0;
    const scrollHeight = Math.max(
      doc ? doc.scrollHeight : 0,
      body ? body.scrollHeight : 0,
    );
    const distanceToBottom = Math.max(0, scrollHeight - (y + viewportHeight));
    const canUp = y > 260;
    const canDown = distanceToBottom > 260;
    if (topBtn) topBtn.classList.toggle("visible", canUp);
    if (bottomBtn) bottomBtn.classList.toggle("visible", canDown);

    if (desktopBar) {
      const showDesktopBar = !isMobileViewport() && (canUp || canDown);
      desktopBar.classList.toggle("visible", showDesktopBar);
    }
    if (topDesktopBtn) topDesktopBtn.disabled = !canUp;
    if (bottomDesktopBtn) bottomDesktopBtn.disabled = !canDown;
  };
  window.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update, { passive: true });
  update();
}

function normalizeLoopIndex(index, total) {
  if (!total) return 0;
  return ((index % total) + total) % total;
}

function isMobileViewport() {
  return window.matchMedia && window.matchMedia("(max-width: 768px)").matches;
}

function hasCoarsePointer() {
  return !!(window.matchMedia && window.matchMedia("(hover: none) and (pointer: coarse)").matches);
}

function isActualMobileViewport() {
  return isMobileViewport();
}

function isNarrowDesktopViewport() {
  return false;
}

function syncResponsiveViewportMode() {
  const root = document.documentElement;
  if (root) {
    root.classList.toggle("actual-mobile-viewport", isActualMobileViewport());
    root.classList.toggle("narrow-desktop-viewport", isNarrowDesktopViewport());
  }
  if (!document.body) return;
  document.body.classList.toggle("actual-mobile-viewport", isActualMobileViewport());
  document.body.classList.toggle("narrow-desktop-viewport", isNarrowDesktopViewport());
}

function shouldHideTopSearchBatchRow() {
  return isActualMobileViewport();
}

function syncTopSearchBatchRowVisibility() {
  const row = document.getElementById("searchActionRow");
  if (!row) return;
  row.hidden = shouldHideTopSearchBatchRow();
}

function normalizeMobileUiFontSize(value) {
  const size = String(value || "").trim().toLowerCase();
  return MOBILE_UI_FONT_SIZE_OPTIONS.includes(size) ? size : MOBILE_UI_FONT_SIZE_DEFAULT;
}

function syncMobileUiFontSizeButtons() {
  const idMap = {
    sm: "btnMobileFontSm",
    smd: "btnMobileFontSmd",
    md: "btnMobileFontMd",
    lg: "btnMobileFontLg",
    xl: "btnMobileFontXl",
  };
  Object.entries(idMap).forEach(([size, id]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    const active = size === mobileUiFontSize;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function applyMobileUiFontSize(value, options = {}) {
  mobileUiFontSize = normalizeMobileUiFontSize(value);
  document.documentElement.setAttribute("data-mobile-ui-font-size", mobileUiFontSize);
  syncMobileUiFontSizeButtons();
  window.setTimeout(fitElementGridForMobile, 0);
  if (options.persist !== false) {
    localStorage.setItem(MOBILE_UI_FONT_SIZE_KEY, mobileUiFontSize);
  }
}

function setMobileUiFontSize(value) {
  applyMobileUiFontSize(value, { persist: true });
}

function initMobileUiFontSizeControls() {
  const saved = localStorage.getItem(MOBILE_UI_FONT_SIZE_KEY);
  const initial = saved || MOBILE_UI_FONT_SIZE_DEFAULT;
  applyMobileUiFontSize(initial, { persist: false });
  if (!saved) {
    localStorage.setItem(MOBILE_UI_FONT_SIZE_KEY, mobileUiFontSize);
  }
}

function refreshMobileNavbarOffset() {
  const root = document.documentElement;
  if (!root) return;
  if (!isMobileViewport()) {
    root.style.removeProperty("--mobile-nav-offset");
    root.style.removeProperty("--sticky-toolbar-top");
    return;
  }
  const nav = document.querySelector(".navbar");
  if (!nav) return;
  const navHeight = Math.max(0, Math.round(nav.getBoundingClientRect().height));
  if (!navHeight) return;
  const offset = `${navHeight}px`;
  root.style.setProperty("--mobile-nav-offset", offset);
  root.style.removeProperty("--sticky-toolbar-top");
}

function clampMobileViewportInset(value) {
  const n = Number(value || 0);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(MOBILE_VV_INSET_MAX_PX, Math.round(n)));
}

function isEditableField(el) {
  if (!el || !(el instanceof HTMLElement)) return false;
  if (el.isContentEditable) return true;
  const tag = String(el.tagName || "").toUpperCase();
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag !== "INPUT") return false;
  const type = String(el.getAttribute("type") || "text").trim().toLowerCase();
  return !INPUT_NON_TEXT_TYPES.has(type);
}

function syncMobileVisualViewportInsets() {
  const root = document.documentElement;
  if (!root) return;
  if (!isActualMobileViewport()) {
    root.style.setProperty("--mobile-vv-top-offset", "0px");
    root.style.setProperty("--mobile-vv-bottom-offset", "0px");
    return;
  }
  const vv = window.visualViewport;
  if (!vv) {
    root.style.setProperty("--mobile-vv-top-offset", "0px");
    root.style.setProperty("--mobile-vv-bottom-offset", "0px");
    return;
  }
  const innerHeight = Math.max(0, Number(window.innerHeight || 0));
  const vvHeight = Math.max(0, Number(vv.height || 0));
  const rawTop = Math.max(0, Number(vv.offsetTop || 0));
  const rawBottom = Math.max(0, innerHeight > 0 ? innerHeight - (vvHeight + rawTop) : 0);
  const keyboardByInset = rawBottom >= MOBILE_VV_KEYBOARD_INSET_MIN_PX;
  const keyboardByHeight = innerHeight > 0 && vvHeight > 0 && vvHeight <= innerHeight * MOBILE_VV_KEYBOARD_HEIGHT_RATIO;
  const keyboardLikelyOpen = isEditableField(document.activeElement) && (keyboardByInset || keyboardByHeight);
  const bottomInset = keyboardLikelyOpen ? 0 : clampMobileViewportInset(rawBottom);
  root.style.setProperty("--mobile-vv-top-offset", "0px");
  root.style.setProperty("--mobile-vv-bottom-offset", `${bottomInset}px`);
}

function scheduleMobileVisualViewportInsetsSync() {
  if (mobileViewportInsetRaf) return;
  mobileViewportInsetRaf = window.requestAnimationFrame(() => {
    mobileViewportInsetRaf = 0;
    syncMobileVisualViewportInsets();
  });
}

function bindMobileVisualViewportInsetsSync() {
  if (mobileViewportInsetBound) return;
  mobileViewportInsetBound = true;
  const vv = window.visualViewport;
  if (vv) {
    vv.addEventListener("resize", scheduleMobileVisualViewportInsetsSync, { passive: true });
    vv.addEventListener("scroll", scheduleMobileVisualViewportInsetsSync, { passive: true });
  }
  window.addEventListener("focusin", scheduleMobileVisualViewportInsetsSync);
  window.addEventListener("focusout", () => {
    window.setTimeout(scheduleMobileVisualViewportInsetsSync, 80);
  });
  scheduleMobileVisualViewportInsetsSync();
}

function isDesktopSidebarViewport() {
  return window.matchMedia && window.matchMedia("(min-width: 900px)").matches;
}

function hasSearchResultsForPcSidebarToggle() {
  if (!currentResultsData || typeof currentResultsData !== "object") return false;
  if (Array.isArray(currentResultsData.results) && currentResultsData.results.length > 0) return true;
  return Number(currentResultsData.total || 0) > 0;
}

function refreshPcSidebarLayout() {
  const desktop = isDesktopSidebarViewport();
  const shouldSettingsFullscreen = !!(pcSystemSettingsFullscreen && desktop);
  const shouldMainHidden = !!(!shouldSettingsFullscreen && pcMainHidden && desktop);
  const shouldSidebarCollapse = !!(!shouldSettingsFullscreen && pcSidebarCollapsed && desktop && !shouldMainHidden);
  document.body.classList.toggle("pc-sidebar-collapsed", shouldSidebarCollapse);
  document.body.classList.toggle("pc-main-collapsed", shouldMainHidden);
  document.body.classList.toggle("pc-settings-fullscreen", shouldSettingsFullscreen);

  const btn = document.getElementById("btnTogglePcSidebar");
  if (btn) {
    const visible = desktop && !shouldMainHidden && !shouldSettingsFullscreen && (hasSearchResultsForPcSidebarToggle() || pcSidebarCollapsed);
    btn.hidden = !visible;
    btn.setAttribute("aria-pressed", pcSidebarCollapsed ? "true" : "false");
    btn.textContent = pcSidebarCollapsed ? "显示侧栏" : "隐藏侧栏";
    btn.title = pcSidebarCollapsed ? "显示左侧搜索面板" : "隐藏左侧搜索面板";
  }

  const fullBtn = document.getElementById("btnToggleSidebarFullscreen");
  if (fullBtn) {
    const visible = desktop && !shouldSettingsFullscreen;
    fullBtn.hidden = !visible;
    fullBtn.setAttribute("aria-pressed", shouldMainHidden ? "true" : "false");
    fullBtn.textContent = shouldMainHidden ? "恢复界面" : "全屏";
    fullBtn.title = shouldMainHidden ? "恢复正常双栏界面" : "隐藏主栏，侧栏全屏显示";
  }

  const settingsFullBtn = document.getElementById("btnToggleSystemSettingsFullscreen");
  if (settingsFullBtn) {
    settingsFullBtn.hidden = !desktop;
    settingsFullBtn.setAttribute("aria-pressed", shouldSettingsFullscreen ? "true" : "false");
    settingsFullBtn.textContent = shouldSettingsFullscreen ? "恢复界面" : "全屏";
    settingsFullBtn.title = shouldSettingsFullscreen ? "恢复正常双栏界面" : "仅显示系统设置，隐藏侧栏和搜索结果";
  }
}

function setPcSidebarCollapsed(collapsed, options = {}) {
  pcSidebarCollapsed = !!collapsed;
  if (pcSidebarCollapsed && pcMainHidden) {
    pcMainHidden = false;
    localStorage.setItem(PC_MAIN_HIDDEN_KEY, "0");
  }
  if (pcSidebarCollapsed && pcSystemSettingsFullscreen) {
    pcSystemSettingsFullscreen = false;
    localStorage.setItem(PC_SYSTEM_SETTINGS_FULLSCREEN_KEY, "0");
  }
  if (!options.skipPersist) {
    localStorage.setItem(PC_SIDEBAR_COLLAPSED_KEY, pcSidebarCollapsed ? "1" : "0");
  }
  refreshPcSidebarLayout();
}

function setPcMainHidden(hidden, options = {}) {
  pcMainHidden = !!hidden;
  if (pcMainHidden && pcSidebarCollapsed) {
    pcSidebarCollapsed = false;
    localStorage.setItem(PC_SIDEBAR_COLLAPSED_KEY, "0");
  }
  if (pcMainHidden && pcSystemSettingsFullscreen) {
    pcSystemSettingsFullscreen = false;
    localStorage.setItem(PC_SYSTEM_SETTINGS_FULLSCREEN_KEY, "0");
  }
  if (!options.skipPersist) {
    localStorage.setItem(PC_MAIN_HIDDEN_KEY, pcMainHidden ? "1" : "0");
  }
  refreshPcSidebarLayout();
  if (pcMainHidden && !options.skipScroll && isDesktopSidebarViewport()) {
    window.setTimeout(() => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }, 20);
  }
}

function setPcSystemSettingsFullscreen(fullscreen, options = {}) {
  pcSystemSettingsFullscreen = !!fullscreen;
  if (pcSystemSettingsFullscreen && pcMainHidden) {
    pcMainHidden = false;
    localStorage.setItem(PC_MAIN_HIDDEN_KEY, "0");
  }
  if (pcSystemSettingsFullscreen && pcSidebarCollapsed) {
    pcSidebarCollapsed = false;
    localStorage.setItem(PC_SIDEBAR_COLLAPSED_KEY, "0");
  }
  if (!options.skipPersist) {
    localStorage.setItem(PC_SYSTEM_SETTINGS_FULLSCREEN_KEY, pcSystemSettingsFullscreen ? "1" : "0");
  }
  refreshPcSidebarLayout();
  if (pcSystemSettingsFullscreen && !options.skipScroll && isDesktopSidebarViewport()) {
    window.setTimeout(() => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }, 20);
  }
}

function togglePcSidebar() {
  setPcSidebarCollapsed(!pcSidebarCollapsed);
}

function toggleSidebarFullscreen() {
  setPcMainHidden(!pcMainHidden);
}

function toggleSystemSettingsFullscreen() {
  setPcSystemSettingsFullscreen(!pcSystemSettingsFullscreen);
}

function initPcSidebarToggle() {
  const btn = document.getElementById("btnTogglePcSidebar");
  if (btn && btn.dataset.bound !== "1") {
    btn.dataset.bound = "1";
    btn.addEventListener("click", togglePcSidebar);
  }
  const fullBtn = document.getElementById("btnToggleSidebarFullscreen");
  if (fullBtn && fullBtn.dataset.bound !== "1") {
    fullBtn.dataset.bound = "1";
    fullBtn.addEventListener("click", toggleSidebarFullscreen);
  }
  const settingsFullBtn = document.getElementById("btnToggleSystemSettingsFullscreen");
  if (settingsFullBtn && settingsFullBtn.dataset.bound !== "1") {
    settingsFullBtn.dataset.bound = "1";
    settingsFullBtn.addEventListener("click", toggleSystemSettingsFullscreen);
  }
  const savedSidebar = localStorage.getItem(PC_SIDEBAR_COLLAPSED_KEY);
  const savedMainHidden = localStorage.getItem(PC_MAIN_HIDDEN_KEY);
  const savedSettingsFullscreen = localStorage.getItem(PC_SYSTEM_SETTINGS_FULLSCREEN_KEY);
  pcSidebarCollapsed = savedSidebar === "1";
  pcMainHidden = savedMainHidden === "1";
  pcSystemSettingsFullscreen = savedSettingsFullscreen === "1";
  if (pcSystemSettingsFullscreen) {
    pcSidebarCollapsed = false;
    pcMainHidden = false;
  } else if (pcMainHidden && pcSidebarCollapsed) {
    pcSidebarCollapsed = false;
  }
  refreshPcSidebarLayout();
}

function syncMobileSortBarPlacement() {
  const sortInline = document.getElementById("resultSortInline");
  const anchor = document.getElementById("resultSortInlineAnchor");
  const sortSelect = document.getElementById("resultSortMode");
  const exactWrap = document.getElementById("resultFaceCountExactWrap");
  const mobileActionBar = document.querySelector(".mobile-action-bar");
  const mobileSortSlot = document.getElementById("mobileSortSelectSlot");
  const mobileExactSlot = document.getElementById("mobileFaceCountExactSlot");
  if (!sortInline || !anchor || !sortSelect || !exactWrap) return;

  const enableMobileBar = !!(isActualMobileViewport() && mobileActionBar && mobileSortSlot && mobileExactSlot);
  if (enableMobileBar) {
    if (sortSelect.parentElement !== mobileSortSlot) {
      mobileSortSlot.appendChild(sortSelect);
    }
    if (exactWrap.parentElement !== mobileExactSlot) {
      mobileExactSlot.appendChild(exactWrap);
    }
    mobileExactSlot.hidden = !!exactWrap.hidden;
    return;
  }

  if (sortSelect.parentElement !== sortInline) {
    sortInline.appendChild(sortSelect);
  }
  if (exactWrap.parentElement !== sortInline) {
    sortInline.appendChild(exactWrap);
  }
  if (anchor.parentElement && (sortInline.parentElement !== anchor.parentElement || sortInline.previousElementSibling !== anchor)) {
    anchor.insertAdjacentElement("afterend", sortInline);
  }
  if (mobileExactSlot) {
    mobileExactSlot.hidden = true;
  }
}

function getSearchBatchCacheLimit() {
  return isMobileViewport() ? SEARCH_BATCH_CACHE_LIMIT_MOBILE : SEARCH_BATCH_CACHE_LIMIT_DESKTOP;
}

function getSearchBatchPrefetchAhead() {
  return isMobileViewport() ? SEARCH_BATCH_PREFETCH_AHEAD_MOBILE : SEARCH_BATCH_PREFETCH_AHEAD_DESKTOP;
}

function makeSearchBatchCacheKey(searchId, batch, sortMode = "", faceCountExact = null) {
  const normalizedSort = String(sortMode || "").trim().toLowerCase() || "default";
  const hasExact = normalizedSort === "face_count_exact" && Number.isFinite(Number(faceCountExact));
  const normalizedExact = hasExact ? Math.max(0, Math.trunc(Number(faceCountExact))) : "";
  return `${String(searchId || "")}:${normalizedSort}:${normalizedExact}:${Math.max(1, Number(batch || 1))}`;
}

function clearSearchBatchClientCache(searchId = "") {
  const scopedSearchId = String(searchId || "");
  if (!scopedSearchId) {
    searchBatchCache.clear();
    searchBatchInflight.clear();
    return;
  }
  for (const key of Array.from(searchBatchCache.keys())) {
    if (key.startsWith(`${scopedSearchId}:`)) {
      searchBatchCache.delete(key);
    }
  }
  for (const key of Array.from(searchBatchInflight.keys())) {
    if (key.startsWith(`${scopedSearchId}:`)) {
      searchBatchInflight.delete(key);
    }
  }
}

function getSearchBatchFromCache(searchId, batch, sortMode = "", faceCountExact = null) {
  const key = makeSearchBatchCacheKey(searchId, batch, sortMode, faceCountExact);
  const cached = searchBatchCache.get(key);
  if (!cached) return null;
  searchBatchCache.delete(key);
  searchBatchCache.set(key, cached);
  return cached;
}

function putSearchBatchCache(data, options = {}) {
  const searchId = String((data && data.search_id) || "");
  const batch = Math.max(1, Number((data && data.batch) || 1));
  const sortMode = String(options.sortMode || "").trim().toLowerCase();
  const faceCountExact = Number.isFinite(Number(options.faceCountExact)) ? Math.max(0, Math.trunc(Number(options.faceCountExact))) : null;
  if (!searchId) return;
  const key = makeSearchBatchCacheKey(searchId, batch, sortMode, faceCountExact);
  searchBatchCache.delete(key);
  searchBatchCache.set(key, data);

  const prefix = `${searchId}:`;
  for (const keyItem of Array.from(searchBatchCache.keys())) {
    if (!keyItem.startsWith(prefix)) {
      searchBatchCache.delete(keyItem);
    }
  }
  const limit = getSearchBatchCacheLimit();
  while (searchBatchCache.size > limit) {
    const oldestKey = searchBatchCache.keys().next().value;
    if (!oldestKey) break;
    searchBatchCache.delete(oldestKey);
  }
}

async function fetchSearchBatchData(searchId, batch, options = {}) {
  const sid = String(searchId || "");
  const targetBatch = Math.max(1, Number(batch || 1));
  if (!sid) throw new Error("search session not found");
  const sortMode = getServerGlobalSortMode(options.sortMode);
  const normalizedFaceCountExact = sortMode === "face_count_exact"
    ? (
        Number.isFinite(Number(options.faceCountExact))
          ? Math.max(0, Math.trunc(Number(options.faceCountExact)))
          : getResultFaceCountExactValue()
      )
    : null;
  const preferCache = options.preferCache !== false;
  if (preferCache) {
    const cached = getSearchBatchFromCache(sid, targetBatch, sortMode, normalizedFaceCountExact);
    if (cached) return cached;
  }
  const key = makeSearchBatchCacheKey(sid, targetBatch, sortMode, normalizedFaceCountExact);
  const inflight = searchBatchInflight.get(key);
  if (inflight) return inflight;
  const sortParam = sortMode ? `&sort_mode=${encodeURIComponent(sortMode)}` : "";
  const exactParam = sortMode === "face_count_exact" ? `&face_count_exact=${encodeURIComponent(normalizedFaceCountExact ?? 0)}` : "";
  const req = apiFetch(`${apiBase}/search/batch?search_id=${encodeURIComponent(sid)}&batch=${targetBatch}${sortParam}${exactParam}`)
    .then((data) => {
      putSearchBatchCache(data, { sortMode, faceCountExact: normalizedFaceCountExact });
      return data;
    })
    .finally(() => {
      searchBatchInflight.delete(key);
    });
  searchBatchInflight.set(key, req);
  return req;
}

function prefetchSearchBatchAround() {
  const sid = String(searchSessionState.searchId || "");
  if (!sid) return;
  const sortMode = getServerGlobalSortMode();
  const faceCountExact = sortMode === "face_count_exact" ? getResultFaceCountExactValue() : null;
  const totalBatches = Math.max(1, Number(searchSessionState.totalBatches || 1));
  const current = Math.max(1, Math.min(Number(searchSessionState.batch || 1), totalBatches));
  const ahead = getSearchBatchPrefetchAhead();
  const targets = [];
  for (let d = 1; d <= ahead; d += 1) {
    const nextBatch = current + d;
    const prevBatch = current - d;
    if (nextBatch <= totalBatches) targets.push(nextBatch);
    if (prevBatch >= 1) targets.push(prevBatch);
  }
  targets.forEach((targetBatch) => {
    fetchSearchBatchData(sid, targetBatch, { preferCache: true, sortMode, faceCountExact }).catch(() => {});
  });
}

function applyLightboxStageOffsetNow() {
  resultLightboxOffsetRaf = 0;
  const track = document.getElementById("resultLightboxTrack");
  if (!track) return;
  const animate = !!resultLightboxPendingAnimate;
  if (resultLightboxTrackAnimateState !== animate) {
    track.style.transition = animate ? "transform 210ms cubic-bezier(0.22, 0.61, 0.36, 1)" : "none";
    resultLightboxTrackAnimateState = animate;
  }
  track.style.transform = `translate3d(calc(-100% + ${Math.round(resultLightboxPendingOffsetX)}px),${Math.round(resultLightboxPendingOffsetY)}px,0)`;
}

function setLightboxStageOffset(offsetX, offsetY = 0, animate = false) {
  resultLightboxPendingOffsetX = Number.isFinite(Number(offsetX)) ? Number(offsetX) : 0;
  resultLightboxPendingOffsetY = Number.isFinite(Number(offsetY)) ? Number(offsetY) : 0;
  resultLightboxPendingAnimate = !!animate;
  if (resultLightboxOffsetRaf) return;
  resultLightboxOffsetRaf = window.requestAnimationFrame(applyLightboxStageOffsetNow);
}

function resetLightboxStageOffset(animate = false) {
  setLightboxStageOffset(0, 0, animate);
}

function clampLightboxZoomScale(scale) {
  const value = Number(scale);
  if (!Number.isFinite(value)) return LIGHTBOX_ZOOM_MIN;
  return Math.max(LIGHTBOX_ZOOM_MIN, Math.min(LIGHTBOX_ZOOM_MAX, value));
}

function isLightboxZoomed() {
  return resultLightboxZoomScale > (LIGHTBOX_ZOOM_MIN + 0.001);
}

function getLightboxZoomLimits(scale = resultLightboxZoomScale) {
  const safeScale = clampLightboxZoomScale(scale);
  const stage = document.querySelector("#resultLightbox .result-lightbox-stage");
  const width = stage ? Math.max(0, Number(stage.clientWidth || 0)) : Math.max(0, Number(window.innerWidth || 0));
  const height = stage ? Math.max(0, Number(stage.clientHeight || 0)) : Math.max(0, Number(window.innerHeight || 0));
  if (safeScale <= (LIGHTBOX_ZOOM_MIN + 0.001)) {
    return { maxX: 0, maxY: 0 };
  }
  return {
    maxX: Math.max(0, ((width * safeScale) - width) / 2),
    maxY: Math.max(0, ((height * safeScale) - height) / 2),
  };
}

function clampLightboxZoomOffsets(offsetX, offsetY, scale = resultLightboxZoomScale) {
  const limits = getLightboxZoomLimits(scale);
  const rawX = Number.isFinite(Number(offsetX)) ? Number(offsetX) : 0;
  const rawY = Number.isFinite(Number(offsetY)) ? Number(offsetY) : 0;
  return {
    x: Math.max(-limits.maxX, Math.min(limits.maxX, rawX)),
    y: Math.max(-limits.maxY, Math.min(limits.maxY, rawY)),
  };
}

function applyLightboxImageTransform(imgEl, rotation = 0, scale = 1, offsetX = 0, offsetY = 0) {
  if (!imgEl) return;
  const normalizedRotation = normalizeLightboxRotation(rotation);
  const safeScale = clampLightboxZoomScale(scale);
  const safeX = Number.isFinite(Number(offsetX)) ? Number(offsetX) : 0;
  const safeY = Number.isFinite(Number(offsetY)) ? Number(offsetY) : 0;
  const transformParts = [];
  transformParts.push(`translate3d(${Math.round(safeX)}px, ${Math.round(safeY)}px, 0)`);
  if (safeScale > (LIGHTBOX_ZOOM_MIN + 0.001)) {
    transformParts.push(`scale(${safeScale.toFixed(4)})`);
  }
  if (normalizedRotation) {
    transformParts.push(`rotate(${normalizedRotation}deg)`);
  }
  imgEl.style.transform = transformParts.join(" ");
  imgEl.classList.toggle("rotated-quarter", normalizedRotation % 180 !== 0);
}

function applyCurrentLightboxZoomTransform() {
  const img = document.getElementById("resultLightboxImg");
  const stage = document.querySelector("#resultLightbox .result-lightbox-stage");
  if (!img) {
    if (stage) stage.classList.remove("zooming");
    return;
  }
  const safeScale = clampLightboxZoomScale(resultLightboxZoomScale);
  resultLightboxZoomScale = safeScale;
  if (safeScale <= (LIGHTBOX_ZOOM_MIN + 0.001)) {
    resultLightboxZoomScale = LIGHTBOX_ZOOM_MIN;
    resultLightboxZoomOffsetX = 0;
    resultLightboxZoomOffsetY = 0;
  } else {
    const clamped = clampLightboxZoomOffsets(resultLightboxZoomOffsetX, resultLightboxZoomOffsetY, safeScale);
    resultLightboxZoomOffsetX = clamped.x;
    resultLightboxZoomOffsetY = clamped.y;
  }
  const currentItem = getLightboxItemAt(resultLightboxIndex);
  const rotation = getLightboxRotationForItem(currentItem);
  applyLightboxImageTransform(img, rotation, resultLightboxZoomScale, resultLightboxZoomOffsetX, resultLightboxZoomOffsetY);
  const zoomed = isLightboxZoomed();
  img.classList.toggle("zoomed", zoomed);
  if (stage) stage.classList.toggle("zooming", zoomed);
}

function setLightboxZoomState(scale, offsetX = resultLightboxZoomOffsetX, offsetY = resultLightboxZoomOffsetY) {
  const safeScale = clampLightboxZoomScale(scale);
  if (safeScale <= (LIGHTBOX_ZOOM_MIN + 0.001)) {
    resultLightboxZoomScale = LIGHTBOX_ZOOM_MIN;
    resultLightboxZoomOffsetX = 0;
    resultLightboxZoomOffsetY = 0;
  } else {
    const clamped = clampLightboxZoomOffsets(offsetX, offsetY, safeScale);
    resultLightboxZoomScale = safeScale;
    resultLightboxZoomOffsetX = clamped.x;
    resultLightboxZoomOffsetY = clamped.y;
  }
  applyCurrentLightboxZoomTransform();
}

function resetLightboxZoomState(apply = true) {
  resultLightboxZoomScale = LIGHTBOX_ZOOM_MIN;
  resultLightboxZoomOffsetX = 0;
  resultLightboxZoomOffsetY = 0;
  resultLightboxPinchActive = false;
  resultLightboxPanActive = false;
  resultLightboxPinchStartDistance = 0;
  if (apply) {
    applyCurrentLightboxZoomTransform();
  } else {
    const stage = document.querySelector("#resultLightbox .result-lightbox-stage");
    const img = document.getElementById("resultLightboxImg");
    if (stage) stage.classList.remove("zooming");
    if (img) img.classList.remove("zoomed");
  }
}

function getLightboxCacheBudgetBytes() {
  const baseMb = isMobileViewport() ? LIGHTBOX_CACHE_MB_MOBILE : LIGHTBOX_CACHE_MB_DESKTOP;
  const deviceMemory = Number(navigator && navigator.deviceMemory ? navigator.deviceMemory : 0);
  if (deviceMemory > 0 && deviceMemory <= 4) {
    return Math.floor(Math.min(baseMb, 64) * 1024 * 1024);
  }
  return Math.floor(baseMb * 1024 * 1024);
}

function estimateLightboxImageBytes(img) {
  const w = Number(img && img.naturalWidth ? img.naturalWidth : 0);
  const h = Number(img && img.naturalHeight ? img.naturalHeight : 0);
  if (!w || !h) return 0;
  return Math.max(0, Math.floor(w * h * 4));
}

function touchLightboxCacheEntry(url) {
  const entry = lightboxImageCache.get(url);
  if (!entry) return;
  lightboxImageCache.delete(url);
  lightboxImageCache.set(url, Object.assign({}, entry, { usedAt: Date.now() }));
}

function dropLightboxCacheEntry(url) {
  const entry = lightboxImageCache.get(url);
  if (!entry) return;
  lightboxImageCache.delete(url);
  lightboxCacheBytes = Math.max(0, lightboxCacheBytes - Math.max(0, Number(entry.bytes || 0)));
  if (entry.status === "loading" && entry.image) {
    entry.image.onload = null;
    entry.image.onerror = null;
    try { entry.image.src = ""; } catch (_) {}
  }
}

function setLightboxCacheEntry(url, nextEntry) {
  const prev = lightboxImageCache.get(url);
  if (prev) {
    lightboxCacheBytes = Math.max(0, lightboxCacheBytes - Math.max(0, Number(prev.bytes || 0)));
    lightboxImageCache.delete(url);
  }
  const entry = Object.assign(
    { status: "error", promise: null, bytes: 0, image: null, usedAt: Date.now() },
    nextEntry || {},
  );
  entry.bytes = Math.max(0, Math.floor(Number(entry.bytes || 0)));
  entry.usedAt = Date.now();
  lightboxImageCache.set(url, entry);
  lightboxCacheBytes += entry.bytes;
}

function getLightboxItemAt(index) {
  const total = resultLightboxItems.length;
  if (!total) return null;
  return resultLightboxItems[normalizeLoopIndex(index, total)] || null;
}

function buildProtectedLightboxUrls(centerIndex = resultLightboxIndex) {
  const total = resultLightboxItems.length;
  const keep = new Set();
  if (!total) return keep;
  for (let d = -LIGHTBOX_CACHE_PROTECTED_RADIUS; d <= LIGHTBOX_CACHE_PROTECTED_RADIUS; d += 1) {
    const item = getLightboxItemAt(centerIndex + d);
    if (item && item.lightboxUrl) keep.add(item.lightboxUrl);
  }
  return keep;
}

function trimLightboxImageCache(force = false) {
  const budgetBytes = getLightboxCacheBudgetBytes();
  if (lightboxCacheBytes <= budgetBytes && !force) return;
  const keep = buildProtectedLightboxUrls();
  for (const [url, entry] of lightboxImageCache) {
    if (lightboxCacheBytes <= budgetBytes) break;
    if (keep.has(url)) continue;
    if (entry && entry.status === "loading") continue;
    dropLightboxCacheEntry(url);
  }
}

function cancelLightboxPreloadTask(task) {
  if (!task || task.canceled) return;
  task.canceled = true;
  if (task.image) {
    task.image.onload = null;
    task.image.onerror = null;
    try { task.image.src = ""; } catch (_) {}
  }
  if (typeof task.resolve === "function") {
    task.resolve(false);
    task.resolve = null;
  }
  lightboxPreloadActive.delete(task.url);
}

function drainLightboxPreloadQueue() {
  while (lightboxPreloadActive.size < LIGHTBOX_PRELOAD_CONCURRENCY && lightboxPreloadQueue.length) {
    lightboxPreloadQueue.sort((a, b) => {
      if (b.priority !== a.priority) return b.priority - a.priority;
      return a.createdAt - b.createdAt;
    });
    const task = lightboxPreloadQueue.shift();
    if (!task || task.canceled) continue;
    const cached = lightboxImageCache.get(task.url);
    if (cached && cached.status === "loaded") {
      touchLightboxCacheEntry(task.url);
      if (typeof task.resolve === "function") {
        task.resolve(true);
        task.resolve = null;
      }
      continue;
    }
    if (lightboxPreloadActive.has(task.url)) continue;

    lightboxPreloadActive.set(task.url, task);
    const img = new Image();
    img.decoding = "async";
    if (task.priority >= LIGHTBOX_PRELOAD_PRIORITY.next) {
      img.fetchPriority = "high";
    }
    task.image = img;
    setLightboxCacheEntry(task.url, { status: "loading", promise: task.promise, bytes: 0, image: img });

    img.onload = () => {
      lightboxPreloadActive.delete(task.url);
      if (!task.canceled) {
        const bytes = estimateLightboxImageBytes(img);
        setLightboxCacheEntry(task.url, { status: "loaded", promise: null, bytes, image: null });
        trimLightboxImageCache();
        if (typeof task.resolve === "function") {
          task.resolve(true);
          task.resolve = null;
        }
      }
      drainLightboxPreloadQueue();
    };
    img.onerror = () => {
      lightboxPreloadActive.delete(task.url);
      if (!task.canceled) {
        setLightboxCacheEntry(task.url, { status: "error", promise: null, bytes: 0, image: null });
        if (typeof task.resolve === "function") {
          task.resolve(false);
          task.resolve = null;
        }
      }
      drainLightboxPreloadQueue();
    };
    img.src = task.url;
  }
}

function pruneLightboxPreloadTasks(allowSet) {
  if (!(allowSet instanceof Set)) return;
  const kept = [];
  for (const task of lightboxPreloadQueue) {
    if (allowSet.has(task.url)) {
      kept.push(task);
      continue;
    }
    cancelLightboxPreloadTask(task);
  }
  lightboxPreloadQueue = kept;
  for (const [url, task] of lightboxPreloadActive) {
    if (allowSet.has(url)) continue;
    cancelLightboxPreloadTask(task);
    const entry = lightboxImageCache.get(url);
    if (entry && entry.status === "loading") {
      dropLightboxCacheEntry(url);
    }
  }
}

function preloadLightboxUrl(url, options = {}) {
  if (!url) return Promise.resolve(false);
  const cached = lightboxImageCache.get(url);
  if (cached && cached.status === "loaded") {
    touchLightboxCacheEntry(url);
    return Promise.resolve(true);
  }
  if (cached && cached.status === "loading" && cached.promise) {
    return cached.promise;
  }

  const existingTask = lightboxPreloadQueue.find((it) => it.url === url);
  const priority = Math.max(0, Number.isFinite(options.priority) ? Number(options.priority) : 0);
  if (existingTask) {
    existingTask.priority = Math.max(existingTask.priority, priority);
    drainLightboxPreloadQueue();
    return existingTask.promise;
  }
  const activeTask = lightboxPreloadActive.get(url);
  if (activeTask) {
    activeTask.priority = Math.max(activeTask.priority, priority);
    return activeTask.promise;
  }

  let resolveTask;
  const promise = new Promise((resolve) => {
    resolveTask = resolve;
  });
  lightboxPreloadQueue.push({
    url,
    priority,
    createdAt: Date.now(),
    promise,
    resolve: resolveTask,
    canceled: false,
    image: null,
  });
  drainLightboxPreloadQueue();
  return promise;
}

function isLightboxUrlLoaded(url) {
  if (!url) return false;
  const cached = lightboxImageCache.get(url);
  return !!cached && cached.status === "loaded";
}

function syncLightboxImageCache() {
  const allow = new Set(resultLightboxItems.map((it) => it.lightboxUrl).filter(Boolean));
  pruneLightboxPreloadTasks(allow);
  for (const key of lightboxImageCache.keys()) {
    if (!allow.has(key)) {
      dropLightboxCacheEntry(key);
    }
  }
  trimLightboxImageCache(true);
}

function clearLightboxCacheAll() {
  for (const task of lightboxPreloadQueue) {
    cancelLightboxPreloadTask(task);
  }
  lightboxPreloadQueue = [];
  for (const task of lightboxPreloadActive.values()) {
    cancelLightboxPreloadTask(task);
  }
  lightboxPreloadActive.clear();
  for (const key of Array.from(lightboxImageCache.keys())) {
    dropLightboxCacheEntry(key);
  }
  lightboxImageCache.clear();
  lightboxCacheBytes = 0;
}

function markLightboxMove(step) {
  const direction = step >= 0 ? 1 : -1;
  const now = Date.now();
  const dt = resultLightboxLastMoveTs ? (now - resultLightboxLastMoveTs) : 9999;
  if (direction === resultLightboxLastStep && dt <= LIGHTBOX_PRELOAD_QUICK_WINDOW_MS) {
    resultLightboxFastMoveStreak += 1;
  } else {
    resultLightboxFastMoveStreak = 0;
  }
  resultLightboxLastStep = direction;
  resultLightboxLastMoveTs = now;
}

function getDynamicPreloadRadius() {
  const base = isMobileViewport() ? LIGHTBOX_PRELOAD_RADIUS_MOBILE : LIGHTBOX_PRELOAD_RADIUS_DESKTOP;
  if (resultLightboxFastMoveStreak >= LIGHTBOX_PRELOAD_QUICK_STREAK) {
    return 1;
  }
  return base;
}

function preloadLightboxNeighbors(centerIndex, hintDirection = 0) {
  const total = resultLightboxItems.length;
  if (!total) return;
  const direction = hintDirection > 0 ? 1 : (hintDirection < 0 ? -1 : resultLightboxLastStep);
  const radius = getDynamicPreloadRadius();
  const allow = buildProtectedLightboxUrls(centerIndex);
  const center = getLightboxItemAt(centerIndex);
  if (center && center.lightboxUrl) {
    allow.add(center.lightboxUrl);
    preloadLightboxUrl(center.lightboxUrl, { priority: LIGHTBOX_PRELOAD_PRIORITY.current });
  }
  for (let d = 1; d <= radius; d += 1) {
    const forward = getLightboxItemAt(centerIndex + direction * d);
    const backward = getLightboxItemAt(centerIndex - direction * d);
    const forwardPriority = d === 1 ? LIGHTBOX_PRELOAD_PRIORITY.next : LIGHTBOX_PRELOAD_PRIORITY.near;
    if (forward && forward.lightboxUrl) {
      allow.add(forward.lightboxUrl);
      preloadLightboxUrl(forward.lightboxUrl, { priority: forwardPriority });
    }
    if (backward && backward.lightboxUrl) {
      allow.add(backward.lightboxUrl);
      preloadLightboxUrl(backward.lightboxUrl, { priority: LIGHTBOX_PRELOAD_PRIORITY.far });
    }
  }
  pruneLightboxPreloadTasks(allow);
}

function normalizeLightboxRotation(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  const normalized = ((Math.round(n / 90) * 90) % 360 + 360) % 360;
  return normalized;
}

function getLightboxItemRotationKey(item) {
  if (!item || typeof item !== "object") return "";
  const photoId = Number(item.photoId);
  if (Number.isFinite(photoId) && photoId > 0) {
    return `id:${Math.trunc(photoId)}`;
  }
  const filePath = String(item.filePath || "").trim();
  return filePath ? `path:${filePath}` : "";
}

function getLightboxRotationForItem(item) {
  const key = getLightboxItemRotationKey(item);
  if (!key) return 0;
  return normalizeLightboxRotation(lightboxRotationMap.get(key));
}

function setLightboxRotationForItem(item, value) {
  const key = getLightboxItemRotationKey(item);
  if (!key) return;
  const normalized = normalizeLightboxRotation(value);
  if (!normalized) {
    lightboxRotationMap.delete(key);
    return;
  }
  lightboxRotationMap.set(key, normalized);
}

function rotateCurrentResultLightbox(step) {
  if (!resultLightboxActive || !resultLightboxItems.length) return;
  const item = getLightboxItemAt(resultLightboxIndex);
  if (!item) return;
  const current = getLightboxRotationForItem(item);
  setLightboxRotationForItem(item, current + Number(step || 0));
  updateResultLightboxView(0);
}

function resetCurrentResultLightboxRotation() {
  if (!resultLightboxActive || !resultLightboxItems.length) return;
  const item = getLightboxItemAt(resultLightboxIndex);
  if (!item) return;
  setLightboxRotationForItem(item, 0);
  updateResultLightboxView(0);
}

function resetCurrentResultLightboxZoom() {
  if (!resultLightboxActive) return;
  resetLightboxZoomState(true);
  resultLightboxTouchBlockClickUntil = Date.now() + 180;
}
function ensureResultLightbox() {
  if (document.getElementById("resultLightbox")) return;
  const overlay = document.createElement("div");
  overlay.id = "resultLightbox";
  overlay.className = "result-lightbox";
  overlay.hidden = true;
  overlay.innerHTML = `
    <div class="result-lightbox-top">
      <div id="resultLightboxCounter" class="result-lightbox-counter"></div>
      <div class="result-lightbox-actions" role="group" aria-label="旋转控制">
        <button id="resultLightboxRotateLeft" class="result-lightbox-rotate" type="button" aria-label="左转90度">左转90°</button>
        <button id="resultLightboxRotateRight" class="result-lightbox-rotate" type="button" aria-label="右转90度">右转90°</button>
        <button id="resultLightboxRotateReset" class="result-lightbox-rotate" type="button" aria-label="旋转复位">复位</button>
        <button id="resultLightboxZoomReset" class="result-lightbox-rotate" type="button" aria-label="复原到1比1">复原</button>
      </div>
      <button id="resultLightboxClose" class="result-lightbox-close" type="button" aria-label="关闭">×</button>
    </div>
    <button id="resultLightboxPrev" class="result-lightbox-nav prev" type="button" aria-label="上一张">‹</button>
    <div class="result-lightbox-stage">
      <div id="resultLightboxTrack" class="result-lightbox-track">
        <div class="result-lightbox-frame"><img id="resultLightboxImgPrev" class="result-lightbox-img" alt="上一张预览"></div>
        <div class="result-lightbox-frame"><img id="resultLightboxImg" class="result-lightbox-img" alt="放大预览"></div>
        <div class="result-lightbox-frame"><img id="resultLightboxImgNext" class="result-lightbox-img" alt="下一张预览"></div>
      </div>
      <div id="resultLightboxTitle" class="result-lightbox-title"></div>
    </div>
    <button id="resultLightboxNext" class="result-lightbox-nav next" type="button" aria-label="下一张">›</button>
  `;
  document.body.appendChild(overlay);

  const closeBtn = document.getElementById("resultLightboxClose");
  const prevBtn = document.getElementById("resultLightboxPrev");
  const nextBtn = document.getElementById("resultLightboxNext");
  const rotateLeftBtn = document.getElementById("resultLightboxRotateLeft");
  const rotateRightBtn = document.getElementById("resultLightboxRotateRight");
  const rotateResetBtn = document.getElementById("resultLightboxRotateReset");
  const zoomResetBtn = document.getElementById("resultLightboxZoomReset");
  const stage = overlay.querySelector(".result-lightbox-stage");

  if (closeBtn) {
    closeBtn.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      closeResultLightbox();
    });
    closeBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      closeResultLightbox();
    });
  }
  if (prevBtn) prevBtn.addEventListener("click", () => moveResultLightbox(-1));
  if (nextBtn) nextBtn.addEventListener("click", () => moveResultLightbox(1));
  if (rotateLeftBtn) {
    rotateLeftBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      rotateCurrentResultLightbox(-90);
    });
  }
  if (rotateRightBtn) {
    rotateRightBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      rotateCurrentResultLightbox(90);
    });
  }
  if (rotateResetBtn) {
    rotateResetBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      resetCurrentResultLightboxRotation();
    });
  }
  if (zoomResetBtn) {
    zoomResetBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      resetCurrentResultLightboxZoom();
    });
  }

  overlay.addEventListener("dblclick", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
    const target = ev.target;
    const isStage = !!(target && target.classList && target.classList.contains("result-lightbox-stage"));
    const isTrackOrFrame = !!(
      target
      && target.classList
      && (target.classList.contains("result-lightbox-track") || target.classList.contains("result-lightbox-frame"))
    );
    const isImage = !!(target && target.classList && target.classList.contains("result-lightbox-img"));
    if (target && (isImage || isStage || isTrackOrFrame || target.id === "resultLightbox")) {
      closeResultLightbox();
    }
  });
  overlay.addEventListener("click", (ev) => {
    if (Date.now() < resultLightboxTouchBlockClickUntil) return;
    const target = ev.target;
    const inNavOrClose = !!(target && target.closest && target.closest(".result-lightbox-nav, .result-lightbox-close"));
    if (inNavOrClose) return;
    if (isLightboxZoomed()) return;
    const isTrackOrFrame = !!(
      target
      && target.classList
      && (target.classList.contains("result-lightbox-track") || target.classList.contains("result-lightbox-frame"))
    );
    const isImage = !!(target && target.classList && target.classList.contains("result-lightbox-img"));
    const canCloseBySingleClick = target && (
      target.id === "resultLightbox"
      || isImage
      || isTrackOrFrame
      || (target.classList && target.classList.contains("result-lightbox-stage"))
    );
    if (!canCloseBySingleClick) return;
    ev.preventDefault();
    ev.stopPropagation();
    closeResultLightbox();
  });

  overlay.addEventListener("wheel", (ev) => {
    if (!resultLightboxActive) return;
    if (isLightboxZoomed()) return;
    ev.preventDefault();
    const delta = Math.abs(ev.deltaX) > Math.abs(ev.deltaY) ? ev.deltaX : ev.deltaY;
    if (delta > 0) {
      moveResultLightbox(1);
    } else if (delta < 0) {
      moveResultLightbox(-1);
    }
  }, { passive: false });

  if (stage) {
    stage.addEventListener("touchstart", (ev) => {
      if (!resultLightboxActive || !ev.touches || !ev.touches.length) return;
      const touches = ev.touches;
      stage.classList.remove("swiping");
      stage.classList.remove("swiping-horizontal");
      stage.classList.remove("swiping-vertical");
      resetLightboxStageOffset(false);

      if (touches.length >= 2) {
        const p1 = touches[0];
        const p2 = touches[1];
        const distance = Math.hypot(p2.clientX - p1.clientX, p2.clientY - p1.clientY);
        if (!Number.isFinite(distance) || distance <= 0) return;
        resultLightboxPinchActive = true;
        resultLightboxPanActive = false;
        resultLightboxTouchMoved = false;
        resultLightboxTouchHorizontal = false;
        resultLightboxTouchAxis = "";
        resultLightboxPinchStartDistance = Math.max(1, distance);
        resultLightboxPinchStartScale = resultLightboxZoomScale;
        resultLightboxPinchStartCenterX = (p1.clientX + p2.clientX) / 2;
        resultLightboxPinchStartCenterY = (p1.clientY + p2.clientY) / 2;
        resultLightboxPinchStartOffsetX = resultLightboxZoomOffsetX;
        resultLightboxPinchStartOffsetY = resultLightboxZoomOffsetY;
        resultLightboxTouchBlockClickUntil = Date.now() + 260;
        return;
      }

      const point = touches[0];
      resultLightboxTouchStartX = point.clientX;
      resultLightboxTouchStartY = point.clientY;
      resultLightboxTouchLastX = point.clientX;
      resultLightboxTouchLastY = point.clientY;
      resultLightboxTouchStartTs = Date.now();
      resultLightboxTouchMoved = false;
      resultLightboxTouchHorizontal = false;
      resultLightboxTouchAxis = "";

      if (isLightboxZoomed()) {
        resultLightboxPanActive = true;
        resultLightboxPinchActive = false;
        resultLightboxPanStartX = point.clientX;
        resultLightboxPanStartY = point.clientY;
        resultLightboxPanStartOffsetX = resultLightboxZoomOffsetX;
        resultLightboxPanStartOffsetY = resultLightboxZoomOffsetY;
        resultLightboxTouchBlockClickUntil = Date.now() + 180;
        return;
      }

      resultLightboxPanActive = false;
      resultLightboxPinchActive = false;
    }, { passive: true });

    stage.addEventListener("touchmove", (ev) => {
      if (!resultLightboxActive || !ev.touches || !ev.touches.length) return;
      const touches = ev.touches;

      if (touches.length >= 2) {
        const p1 = touches[0];
        const p2 = touches[1];
        const distance = Math.hypot(p2.clientX - p1.clientX, p2.clientY - p1.clientY);
        if (!Number.isFinite(distance) || distance <= 0) return;
        if (!resultLightboxPinchActive) {
          resultLightboxPinchActive = true;
          resultLightboxPinchStartDistance = Math.max(1, distance);
          resultLightboxPinchStartScale = resultLightboxZoomScale;
          resultLightboxPinchStartCenterX = (p1.clientX + p2.clientX) / 2;
          resultLightboxPinchStartCenterY = (p1.clientY + p2.clientY) / 2;
          resultLightboxPinchStartOffsetX = resultLightboxZoomOffsetX;
          resultLightboxPinchStartOffsetY = resultLightboxZoomOffsetY;
        }
        const centerX = (p1.clientX + p2.clientX) / 2;
        const centerY = (p1.clientY + p2.clientY) / 2;
        const ratio = distance / Math.max(1, resultLightboxPinchStartDistance);
        const nextScale = clampLightboxZoomScale(resultLightboxPinchStartScale * ratio);
        const offsetX = resultLightboxPinchStartOffsetX + (centerX - resultLightboxPinchStartCenterX);
        const offsetY = resultLightboxPinchStartOffsetY + (centerY - resultLightboxPinchStartCenterY);
        setLightboxZoomState(nextScale, offsetX, offsetY);
        resultLightboxPanActive = false;
        stage.classList.remove("swiping");
        stage.classList.remove("swiping-horizontal");
        stage.classList.remove("swiping-vertical");
        resetLightboxStageOffset(false);
        resultLightboxTouchBlockClickUntil = Date.now() + 260;
        ev.preventDefault();
        return;
      }

      const point = touches[0];
      if (resultLightboxPinchActive) {
        resultLightboxPinchActive = false;
        if (isLightboxZoomed()) {
          resultLightboxPanActive = true;
          resultLightboxPanStartX = point.clientX;
          resultLightboxPanStartY = point.clientY;
          resultLightboxPanStartOffsetX = resultLightboxZoomOffsetX;
          resultLightboxPanStartOffsetY = resultLightboxZoomOffsetY;
        }
      }

      if (resultLightboxPanActive || isLightboxZoomed()) {
        if (!resultLightboxPanActive) {
          resultLightboxPanActive = true;
          resultLightboxPanStartX = point.clientX;
          resultLightboxPanStartY = point.clientY;
          resultLightboxPanStartOffsetX = resultLightboxZoomOffsetX;
          resultLightboxPanStartOffsetY = resultLightboxZoomOffsetY;
        }
        const dx = point.clientX - resultLightboxPanStartX;
        const dy = point.clientY - resultLightboxPanStartY;
        setLightboxZoomState(resultLightboxZoomScale, resultLightboxPanStartOffsetX + dx, resultLightboxPanStartOffsetY + dy);
        resultLightboxTouchBlockClickUntil = Date.now() + 240;
        ev.preventDefault();
        return;
      }

      const dx = point.clientX - resultLightboxTouchStartX;
      const dy = point.clientY - resultLightboxTouchStartY;
      resultLightboxTouchLastX = point.clientX;
      resultLightboxTouchLastY = point.clientY;

      if (!resultLightboxTouchMoved) {
        const absDx = Math.abs(dx);
        const absDy = Math.abs(dy);
        if (absDx < 10 && absDy < 10) return;
        resultLightboxTouchMoved = true;
        resultLightboxTouchHorizontal = absDx >= absDy;
        resultLightboxTouchAxis = resultLightboxTouchHorizontal ? "x" : "y";
      }
      if (!resultLightboxTouchAxis) return;
      ev.preventDefault();
      stage.classList.add("swiping");
      stage.classList.toggle("swiping-horizontal", resultLightboxTouchAxis === "x");
      stage.classList.toggle("swiping-vertical", resultLightboxTouchAxis === "y");
      const majorDelta = resultLightboxTouchAxis === "y" ? dy : dx;
      const dampedDelta = isMobileViewport() ? majorDelta * 0.94 : majorDelta * 0.98;
      if (resultLightboxTouchAxis === "y") {
        setLightboxStageOffset(0, dampedDelta, false);
      } else {
        setLightboxStageOffset(dampedDelta, 0, false);
      }
      resultLightboxTouchBlockClickUntil = Date.now() + 260;
    }, { passive: false });

    stage.addEventListener("touchend", (ev) => {
      if (!resultLightboxActive) return;
      const remainingTouches = ev.touches ? ev.touches.length : 0;
      stage.classList.remove("swiping");
      stage.classList.remove("swiping-horizontal");
      stage.classList.remove("swiping-vertical");

      if (resultLightboxPinchActive) {
        if (remainingTouches <= 1) {
          resultLightboxPinchActive = false;
          if (remainingTouches === 1 && isLightboxZoomed()) {
            const point = ev.touches[0];
            resultLightboxPanActive = true;
            resultLightboxPanStartX = point.clientX;
            resultLightboxPanStartY = point.clientY;
            resultLightboxPanStartOffsetX = resultLightboxZoomOffsetX;
            resultLightboxPanStartOffsetY = resultLightboxZoomOffsetY;
          }
        }
        if (!isLightboxZoomed()) {
          setLightboxZoomState(LIGHTBOX_ZOOM_MIN, 0, 0);
        }
        resultLightboxTouchBlockClickUntil = Date.now() + 220;
        resetLightboxStageOffset(false);
        resultLightboxTouchMoved = false;
        resultLightboxTouchHorizontal = false;
        resultLightboxTouchAxis = "";
        return;
      }

      if (resultLightboxPanActive || isLightboxZoomed()) {
        if (remainingTouches === 1 && isLightboxZoomed()) {
          const point = ev.touches[0];
          resultLightboxPanActive = true;
          resultLightboxPanStartX = point.clientX;
          resultLightboxPanStartY = point.clientY;
          resultLightboxPanStartOffsetX = resultLightboxZoomOffsetX;
          resultLightboxPanStartOffsetY = resultLightboxZoomOffsetY;
        } else {
          resultLightboxPanActive = false;
        }
        if (!isLightboxZoomed()) {
          setLightboxZoomState(LIGHTBOX_ZOOM_MIN, 0, 0);
        }
        resultLightboxTouchBlockClickUntil = Date.now() + 180;
        resetLightboxStageOffset(false);
        resultLightboxTouchMoved = false;
        resultLightboxTouchHorizontal = false;
        resultLightboxTouchAxis = "";
        return;
      }

      const point = ev.changedTouches && ev.changedTouches.length ? ev.changedTouches[0] : null;
      const endX = point ? point.clientX : resultLightboxTouchLastX;
      const endY = point ? point.clientY : resultLightboxTouchLastY;
      const dx = endX - resultLightboxTouchStartX;
      const dy = endY - resultLightboxTouchStartY;
      const dt = Math.max(1, Date.now() - resultLightboxTouchStartTs);
      const axis = resultLightboxTouchAxis
        || (Math.abs(dx) >= Math.abs(dy) ? "x" : "y");
      const majorDelta = axis === "y" ? dy : dx;
      const velocity = Math.abs(majorDelta) / dt;
      const width = Math.max(stage.clientWidth || 0, window.innerWidth || 0, 320);
      const height = Math.max(stage.clientHeight || 0, window.innerHeight || 0, 320);
      const baseLength = axis === "y" ? height : width;
      const distanceThreshold = Math.min(120, Math.max(42, Math.floor(baseLength * 0.16)));
      const movedEnough = axis === "y" ? Math.abs(dy) > 14 : Math.abs(dx) > 14;
      const canSwitch = movedEnough && (Math.abs(majorDelta) >= distanceThreshold || velocity >= 0.42);

      if (canSwitch) {
        resultLightboxTouchBlockClickUntil = Date.now() + 320;
        if (majorDelta > 0) {
          moveResultLightbox(-1);
        } else {
          moveResultLightbox(1);
        }
      }
      resetLightboxStageOffset(true);
      resultLightboxTouchMoved = false;
      resultLightboxTouchHorizontal = false;
      resultLightboxTouchAxis = "";
    }, { passive: true });

    stage.addEventListener("touchcancel", () => {
      stage.classList.remove("swiping");
      stage.classList.remove("swiping-horizontal");
      stage.classList.remove("swiping-vertical");
      resetLightboxStageOffset(true);
      resultLightboxTouchMoved = false;
      resultLightboxTouchHorizontal = false;
      resultLightboxTouchAxis = "";
      resultLightboxPinchActive = false;
      resultLightboxPanActive = false;
      if (!isLightboxZoomed()) {
        resetLightboxZoomState(true);
      }
    }, { passive: true });
  }

  document.addEventListener("keydown", (ev) => {
    if (!resultLightboxActive) return;
    if (ev.key === "Escape") {
      closeResultLightbox();
      return;
    }
    if (ev.key === "ArrowLeft") {
      moveResultLightbox(-1);
      return;
    }
    if (ev.key === "ArrowRight") {
      moveResultLightbox(1);
    }
  });
}

function updateResultLightboxView(stepHint = 0) {
  const overlay = document.getElementById("resultLightbox");
  const imgPrev = document.getElementById("resultLightboxImgPrev");
  const img = document.getElementById("resultLightboxImg");
  const imgNext = document.getElementById("resultLightboxImgNext");
  const title = document.getElementById("resultLightboxTitle");
  const counter = document.getElementById("resultLightboxCounter");
  if (!overlay || !img || !imgPrev || !imgNext || !counter || !title || !resultLightboxItems.length) return;
  resultLightboxIndex = normalizeLoopIndex(resultLightboxIndex, resultLightboxItems.length);
  resultLightboxRenderToken += 1;
  const baseToken = resultLightboxRenderToken;
  const centerIndex = resultLightboxIndex;
  const prevItem = getLightboxItemAt(centerIndex - 1);
  const item = getLightboxItemAt(centerIndex);
  const nextItem = getLightboxItemAt(centerIndex + 1);
  const renderFrame = (imgEl, frameItem, frameOffset, fallbackAlt, priority) => {
    if (!imgEl) return;
    const fallbackUrl = frameItem && (frameItem.thumbUrl || frameItem.lightboxUrl || frameItem.fileUrl)
      ? (frameItem.thumbUrl || frameItem.lightboxUrl || frameItem.fileUrl)
      : "";
    const highResUrl = frameItem && frameItem.lightboxUrl ? frameItem.lightboxUrl : "";
    const imageUrl = isLightboxUrlLoaded(highResUrl) ? highResUrl : fallbackUrl;
    if (imageUrl) {
      imgEl.src = imageUrl;
    } else {
      imgEl.removeAttribute("src");
    }
    imgEl.alt = frameItem && frameItem.filePath ? shortPath(frameItem.filePath) : fallbackAlt;
    const rotation = getLightboxRotationForItem(frameItem);
    if (frameOffset === 0) {
      applyCurrentLightboxZoomTransform();
    } else {
      applyLightboxImageTransform(imgEl, rotation, LIGHTBOX_ZOOM_MIN, 0, 0);
      imgEl.classList.remove("zoomed");
    }
    if (highResUrl && imageUrl !== highResUrl) {
      preloadLightboxUrl(highResUrl, { priority }).then((ok) => {
        if (!ok || !resultLightboxActive || baseToken !== resultLightboxRenderToken) return;
        const currentFrameItem = getLightboxItemAt(resultLightboxIndex + frameOffset);
        if (!currentFrameItem || currentFrameItem.lightboxUrl !== highResUrl) return;
        imgEl.src = highResUrl;
      });
    }
  };
  renderFrame(imgPrev, prevItem, -1, "上一张预览", LIGHTBOX_PRELOAD_PRIORITY.near);
  renderFrame(img, item, 0, "放大预览", LIGHTBOX_PRELOAD_PRIORITY.current);
  renderFrame(imgNext, nextItem, 1, "下一张预览", LIGHTBOX_PRELOAD_PRIORITY.next);
  counter.textContent = `${resultLightboxIndex + 1} / ${resultLightboxItems.length}`;
  if (item) {
    const name = item.filePath ? shortPath(item.filePath) : "未命名";
    const exif = item.exifDatetime || "未知时间";
    title.textContent = `${name} ｜ EXIF: ${exif}`;
  } else {
    title.textContent = "";
  }
  preloadLightboxNeighbors(resultLightboxIndex, stepHint);
}

function openResultLightbox(index) {
  if (!resultLightboxItems.length) return;
  if (Date.now() < resultLightboxClosingUntil) return;
  ensureResultLightbox();
  const overlay = document.getElementById("resultLightbox");
  if (!overlay) return;
  resultLightboxIndex = normalizeLoopIndex(Number(index) || 0, resultLightboxItems.length);
  overlay.hidden = false;
  overlay.style.display = "flex";
  overlay.classList.add("open");
  resultLightboxActive = true;
  resultLightboxFastMoveStreak = 0;
  resultLightboxLastMoveTs = Date.now();
  resultLightboxLastStep = 1;
  resultLightboxTouchBlockClickUntil = Date.now() + 160;
  resetLightboxZoomState(false);
  resetLightboxStageOffset(false);
  document.body.classList.add("lightbox-open");
  updateResultLightboxView(0);
}

function moveResultLightbox(step) {
  if (!resultLightboxActive || !resultLightboxItems.length) return;
  const delta = Number(step || 0);
  if (!delta) return;
  resetLightboxZoomState(false);
  markLightboxMove(delta);
  resultLightboxIndex = normalizeLoopIndex(resultLightboxIndex + delta, resultLightboxItems.length);
  updateResultLightboxView(delta);
}

function closeResultLightbox() {
  const overlay = document.getElementById("resultLightbox");
  if (!overlay) return;
  if (resultLightboxOffsetRaf) {
    window.cancelAnimationFrame(resultLightboxOffsetRaf);
    resultLightboxOffsetRaf = 0;
  }
  resultLightboxTrackAnimateState = null;
  resultLightboxClosingUntil = Date.now() + 1200;
  overlay.classList.remove("open");
  overlay.hidden = true;
  overlay.style.display = "none";
  resetLightboxZoomState(false);
  resetLightboxStageOffset(false);
  resultLightboxActive = false;
  resultLightboxFastMoveStreak = 0;
  document.body.classList.remove("lightbox-open");
}

function bindSectionTitleToggle(titleId, toggleFn) {
  const title = document.getElementById(titleId);
  if (!title || typeof toggleFn !== "function") return;
  if (title.dataset.toggleKeyBound === "1") return;
  title.dataset.toggleKeyBound = "1";
  title.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      toggleFn();
    }
  });
}

function scrollExpandedSectionToTop(contentEl) {
  if (!isMobileViewport() || !contentEl) return;
  const target = contentEl.closest(".card") || contentEl;
  const nav = document.querySelector(".navbar");
  const navHeight = nav ? Math.max(0, Number(nav.getBoundingClientRect().height || 0)) : 0;
  const top = window.scrollY + target.getBoundingClientRect().top - (navHeight + 6);
  window.scrollTo({ top: Math.max(0, Math.round(top)), behavior: "smooth" });
}

function scrollSearchResultsCardToTop() {
  if (!isMobileViewport()) return;
  const content = document.getElementById("searchResultsContent");
  if (!content) return;
  scrollExpandedSectionToTop(content);
}

function isPanelOpenById(contentId) {
  const panel = document.getElementById(contentId);
  return !!(panel && !panel.hidden);
}

function hasAutoCollapseTargetOpen() {
  return (
    isPanelOpenById("dateFiltersContent")
    || isPanelOpenById("systemSettingsContent")
    || isPanelOpenById("systemStatusContent")
  );
}

function normalizePanelAutoCollapseMs(value) {
  const parsed = Number.parseInt(String(value || ""), 10);
  if (!Number.isFinite(parsed)) return PANEL_AUTO_COLLAPSE_IDLE_MS_DEFAULT;
  if (!PANEL_AUTO_COLLAPSE_IDLE_OPTIONS.includes(parsed)) return PANEL_AUTO_COLLAPSE_IDLE_MS_DEFAULT;
  return parsed;
}

function initPanelAutoCollapseSettings() {
  const disableEl = document.getElementById("panelAutoCollapseDisabled");
  const secondsEl = document.getElementById("panelAutoCollapseSeconds");
  const savedDisabled = localStorage.getItem(PANEL_AUTO_COLLAPSE_DISABLED_KEY) === "1";
  const savedMs = normalizePanelAutoCollapseMs(localStorage.getItem(PANEL_AUTO_COLLAPSE_SECONDS_KEY));
  panelAutoCollapseDisabled = savedDisabled;
  panelAutoCollapseIdleMs = savedMs;
  localStorage.setItem(PANEL_AUTO_COLLAPSE_SECONDS_KEY, String(savedMs));

  if (secondsEl) {
    secondsEl.value = String(savedMs);
    secondsEl.disabled = savedDisabled;
    secondsEl.addEventListener("change", () => {
      panelAutoCollapseIdleMs = normalizePanelAutoCollapseMs(secondsEl.value);
      secondsEl.value = String(panelAutoCollapseIdleMs);
      localStorage.setItem(PANEL_AUTO_COLLAPSE_SECONDS_KEY, String(panelAutoCollapseIdleMs));
      touchPanelAutoCollapseActivity();
    });
  }

  if (disableEl) {
    disableEl.checked = savedDisabled;
    disableEl.addEventListener("change", () => {
      panelAutoCollapseDisabled = !!disableEl.checked;
      localStorage.setItem(PANEL_AUTO_COLLAPSE_DISABLED_KEY, panelAutoCollapseDisabled ? "1" : "0");
      if (secondsEl) {
        secondsEl.disabled = panelAutoCollapseDisabled;
      }
      touchPanelAutoCollapseActivity();
    });
  }
}

function clearPanelAutoCollapseTimer() {
  if (!panelAutoCollapseTimer) return;
  window.clearTimeout(panelAutoCollapseTimer);
  panelAutoCollapseTimer = 0;
}

function schedulePanelAutoCollapseTimer() {
  clearPanelAutoCollapseTimer();
  if (panelAutoCollapseDisabled) return;
  if (!hasAutoCollapseTargetOpen()) return;
  panelAutoCollapseTimer = window.setTimeout(() => {
    panelAutoCollapseTimer = 0;
    if (panelAutoCollapseDisabled) return;
    if (!hasAutoCollapseTargetOpen()) return;
    toggleDateFilters(false, { skipAutoCollapseRefresh: true });
    toggleSystemSettings(false, { skipMobileScroll: true, skipPersist: true, skipAutoCollapseRefresh: true });
    toggleSystemStatusPanel(false, { skipPersist: true, skipAutoCollapseRefresh: true });
  }, panelAutoCollapseIdleMs);
}

function touchPanelAutoCollapseActivity() {
  if (panelAutoCollapseDisabled) {
    clearPanelAutoCollapseTimer();
    return;
  }
  if (!hasAutoCollapseTargetOpen()) {
    clearPanelAutoCollapseTimer();
    return;
  }
  schedulePanelAutoCollapseTimer();
}

function initPanelAutoCollapseIdleWatcher() {
  if (panelAutoCollapseBound) return;
  panelAutoCollapseBound = true;
  const passiveOptions = { passive: true };
  ["pointerdown", "touchstart", "wheel"].forEach((name) => {
    document.addEventListener(name, touchPanelAutoCollapseActivity, passiveOptions);
  });
  document.addEventListener("keydown", touchPanelAutoCollapseActivity);
  window.addEventListener("scroll", touchPanelAutoCollapseActivity, passiveOptions);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearPanelAutoCollapseTimer();
      return;
    }
    touchPanelAutoCollapseActivity();
  });
  touchPanelAutoCollapseActivity();
}

function syncMobileSystemSettingsQuickButton() {
  const btn = document.getElementById("btnMobileSystemSettingsQuick");
  const content = document.getElementById("systemSettingsContent");
  const card = document.getElementById("systemSettingsCard");
  if (!btn || !content) return;
  const open = !content.hidden;
  const mobile = isActualMobileViewport();
  btn.classList.toggle("active", open);
  btn.setAttribute("aria-pressed", open ? "true" : "false");
  if (card) {
    card.hidden = mobile ? !open : false;
  }
}

function syncMobileSearchResultsQuickButton() {
  const btn = document.getElementById("btnMobileToggleSearchResultsQuick");
  const content = document.getElementById("searchResultsContent");
  const card = document.getElementById("searchResultsCard");
  const labelEl = document.getElementById("mobileSearchResultsQuickLabel");
  if (!btn || !content) return;
  const open = !content.hidden;
  const mobile = shouldHideTopSearchBatchRow();
  const label = open ? "收起搜索结果" : "展开搜索结果";
  btn.classList.toggle("active", open);
  btn.setAttribute("aria-pressed", open ? "true" : "false");
  btn.setAttribute("aria-label", label);
  btn.setAttribute("title", label);
  if (card) {
    card.hidden = mobile ? !open : false;
  }
  if (labelEl) {
    labelEl.textContent = open ? "收起结果" : "展开结果";
    labelEl.setAttribute("aria-label", label);
    labelEl.setAttribute("title", label);
    labelEl.classList.toggle("active", open);
  }
}

function syncSearchResultsHeaderRowVisibility() {
  const row = document.getElementById("searchResultsHeaderRow");
  if (!row) return;
  row.hidden = shouldHideTopSearchBatchRow();
}

function toggleSystemSettings(forceOpen = null, options = {}) {
  const content = document.getElementById("systemSettingsContent");
  const btn = document.getElementById("btnToggleSystemSettings");
  const title = document.getElementById("systemSettingsTitle");
  if (!content || !btn) return;
  const wasHidden = !!content.hidden;
  let open;
  if (forceOpen === null) {
    open = content.hidden;
  } else {
    open = !!forceOpen;
  }
  content.hidden = !open;
  btn.textContent = open ? "▼" : "▶";
  btn.setAttribute("aria-expanded", String(open));
  if (title) title.setAttribute("aria-expanded", String(open));
  syncMobileSystemSettingsQuickButton();
  if (!options.skipPersist) {
    localStorage.setItem(SYSTEM_SETTINGS_OPEN_KEY, open ? "1" : "0");
  }
  if (open && wasHidden && !options.skipMobileScroll) {
    window.setTimeout(() => scrollExpandedSectionToTop(content), 40);
  } else if (!open && !wasHidden && !options.skipMobileScroll && isActualMobileViewport()) {
    window.setTimeout(() => scrollToTop(), 40);
  }
  if (!options.skipAutoCollapseRefresh) {
    touchPanelAutoCollapseActivity();
  }
}

function initSystemSettingsToggle() {
  const saved = localStorage.getItem(SYSTEM_SETTINGS_OPEN_KEY);
  const open = saved === "1";
  toggleSystemSettings(open, { skipMobileScroll: true, skipAutoCollapseRefresh: true });
  bindSectionTitleToggle("systemSettingsTitle", toggleSystemSettings);
}

function syncMobileFilterQuickButtons() {
  const gpsBtn = document.getElementById("btnMobileGpsFilter");
  const dateBtn = document.getElementById("btnMobileDateFilter");
  const gpsItem = document.getElementById("mobileGpsQuickItem");
  const dateItem = document.getElementById("mobileDateQuickItem");
  const gpsCard = document.getElementById("gpsFiltersCard");
  const dateCard = document.getElementById("dateFiltersCard");
  const gpsContent = document.getElementById("gpsFiltersContent");
  const dateContent = document.getElementById("dateFiltersContent");
  const gpsOpen = !!(gpsContent && !gpsContent.hidden);
  const dateOpen = !!(dateContent && !dateContent.hidden);
  const mobile = isActualMobileViewport();

  if (gpsBtn) {
    gpsBtn.classList.toggle("active", gpsOpen);
    gpsBtn.setAttribute("aria-pressed", gpsOpen ? "true" : "false");
  }
  if (gpsItem) gpsItem.classList.toggle("active", gpsOpen);
  if (dateBtn) {
    dateBtn.classList.toggle("active", dateOpen);
    dateBtn.setAttribute("aria-pressed", dateOpen ? "true" : "false");
  }
  if (dateItem) dateItem.classList.toggle("active", dateOpen);
  if (gpsCard) {
    gpsCard.hidden = mobile ? !gpsOpen : false;
  }
  if (dateCard) {
    dateCard.hidden = mobile ? !dateOpen : false;
  }
}

function toggleDateFilters(forceOpen = null, options = {}) {
  const content = document.getElementById("dateFiltersContent");
  const btn = document.getElementById("btnToggleDateFilters");
  const title = document.getElementById("dateFiltersTitle");
  if (!content || !btn) return;
  let open;
  if (forceOpen === null) {
    open = content.hidden;
  } else {
    open = !!forceOpen;
  }
  content.hidden = !open;
  btn.textContent = open ? "▼" : "▶";
  btn.setAttribute("aria-expanded", String(open));
  if (title) title.setAttribute("aria-expanded", String(open));
  syncMobileFilterQuickButtons();
  if (!options.skipAutoCollapseRefresh) {
    touchPanelAutoCollapseActivity();
  }
}

function initDateFiltersToggle() {
  toggleDateFilters(false, { skipAutoCollapseRefresh: true });
  bindSectionTitleToggle("dateFiltersTitle", toggleDateFilters);
}

function toggleGpsFilters(forceOpen = null, options = {}) {
  const content = document.getElementById("gpsFiltersContent");
  const btn = document.getElementById("btnToggleGpsFilters");
  const title = document.getElementById("gpsFiltersTitle");
  if (!content || !btn) return;
  let open;
  if (forceOpen === null) {
    open = content.hidden;
  } else {
    open = !!forceOpen;
  }
  content.hidden = !open;
  btn.textContent = open ? "▼" : "▶";
  btn.setAttribute("aria-expanded", String(open));
  if (title) title.setAttribute("aria-expanded", String(open));
  syncMobileFilterQuickButtons();
  if (!options.skipAutoCollapseRefresh) {
    touchPanelAutoCollapseActivity();
  }
}

function initGpsFiltersToggle() {
  toggleGpsFilters(false);
  bindSectionTitleToggle("gpsFiltersTitle", toggleGpsFilters);
}

function fitElementHeaderForMobile() {
  const header = document.querySelector(".element-header");
  if (!header) return;
  header.classList.remove("element-header-fit-1", "element-header-fit-2");
  if (window.innerWidth > 520) return;
  const isOverflow = () => header.scrollWidth > (header.clientWidth + 1);
  if (isOverflow()) header.classList.add("element-header-fit-1");
  if (isOverflow()) header.classList.add("element-header-fit-2");
}

function initElementHeaderFit() {
  fitElementHeaderForMobile();
  const onResize = () => {
    if (elementHeaderFitTimer) window.clearTimeout(elementHeaderFitTimer);
    elementHeaderFitTimer = window.setTimeout(() => {
      fitElementHeaderForMobile();
      elementHeaderFitTimer = 0;
    }, 80);
  };
  window.addEventListener("resize", onResize, { passive: true });
  window.addEventListener("orientationchange", () => {
    window.setTimeout(fitElementHeaderForMobile, 120);
  });
}

function fitElementGridForMobile() {
  const grid = document.querySelector(".element-grid");
  if (!grid) return;
  const props = [
    "--element-chip-font-size",
    "--element-chip-pad-y",
    "--element-chip-pad-x",
    "--element-chip-gap",
    "--element-chip-check-size",
  ];
  if (!isMobileViewport()) {
    props.forEach((name) => grid.style.removeProperty(name));
    return;
  }
  const presets = [
    { font: 0.94, padY: 0.23, padX: 0.54, gap: 0.38, check: 12 },
    { font: 0.9, padY: 0.21, padX: 0.48, gap: 0.34, check: 11 },
    { font: 0.86, padY: 0.19, padX: 0.42, gap: 0.3, check: 10 },
    { font: 0.82, padY: 0.17, padX: 0.38, gap: 0.27, check: 10 },
    { font: 0.78, padY: 0.16, padX: 0.34, gap: 0.24, check: 9 },
  ];
  const applyPreset = (preset) => {
    grid.style.setProperty("--element-chip-font-size", `${preset.font}rem`);
    grid.style.setProperty("--element-chip-pad-y", `${preset.padY}rem`);
    grid.style.setProperty("--element-chip-pad-x", `${preset.padX}rem`);
    grid.style.setProperty("--element-chip-gap", `${preset.gap}rem`);
    grid.style.setProperty("--element-chip-check-size", `${preset.check}px`);
  };
  let chosen = presets[presets.length - 1];
  for (const preset of presets) {
    applyPreset(preset);
    if (grid.scrollWidth <= grid.clientWidth + 1) {
      chosen = preset;
      break;
    }
  }
  applyPreset(chosen);
}

function initElementGridFit() {
  fitElementGridForMobile();
  const onResize = () => {
    if (elementGridFitTimer) window.clearTimeout(elementGridFitTimer);
    elementGridFitTimer = window.setTimeout(() => {
      fitElementGridForMobile();
      elementGridFitTimer = 0;
    }, 80);
  };
  window.addEventListener("resize", onResize, { passive: true });
  window.addEventListener("orientationchange", () => {
    window.setTimeout(fitElementGridForMobile, 120);
  }, { passive: true });
}

function toggleSearchResultsPanel(forceOpen = null, options = {}) {
  const content = document.getElementById("searchResultsContent");
  const btn = document.getElementById("btnToggleSearchResults");
  const title = document.getElementById("searchResultsTitle");
  if (!content) return;
  const wasHidden = !!content.hidden;
  let open;
  if (forceOpen === null) {
    open = content.hidden;
  } else {
    open = !!forceOpen;
  }
  content.hidden = !open;
  if (btn) {
    btn.textContent = open ? "▼" : "▶";
    btn.setAttribute("aria-expanded", String(open));
  }
  if (title) title.setAttribute("aria-expanded", String(open));
  syncMobileSearchResultsQuickButton();
  localStorage.setItem(SEARCH_RESULTS_OPEN_KEY, open ? "1" : "0");
  if (open && wasHidden && !options.skipMobileScroll) {
    window.setTimeout(() => scrollExpandedSectionToTop(content), 40);
  }
}

function initSearchResultsToggle() {
  const saved = localStorage.getItem(SEARCH_RESULTS_OPEN_KEY);
  const open = saved !== "0";
  toggleSearchResultsPanel(open, { skipMobileScroll: true });
  bindSectionTitleToggle("searchResultsTitle", toggleSearchResultsPanel);
}

function toggleSystemStatusPanel(forceOpen = null, options = {}) {
  const content = document.getElementById("systemStatusContent");
  const btn = document.getElementById("btnToggleSystemStatus");
  const title = document.getElementById("systemStatusTitle");
  if (!content || !btn) return;
  let open;
  if (forceOpen === null) {
    open = content.hidden;
  } else {
    open = !!forceOpen;
  }
  content.hidden = !open;
  btn.textContent = open ? "▼" : "▶";
  btn.setAttribute("aria-expanded", String(open));
  if (title) title.setAttribute("aria-expanded", String(open));
  if (!options.skipPersist) {
    localStorage.setItem(SYSTEM_STATUS_OPEN_KEY, open ? "1" : "0");
  }
  if (!options.skipAutoCollapseRefresh) {
    touchPanelAutoCollapseActivity();
  }
}

function initSystemStatusToggle() {
  const saved = localStorage.getItem(SYSTEM_STATUS_OPEN_KEY);
  const open = saved === "1";
  toggleSystemStatusPanel(open, { skipAutoCollapseRefresh: true });
  bindSectionTitleToggle("systemStatusTitle", toggleSystemStatusPanel);
}

function toggleUsageGuide(forceOpen = null) {
  const content = document.getElementById("usageGuideContent");
  const btn = document.getElementById("btnToggleUsageGuide");
  if (!content || !btn) return;
  let open;
  if (forceOpen === null) {
    open = content.hidden;
  } else {
    open = !!forceOpen;
  }
  content.hidden = !open;
  btn.textContent = open ? "隐藏使用说明" : "查看使用说明";
  localStorage.setItem(USAGE_GUIDE_OPEN_KEY, open ? "1" : "0");
}

function initUsageGuideToggle() {
  const saved = localStorage.getItem(USAGE_GUIDE_OPEN_KEY);
  const open = saved === "1";
  toggleUsageGuide(open);
}

function getLightboxTriggerMode() {
  const el = document.getElementById("lightboxTriggerMode");
  const value = el ? String(el.value || "dblclick").toLowerCase() : "dblclick";
  return value === "click" ? "click" : "dblclick";
}

function initLightboxTriggerMode() {
  const el = document.getElementById("lightboxTriggerMode");
  if (!el) return;
  const saved = localStorage.getItem(LIGHTBOX_TRIGGER_KEY);
  if (saved === "click" || saved === "dblclick") {
    el.value = saved;
  } else {
    el.value = "dblclick";
    localStorage.setItem(LIGHTBOX_TRIGGER_KEY, "dblclick");
  }
  el.addEventListener("change", () => {
    const mode = getLightboxTriggerMode();
    localStorage.setItem(LIGHTBOX_TRIGGER_KEY, mode);
    setText("searchStatus", mode === "click" ? "已切换为单击放大" : "已切换为双击放大");
  });
}

function getLightboxQualitySize() {
  const el = document.getElementById("lightboxQuality");
  const value = el ? parseInt(String(el.value || LIGHTBOX_QUALITY_DEFAULT), 10) : LIGHTBOX_QUALITY_DEFAULT;
  if (!Number.isFinite(value)) return LIGHTBOX_QUALITY_DEFAULT;
  if (!LIGHTBOX_QUALITY_OPTIONS.includes(value)) return LIGHTBOX_QUALITY_DEFAULT;
  return value;
}

function initLightboxQuality() {
  const el = document.getElementById("lightboxQuality");
  if (!el) return;
  const saved = parseInt(String(localStorage.getItem(LIGHTBOX_QUALITY_KEY) || ""), 10);
  const initial = LIGHTBOX_QUALITY_OPTIONS.includes(saved) ? saved : LIGHTBOX_QUALITY_DEFAULT;
  el.value = String(initial);
  localStorage.setItem(LIGHTBOX_QUALITY_KEY, String(initial));
  el.addEventListener("change", () => {
    const size = getLightboxQualitySize();
    localStorage.setItem(LIGHTBOX_QUALITY_KEY, String(size));
    clearLightboxCacheAll();
    setText("searchStatus", `已切换放大精细度：${size}`);
    if (currentResultsData && Array.isArray(currentResultsData.results) && currentResultsData.results.length > 0) {
      renderResults(currentResultsData);
    }
  });
}

function setStandardActionStatus(text) {
  setText("standardActionStatus", text || "");
}

function setStandardPoolStatus(text) {
  setText("standardPoolStatus", text || "");
}

function shortPath(path) {
  if (!path) return "";
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

function splitFileNameExt(fileName) {
  const raw = String(fileName || "");
  const dot = raw.lastIndexOf(".");
  if (dot <= 0) return { stem: raw, ext: "" };
  return { stem: raw.slice(0, dot), ext: raw.slice(dot) };
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getStandardPhotoIds() {
  return standardPhotoPool.map((it) => Number(it.photo_id)).filter((id) => Number.isFinite(id) && id > 0);
}

function makeResultActionKey(type, photoId) {
  return `${String(type || "")}:${Number(photoId || 0)}`;
}

function setResultActionPending(type, photoId, pending = true) {
  const key = makeResultActionKey(type, photoId);
  if (pending) {
    resultActionPendingKeys.add(key);
  } else {
    resultActionPendingKeys.delete(key);
  }
}

function getResultActionFlash(type, photoId) {
  const key = makeResultActionKey(type, photoId);
  const item = resultActionFlashMap.get(key);
  if (!item) return "";
  if (item.expireAt <= Date.now()) {
    resultActionFlashMap.delete(key);
    return "";
  }
  return String(item.state || "");
}

function setResultActionFlash(type, photoId, state = "success", ttlMs = RESULT_ACTION_FLASH_MS) {
  const key = makeResultActionKey(type, photoId);
  const expireAt = Date.now() + Math.max(200, Number(ttlMs || RESULT_ACTION_FLASH_MS));
  resultActionFlashMap.set(key, { state, expireAt });
  setTimeout(() => {
    const latest = resultActionFlashMap.get(key);
    if (!latest) return;
    if (latest.expireAt <= Date.now()) {
      resultActionFlashMap.delete(key);
      refreshResultActionButtons();
    }
  }, Math.max(220, Number(ttlMs || RESULT_ACTION_FLASH_MS) + 60));
}

function applyResultActionButtonVisual(btn, text, stateClass = "", disabled = false) {
  if (!btn) return;
  btn.textContent = text;
  btn.classList.remove(
    "btn-result-action-pending",
    "btn-result-action-success",
    "btn-result-action-error",
    "btn-result-action-active",
  );
  if (stateClass) btn.classList.add(stateClass);
  btn.disabled = !!disabled;
  if (disabled) {
    btn.setAttribute("aria-disabled", "true");
  } else {
    btn.removeAttribute("aria-disabled");
  }
}

function refreshResultActionButtons(root = document.getElementById("results")) {
  const container = root || document.getElementById("results");
  if (!container) return;
  const standardIds = new Set(getStandardPhotoIds());
  const currentGpsPhotoId = gpsCenter && Number.isFinite(Number(gpsCenter.photoId))
    ? Number(gpsCenter.photoId)
    : 0;
  const renameBlocked = isRenameBlockedByScan();

  container.querySelectorAll(".set-standard-photo").forEach((btn) => {
    const photoId = parseInt(btn.dataset.photoId || "", 10);
    if (Number.isNaN(photoId) || photoId <= 0) return;
    const key = makeResultActionKey("standard", photoId);
    const pending = resultActionPendingKeys.has(key);
    const flash = getResultActionFlash("standard", photoId);
    const alreadyStandard = standardIds.has(photoId);
    if (pending) {
      btn.setAttribute("aria-busy", "true");
      applyResultActionButtonVisual(btn, "处理中...", "btn-result-action-pending", true);
      return;
    }
    btn.removeAttribute("aria-busy");
    if (flash === "error") {
      applyResultActionButtonVisual(btn, "设置失败", "btn-result-action-error", false);
      return;
    }
    if (alreadyStandard) {
      if (flash === "success") {
        applyResultActionButtonVisual(btn, "已设置✓", "btn-result-action-success", true);
      } else {
        applyResultActionButtonVisual(btn, "已设为标准", "btn-result-action-active", true);
      }
      return;
    }
    applyResultActionButtonVisual(btn, "标准照片", "", false);
  });

  container.querySelectorAll(".set-gps-center").forEach((btn) => {
    const photoId = parseInt(btn.dataset.photoId || "", 10);
    if (Number.isNaN(photoId) || photoId <= 0) return;
    const isCurrentCenter = currentGpsPhotoId > 0 && currentGpsPhotoId === photoId;
    if (isCurrentCenter) {
      const flash = getResultActionFlash("gps", photoId);
      if (flash === "success") {
        applyResultActionButtonVisual(btn, "已设置✓", "btn-result-action-success", true);
      } else {
        applyResultActionButtonVisual(btn, "当前GPS中心", "btn-result-action-active", true);
      }
      return;
    }
    applyResultActionButtonVisual(btn, "GPS中心", "", false);
  });

  container.querySelectorAll(".rename-photo").forEach((btn) => {
    const photoId = parseInt(btn.dataset.photoId || "", 10);
    if (Number.isNaN(photoId) || photoId <= 0) return;
    const key = makeResultActionKey("rename", photoId);
    const pending = resultActionPendingKeys.has(key);
    const flash = getResultActionFlash("rename", photoId);
    if (pending) {
      btn.setAttribute("aria-busy", "true");
      applyResultActionButtonVisual(btn, "处理中...", "btn-result-action-pending", true);
      return;
    }
    btn.removeAttribute("aria-busy");
    if (renameBlocked) {
      applyResultActionButtonVisual(btn, "扫描中禁用", "btn-result-action-active", true);
      return;
    }
    if (flash === "error") {
      applyResultActionButtonVisual(btn, "重命名失败", "btn-result-action-error", false);
      return;
    }
    if (flash === "success") {
      applyResultActionButtonVisual(btn, "已重命名✓", "btn-result-action-success", false);
      return;
    }
    applyResultActionButtonVisual(btn, "重命名", "", false);
  });
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const toRad = (v) => (v * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return 6371.0 * c;
}

function getResultSortMode() {
  const el = document.getElementById("resultSortMode");
  const value = el ? String(el.value || "") : "";
  return value || RESULT_SORT_DEFAULT;
}

function getServerGlobalSortMode(mode = null) {
  const selectedMode = String(mode || getResultSortMode() || "").trim();
  return SERVER_GLOBAL_SORT_MODES.has(selectedMode) ? selectedMode : "";
}

function buildServerSortQueryParam(mode = null) {
  const sortMode = getServerGlobalSortMode(mode);
  if (!sortMode) return "";
  if (sortMode === "face_count_exact") {
    const exact = getResultFaceCountExactValue();
    return `&sort_mode=${encodeURIComponent(sortMode)}&face_count_exact=${encodeURIComponent(exact)}`;
  }
  return `&sort_mode=${encodeURIComponent(sortMode)}`;
}

function updateSortModeTip() {
  updateResultFaceCountExactControl();
  const tipEl = document.getElementById("sortModeTip");
  const sel = document.getElementById("resultSortMode");
  if (!tipEl || !sel) return;
  const label = sel.selectedOptions && sel.selectedOptions[0]
    ? sel.selectedOptions[0].textContent
    : "时间新→旧";
  const mode = getResultSortMode();
  if (mode === "face_count_exact") {
    const sourceItems = currentResultsData && Array.isArray(currentResultsData.results) ? currentResultsData.results : [];
    const maxCount = getFaceCountMaxForUi(sourceItems);
    const exactCount = getResultFaceCountExactValue(sourceItems);
    if (maxCount > 0 || sourceItems.length) {
      tipEl.textContent = `排序方式：${label}（${exactCount}/${maxCount}）`;
    } else {
      tipEl.textContent = `排序方式：${label}（范围待搜索）`;
    }
    return;
  }
  tipEl.textContent = `排序方式：${label}`;
}

function parseExifTime(value) {
  if (!value) return null;
  const text = String(value).trim();
  if (!text) return null;
  const ts = Date.parse(text.replace(" ", "T"));
  return Number.isFinite(ts) ? ts : null;
}

function splitFileName(filePath) {
  const fullName = shortPath(filePath || "");
  const pos = fullName.lastIndexOf(".");
  if (pos <= 0) {
    return { base: fullName, ext: "" };
  }
  return {
    base: fullName.slice(0, pos),
    ext: fullName.slice(pos + 1),
  };
}

function compareFilePathName(aPath, bPath) {
  const a = splitFileName(aPath);
  const b = splitFileName(bPath);
  const baseCmp = FILE_NAME_COLLATOR.compare(a.base, b.base);
  if (baseCmp !== 0) return baseCmp;
  const extCmp = FILE_NAME_COLLATOR.compare(a.ext, b.ext);
  if (extCmp !== 0) return extCmp;
  return FILE_NAME_COLLATOR.compare(String(aPath || ""), String(bPath || ""));
}

function getFengjingDistance(item) {
  if (!Number.isFinite(item.gps_lat) || !Number.isFinite(item.gps_lon)) {
    return null;
  }
  return haversineKm(Number(item.gps_lat), Number(item.gps_lon), REFERENCE_GPS.lat, REFERENCE_GPS.lon);
}

function compareNullableNumber(aNum, bNum, desc = false) {
  const aOk = Number.isFinite(aNum);
  const bOk = Number.isFinite(bNum);
  if (aOk && bOk) {
    return desc ? bNum - aNum : aNum - bNum;
  }
  if (aOk) return -1;
  if (bOk) return 1;
  return 0;
}

function parseFaceCount(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return null;
  return Math.trunc(n);
}

function getItemFaceCountOrZero(item) {
  const parsed = parseFaceCount(item && item.face_count);
  return parsed == null ? 0 : parsed;
}

function getMaxFaceCountInResults(items) {
  let maxCount = 0;
  (Array.isArray(items) ? items : []).forEach((item) => {
    const faceCount = getItemFaceCountOrZero(item);
    if (faceCount > maxCount) maxCount = faceCount;
  });
  return maxCount;
}

function getFaceCountMaxForUi(items = null) {
  const sourceItems = Array.isArray(items)
    ? items
    : (currentResultsData && Array.isArray(currentResultsData.results) ? currentResultsData.results : []);
  const localMax = getMaxFaceCountInResults(sourceItems);
  const debugMax = Number(currentResultsData && currentResultsData.debug && currentResultsData.debug.face_count_max);
  if (Number.isFinite(debugMax) && debugMax >= 0) {
    return Math.max(localMax, Math.trunc(debugMax));
  }
  return localMax;
}

function getResultFaceCountExactValue(items = null) {
  const inputEl = document.getElementById("resultFaceCountExact");
  const sourceItems = Array.isArray(items)
    ? items
    : (currentResultsData && Array.isArray(currentResultsData.results) ? currentResultsData.results : []);
  const maxCount = getFaceCountMaxForUi(sourceItems);
  let value = FACE_COUNT_EXACT_DEFAULT;
  if (inputEl) {
    const raw = String(inputEl.value || "").trim();
    const parsed = Number.parseInt(raw, 10);
    value = Number.isFinite(parsed) ? parsed : FACE_COUNT_EXACT_DEFAULT;
  }
  if (!sourceItems.length) {
    if (maxCount > 0) value = Math.max(0, Math.min(Math.trunc(value), maxCount));
    else value = Math.max(0, Math.trunc(value));
  } else if (maxCount <= 0) value = 0;
  else value = Math.max(0, Math.min(Math.trunc(value), maxCount));
  if (inputEl && String(inputEl.value || "") !== String(value)) inputEl.value = String(value);
  return value;
}

function updateResultFaceCountExactControl(items = null) {
  const wrapEl = document.getElementById("resultFaceCountExactWrap");
  const inputEl = document.getElementById("resultFaceCountExact");
  if (!wrapEl || !inputEl) return;
  const sortMode = getResultSortMode();
  const isExactMode = sortMode === "face_count_exact";
  wrapEl.hidden = !isExactMode;
  wrapEl.style.display = isExactMode ? "inline-flex" : "none";
  syncMobileSortBarPlacement();
  if (!isExactMode) return;
  const sourceItems = Array.isArray(items)
    ? items
    : (currentResultsData && Array.isArray(currentResultsData.results) ? currentResultsData.results : []);
  const maxCount = getFaceCountMaxForUi(sourceItems);
  inputEl.min = "0";
  if (maxCount > 0 || sourceItems.length) inputEl.max = String(maxCount);
  else inputEl.removeAttribute("max");
  inputEl.step = "1";
  const exact = getResultFaceCountExactValue(sourceItems);
  inputEl.title = (maxCount > 0 || sourceItems.length) ? `限定脸数（0-${maxCount}）` : "限定脸数（范围将随搜索结果更新）";
  if (String(inputEl.value || "") !== String(exact)) inputEl.value = String(exact);
}

function sortResults(items, mode) {
  const sorted = (Array.isArray(items) ? items : []).slice();
  const safeMode = mode || RESULT_SORT_DEFAULT;
  if (safeMode === "face_count_exact") {
    const exactCount = getResultFaceCountExactValue(sorted);
    const filtered = sorted.filter((item) => getItemFaceCountOrZero(item) === exactCount);
    filtered.sort((a, b) => {
      const tCmp = compareNullableNumber(parseExifTime(a.exif_datetime), parseExifTime(b.exif_datetime), true);
      if (tCmp !== 0) return tCmp;
      return compareFilePathName(a.file_path, b.file_path);
    });
    return filtered;
  }
  sorted.sort((a, b) => {
    switch (safeMode) {
      case "exif_desc": {
        const tCmp = compareNullableNumber(parseExifTime(a.exif_datetime), parseExifTime(b.exif_datetime), true);
        if (tCmp !== 0) return tCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
      case "exif_asc": {
        const tCmp = compareNullableNumber(parseExifTime(a.exif_datetime), parseExifTime(b.exif_datetime), false);
        if (tCmp !== 0) return tCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
      case "score_desc": {
        const sCmp = compareNullableNumber(Number(a.score), Number(b.score), true);
        if (sCmp !== 0) return sCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
      case "score_asc": {
        const sCmp = compareNullableNumber(Number(a.score), Number(b.score), false);
        if (sCmp !== 0) return sCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
      case "face_count_desc": {
        const cCmp = compareNullableNumber(parseFaceCount(a.face_count), parseFaceCount(b.face_count), true);
        if (cCmp !== 0) return cCmp;
        // For no-face or same-face-count photos, keep latest EXIF first.
        const tCmp = compareNullableNumber(parseExifTime(a.exif_datetime), parseExifTime(b.exif_datetime), true);
        if (tCmp !== 0) return tCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
      case "face_count_asc": {
        const cCmp = compareNullableNumber(parseFaceCount(a.face_count), parseFaceCount(b.face_count), false);
        if (cCmp !== 0) return cCmp;
        // For no-face or same-face-count photos, keep latest EXIF first.
        const tCmp = compareNullableNumber(parseExifTime(a.exif_datetime), parseExifTime(b.exif_datetime), true);
        if (tCmp !== 0) return tCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
      case "gps_reference_asc": {
        const dCmp = compareNullableNumber(getFengjingDistance(a), getFengjingDistance(b), false);
        if (dCmp !== 0) return dCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
      case "gps_reference_desc": {
        const dCmp = compareNullableNumber(getFengjingDistance(a), getFengjingDistance(b), true);
        if (dCmp !== 0) return dCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
      case "filename_desc":
        return -compareFilePathName(a.file_path, b.file_path);
      case "filename_asc":
        return compareFilePathName(a.file_path, b.file_path);
      default: {
        const tCmp = compareNullableNumber(parseExifTime(a.exif_datetime), parseExifTime(b.exif_datetime), true);
        if (tCmp !== 0) return tCmp;
        return compareFilePathName(a.file_path, b.file_path);
      }
    }
  });
  return sorted;
}

function getUploadedQueryFiles() {
  return uploadedQueryFiles.slice();
}

function makeFileSignature(file) {
  return `${file.name}::${file.size}::${file.lastModified}`;
}

function syncSelectedUploadedQueryFiles(files = uploadedQueryFiles) {
  const valid = new Set((files || []).map((file) => makeFileSignature(file)));
  for (const sign of Array.from(selectedUploadedQueryFileSigns)) {
    if (!valid.has(sign)) {
      selectedUploadedQueryFileSigns.delete(sign);
    }
  }
}

function syncSelectedStandardPhotoIds(items = standardPhotoPool) {
  const valid = new Set(
    (items || [])
      .map((it) => Number(it && it.photo_id))
      .filter((id) => Number.isFinite(id) && id > 0),
  );
  for (const id of Array.from(selectedStandardPhotoIds)) {
    if (!valid.has(id)) {
      selectedStandardPhotoIds.delete(id);
    }
  }
}

function updateUploadedQueryFileCount() {
  const countEl = document.getElementById("fileCount");
  if (!countEl) return;
  countEl.textContent = uploadedQueryFiles.length ? `已添加 ${uploadedQueryFiles.length} 张` : "未选择";
}

function removeSelectedUploadedQueryFiles() {
  syncSelectedUploadedQueryFiles(uploadedQueryFiles);
  if (!selectedUploadedQueryFileSigns.size) return 0;
  const before = uploadedQueryFiles.length;
  uploadedQueryFiles = uploadedQueryFiles.filter((file) => !selectedUploadedQueryFileSigns.has(makeFileSignature(file)));
  const removed = Math.max(0, before - uploadedQueryFiles.length);
  syncSelectedUploadedQueryFiles(uploadedQueryFiles);
  renderQueryPreviewFiles(uploadedQueryFiles);
  updateUploadedQueryFileCount();
  updateActionButtons();
  return removed;
}

function renderQueryPreviewFiles(files) {
  const preview = document.getElementById("queryPreview");
  if (!preview) return;
  const uploadFiles = Array.isArray(files) ? files.slice() : [];
  syncSelectedUploadedQueryFiles(uploadFiles);
  syncSelectedStandardPhotoIds(standardPhotoPool);
  if (previewUrls.length) {
    previewUrls.forEach((url) => URL.revokeObjectURL(url));
    previewUrls = [];
  }
  preview.innerHTML = "";
  preview.classList.remove("query-preview-grid", "query-preview-names", "query-preview-standard", "query-preview-combined");
  if (!uploadFiles.length && !standardPhotoPool.length) {
    preview.style.display = "none";
    return;
  }
  preview.style.display = "block";
  preview.classList.add("query-preview-combined");

  if (uploadFiles.length) {
    const uploadSection = document.createElement("section");
    uploadSection.className = "query-preview-section";
    const uploadTitle = document.createElement("div");
    uploadTitle.className = "query-preview-section-title";
    uploadTitle.textContent = "上传标准照片";
    uploadSection.appendChild(uploadTitle);
    if (uploadFiles.length > 4) {
      uploadSection.classList.add("query-preview-names");
      const list = document.createElement("ul");
      list.className = "query-name-list";
      uploadFiles.forEach((file) => {
        const li = document.createElement("li");
        const row = document.createElement("label");
        row.className = "query-name-select-row";
        const sign = makeFileSignature(file);
        const box = document.createElement("input");
        box.type = "checkbox";
        box.className = "query-upload-select";
        box.dataset.fileSign = sign;
        box.checked = selectedUploadedQueryFileSigns.has(sign);
        const name = document.createElement("span");
        name.textContent = file.name || "未命名文件";
        row.appendChild(box);
        row.appendChild(name);
        li.appendChild(row);
        list.appendChild(li);
      });
      uploadSection.appendChild(list);
    } else {
      uploadSection.classList.add("query-preview-standard");
      const frag = document.createDocumentFragment();
      uploadFiles.forEach((file) => {
        const sign = makeFileSignature(file);
        const item = document.createElement("label");
        item.className = "standard-item query-standard-item query-standard-item-selectable";
        const box = document.createElement("input");
        box.type = "checkbox";
        box.className = "query-upload-select";
        box.dataset.fileSign = sign;
        box.checked = selectedUploadedQueryFileSigns.has(sign);
        const img = document.createElement("img");
        img.className = "standard-item-thumb query-standard-thumb";
        img.alt = file.name || "标准照片";
        const url = URL.createObjectURL(file);
        previewUrls.push(url);
        img.src = url;
        const text = document.createElement("span");
        text.className = "standard-item-text";
        const title = document.createElement("div");
        title.className = "query-standard-name";
        title.textContent = file.name || "未命名文件";
        const meta = document.createElement("small");
        meta.className = "query-standard-meta";
        meta.textContent = `大小: ${formatBytes(file.size || 0)}`;
        text.appendChild(title);
        text.appendChild(meta);
        item.appendChild(box);
        item.appendChild(img);
        item.appendChild(text);
        frag.appendChild(item);
      });
      uploadSection.appendChild(frag);
    }
    preview.appendChild(uploadSection);
  }

  if (standardPhotoPool.length) {
    const poolSection = document.createElement("section");
    poolSection.className = "query-preview-section";
    const poolTitle = document.createElement("div");
    poolTitle.className = "query-preview-section-title";
    poolTitle.textContent = "已添加标准照片（来自搜索结果）";
    poolSection.appendChild(poolTitle);
    const poolList = document.createElement("div");
    poolList.className = "query-preview-standard-list";
    standardPhotoPool.forEach((it) => {
      const item = document.createElement("label");
      item.className = "standard-item query-standard-item query-standard-item-selectable";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.className = "std-select";
      box.dataset.photoId = String(it.photo_id);
      box.checked = selectedStandardPhotoIds.has(Number(it.photo_id));
      const img = document.createElement("img");
      img.className = "standard-item-thumb query-standard-thumb";
      img.loading = "lazy";
      img.src = `${apiBase}/photos/${it.photo_id}/thumb?size=128`;
      img.alt = `标准照片#${it.photo_id}`;
      const text = document.createElement("span");
      text.className = "standard-item-text";
      const title = document.createElement("div");
      title.className = "query-standard-name";
      title.textContent = `#${it.photo_id} ${shortPath(it.file_path)}`;
      const meta = document.createElement("small");
      meta.className = "query-standard-meta";
      const faceCountText = `脸数: ${Number.isFinite(Number(it.face_count)) ? Math.max(0, Math.trunc(Number(it.face_count))) : 0}`;
      meta.textContent = it.exif_datetime ? `时间: ${it.exif_datetime} ｜ ${faceCountText}` : `时间: 未知 ｜ ${faceCountText}`;
      text.appendChild(title);
      text.appendChild(meta);
      item.appendChild(box);
      item.appendChild(img);
      item.appendChild(text);
      poolList.appendChild(item);
    });
    poolSection.appendChild(poolList);
    preview.appendChild(poolSection);
  }

  preview.querySelectorAll(".query-upload-select").forEach((box) => {
    box.addEventListener("change", () => {
      const sign = String(box.dataset.fileSign || "");
      if (!sign) return;
      if (box.checked) {
        selectedUploadedQueryFileSigns.add(sign);
      } else {
        selectedUploadedQueryFileSigns.delete(sign);
      }
      updateFaceMinMatchHint();
      updateActionButtons();
    });
  });
  preview.querySelectorAll(".std-select").forEach((box) => {
    box.addEventListener("change", () => {
      const id = Number(box.dataset.photoId);
      if (!Number.isFinite(id) || id <= 0) return;
      if (box.checked) {
        selectedStandardPhotoIds.add(id);
      } else {
        selectedStandardPhotoIds.delete(id);
      }
      updateFaceMinMatchHint();
      updateActionButtons();
    });
  });
  updateFaceMinMatchHint();
}

function renderStandardPhotoPool(data) {
  const items = (data && Array.isArray(data.items) ? data.items : []).map((it) => ({
    photo_id: Number(it.photo_id),
    file_path: it.file_path || "",
    exif_datetime: it.exif_datetime || "",
    face_count: Number.isFinite(Number(it.face_count)) ? Math.max(0, Math.trunc(Number(it.face_count))) : 0,
  })).filter((it) => Number.isFinite(it.photo_id) && it.photo_id > 0);
  standardPhotoPool = items;
  syncSelectedStandardPhotoIds(standardPhotoPool);
  renderQueryPreviewFiles(uploadedQueryFiles);
  updateActionButtons();
  refreshResultActionButtons();
}


function updateGpsCenterInfo() {
  const el = document.getElementById("gpsCenterInfo");
  if (!el) return;
  if (!gpsCenter || !gpsCenter.photoId) {
    el.textContent = "GPS中心：未设置";
    return;
  }
  const hasGps = gpsCenter.gpsLat !== null && gpsCenter.gpsLon !== null;
  if (hasGps) {
    el.textContent = `GPS中心：#${gpsCenter.photoId} ${shortPath(gpsCenter.filePath)} (${gpsCenter.gpsLat.toFixed(6)}, ${gpsCenter.gpsLon.toFixed(6)})`;
  } else {
    el.textContent = `GPS中心：#${gpsCenter.photoId} ${shortPath(gpsCenter.filePath)}（该照片暂无GPS）`;
  }
}


function setGpsCenter(photoId, filePath, gpsLat, gpsLon) {
  gpsCenter = {
    photoId,
    filePath: filePath || "",
    gpsLat: Number.isFinite(gpsLat) ? gpsLat : null,
    gpsLon: Number.isFinite(gpsLon) ? gpsLon : null,
  };
  updateGpsCenterInfo();
  if (gpsCenter.gpsLat === null || gpsCenter.gpsLon === null) {
    setText("searchStatus", "已设置中心照片，但该照片暂无GPS信息。可换一张后重试。");
  } else {
    setText("searchStatus", `已设置GPS中心：${shortPath(filePath)}`);
  }
  updateActionButtons();
  refreshResultActionButtons();
}

function clearGpsCenterState(clearResults = false) {
  gpsCenter = null;
  updateGpsCenterInfo();
  if (clearResults) {
    resetSearchSessionState();
    renderResults({ stage: 0, total: 0, results: [] });
  }
  updateActionButtons();
  refreshResultActionButtons();
}


async function apiFetch(url, options = {}) {
  const opts = { credentials: "same-origin", ...options };
  const res = await fetch(url, opts);
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("未登录，请先输入密码。");
  }
  if (!res.ok) {
    let msg = "";
    const contentType = String(res.headers.get("content-type") || "").toLowerCase();
    if (contentType.includes("application/json")) {
      try {
        const data = await res.json();
        msg = String((data && (data.message || data.detail)) || "").trim();
        if (!msg) {
          msg = JSON.stringify(data);
        }
      } catch (err) {
        msg = "";
      }
    }
    if (!msg) {
      msg = (await res.text()).trim();
    }
    const err = new Error(msg || res.statusText);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}


async function logoutCurrentUser() {
  if (logoutBusy) return;
  const btn = document.getElementById("btnLogoutCurrentUser");
  logoutBusy = true;
  if (btn) btn.disabled = true;
  setText("logoutStatus", "正在退出...");
  try {
    const data = await apiFetch(`${apiBase}/auth/logout`, { method: "POST" });
    setText("logoutStatus", (data && data.message) || "已退出登录，正在返回登录页...");
    window.location.href = "/login";
  } catch (err) {
    setText("logoutStatus", `退出失败：${err.message}`);
  } finally {
    logoutBusy = false;
    if (btn) btn.disabled = false;
  }
}


function isCurrentUserAdmin() {
  return !!(currentAuthState && currentAuthState.is_admin);
}


function setAdminPolicySectionStatus(text, ok = false) {
  const el = document.getElementById("adminPolicySectionStatus");
  if (!el) return;
  el.textContent = text || "";
  el.style.color = ok ? "#166534" : "";
}


function setPolicyEditorVerifyStatus(text, ok = false) {
  const el = document.getElementById("policyEditorVerifyStatus");
  if (!el) return;
  el.textContent = text || "";
  el.style.color = ok ? "#166534" : "";
}


function setPolicyEditorSaveStatus(text, ok = false) {
  const el = document.getElementById("policyEditorSaveStatus");
  if (!el) return;
  el.textContent = text || "";
  el.style.color = ok ? "#166534" : "";
}


function updateAdminPolicySettingsVisibility() {
  const section = document.getElementById("adminPolicySettingsSection");
  if (section) {
    section.hidden = !isCurrentUserAdmin();
  }
}


function getPolicyEditorElements() {
  return {
    modal: document.getElementById("policyEditorModal"),
    verifyPanel: document.getElementById("policyEditorVerifyPanel"),
    content: document.getElementById("policyEditorContent"),
    topDetails: document.getElementById("policyEditorTopDetails"),
    policiesList: document.getElementById("policyEditorPoliciesList"),
    passwordInput: document.getElementById("policyEditorVerifyPassword"),
    configPath: document.getElementById("policyEditorConfigPath"),
    btnVerify: document.getElementById("btnPolicyEditorVerify"),
    btnReload: document.getElementById("btnPolicyEditorReload"),
    btnAddPolicy: document.getElementById("btnPolicyEditorAddPolicy"),
    btnSave: document.getElementById("btnPolicyEditorSave"),
  };
}


function setPolicyEditorOpen(open) {
  const { modal } = getPolicyEditorElements();
  if (!modal) return;
  modal.hidden = !open;
  document.body.classList.toggle("policy-editor-open", !!open);
}


function resetPolicyEditorSession() {
  adminPolicyConfigToken = "";
  adminPolicyConfigStore = null;
  adminPolicyConfigPath = "";
  adminPolicyConfigBusy = false;
  adminPolicyConfigDirty = false;
  const { verifyPanel, content, topDetails, policiesList, passwordInput, configPath } = getPolicyEditorElements();
  if (verifyPanel) verifyPanel.hidden = false;
  if (content) content.hidden = true;
  if (topDetails) {
    topDetails.open = true;
    delete topDetails.dataset.initialized;
  }
  if (policiesList) policiesList.innerHTML = "";
  if (passwordInput) passwordInput.value = "";
  if (configPath) configPath.textContent = "-";
  setPolicyEditorVerifyStatus("");
  setPolicyEditorSaveStatus("");
  syncPolicyEditorBusyState();
}


function bindPolicyEditorEvents() {
  if (policyEditorEscBound) return;
  policyEditorEscBound = true;
  document.addEventListener("keydown", (ev) => {
    const { modal } = getPolicyEditorElements();
    if (!modal || modal.hidden) return;
    if (ev.key !== "Escape") return;
    ev.preventDefault();
    closePolicyEditorModal(false);
  });
  const { modal } = getPolicyEditorElements();
  if (!modal) return;
  const { topDetails } = getPolicyEditorElements();
  if (topDetails) {
    topDetails.addEventListener("toggle", () => {
      topDetails.dataset.initialized = "true";
      syncPolicyEditorTopSummary();
    });
  }
  modal.addEventListener("input", (ev) => {
    const target = ev.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.closest("#policyEditorContent")) return;
    adminPolicyConfigDirty = true;
    syncPolicyEditorBusyState();
  });
  modal.addEventListener("change", (ev) => {
    const target = ev.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.closest("#policyEditorContent")) return;
    adminPolicyConfigDirty = true;
    syncPolicyEditorBusyState();
  });
}


function applyPolicyEditorTopDetailsDefault() {
  const { topDetails } = getPolicyEditorElements();
  if (!topDetails) return;
  if (topDetails.dataset.initialized === "true") return;
  topDetails.open = !isMobileViewport();
  topDetails.dataset.initialized = "true";
  syncPolicyEditorTopSummary();
}


function syncPolicyEditorTopSummary() {
  const { topDetails } = getPolicyEditorElements();
  if (!topDetails) return;
  const summary = topDetails.querySelector(".policy-editor-top-summary");
  if (!summary) return;
  summary.textContent = topDetails.open ? "收起顶部控制" : "显示顶部控制";
}


function syncPolicyEditorBusyState() {
  const { btnVerify, btnReload, btnAddPolicy, btnSave } = getPolicyEditorElements();
  if (btnVerify) btnVerify.disabled = !!adminPolicyConfigBusy;
  if (btnReload) btnReload.disabled = !!adminPolicyConfigBusy || !adminPolicyConfigToken;
  if (btnAddPolicy) btnAddPolicy.disabled = !!adminPolicyConfigBusy || !adminPolicyConfigToken;
  if (btnSave) btnSave.disabled = !!adminPolicyConfigBusy || !adminPolicyConfigToken || !adminPolicyConfigStore;
}


function cloneAdminPolicyStore(store) {
  if (!store || typeof store !== "object") {
    return {
      version: 2,
      updated_at: "",
      default_deny: true,
      policies: [],
    };
  }
  return JSON.parse(JSON.stringify(store));
}


function normalizeAdminPolicyStore(store) {
  const data = cloneAdminPolicyStore(store);
  data.version = Number.parseInt(data.version, 10);
  if (!Number.isFinite(data.version) || data.version <= 0) {
    data.version = 2;
  }
  data.updated_at = String(data.updated_at || "");
  data.default_deny = !!data.default_deny;
  data.policies = Array.isArray(data.policies) ? data.policies : [];
  data.policies = data.policies.map((item, index) => ({
    id: String(item && item.id ? item.id : `user${index + 1}`),
    name: String(item && item.name ? item.name : ""),
    enabled: item ? !!item.enabled : true,
    is_admin: item ? !!item.is_admin : false,
    password: String(item && item.password ? item.password : ""),
    roots: Array.isArray(item && item.roots) ? item.roots.map((root) => String(root || "")) : [],
    note: String(item && item.note ? item.note : ""),
  }));
  return data;
}


function buildDefaultAdminPolicyItem() {
  const nextIndex = Array.isArray(adminPolicyConfigStore && adminPolicyConfigStore.policies)
    ? adminPolicyConfigStore.policies.length + 1
    : 1;
  return {
    id: `user${nextIndex}`,
    name: `用户${nextIndex}`,
    enabled: true,
    is_admin: false,
    password: "",
    roots: [""],
    note: "",
  };
}


function renderAdminPolicyEditor() {
  const store = normalizeAdminPolicyStore(adminPolicyConfigStore);
  adminPolicyConfigStore = store;
  const { policiesList, content, verifyPanel, configPath } = getPolicyEditorElements();
  if (verifyPanel) verifyPanel.hidden = true;
  if (content) content.hidden = false;
  if (configPath) configPath.textContent = adminPolicyConfigPath || "-";
  setPolicyEditorVerifyStatus("");
  applyPolicyEditorTopDetailsDefault();

  const versionInput = document.getElementById("policyEditorVersion");
  if (versionInput) versionInput.value = String(store.version || 2);
  const updatedAtInput = document.getElementById("policyEditorUpdatedAt");
  if (updatedAtInput) updatedAtInput.value = String(store.updated_at || "");
  const defaultDenyInput = document.getElementById("policyEditorDefaultDeny");
  if (defaultDenyInput) defaultDenyInput.checked = !!store.default_deny;

  if (!policiesList) return;
  if (!store.policies.length) {
    policiesList.innerHTML = `<div class="policy-editor-empty">当前没有策略，请先新增一条。</div>`;
    syncPolicyEditorBusyState();
    return;
  }

  const html = store.policies.map((policy, index) => {
    const roots = Array.isArray(policy.roots) && policy.roots.length ? policy.roots : [""];
    const rootsHtml = roots.map((root, rootIndex) => `
      <div class="policy-editor-root-row">
        <input
          type="text"
          class="form-control form-control-sm policy-editor-root-input"
          value="${escapeHtml(root)}"
          data-root-index="${rootIndex}"
          placeholder="例如：D:/photos">
        <button class="btn btn-outline btn-sm" type="button" onclick="removeAdminPolicyRoot(${index}, ${rootIndex})">删除目录</button>
      </div>
    `).join("");
    return `
      <div class="policy-editor-policy-card" data-policy-index="${index}">
        <div class="policy-editor-policy-header">
          <div class="policy-editor-policy-title">策略 ${index + 1}</div>
          <button class="btn btn-outline btn-sm" type="button" onclick="removeAdminPolicyItem(${index})">删除策略</button>
        </div>
        <div class="policy-editor-policy-grid">
          <label class="policy-editor-field">
            <span class="policy-editor-field-label">id</span>
            <input type="text" class="form-control form-control-sm" data-field="id" value="${escapeHtml(policy.id)}" placeholder="例如：admin">
          </label>
          <label class="policy-editor-field">
            <span class="policy-editor-field-label">name</span>
            <input type="text" class="form-control form-control-sm" data-field="name" value="${escapeHtml(policy.name)}" placeholder="显示名称">
          </label>
          <label class="policy-editor-field">
            <span class="policy-editor-field-label">password</span>
            <input type="text" class="form-control form-control-sm" data-field="password" value="${escapeHtml(policy.password)}" placeholder="访问密码">
          </label>
        </div>
        <div class="policy-editor-policy-grid policy-editor-policy-grid-wide">
          <label class="policy-editor-checkbox-row">
            <input type="checkbox" data-field="enabled" ${policy.enabled ? "checked" : ""}>
            <span>enabled</span>
          </label>
          <label class="policy-editor-checkbox-row">
            <input type="checkbox" data-field="is_admin" ${policy.is_admin ? "checked" : ""}>
            <span>is_admin</span>
          </label>
        </div>
        <label class="policy-editor-field">
          <span class="policy-editor-field-label">note</span>
          <input type="text" class="form-control form-control-sm" data-field="note" value="${escapeHtml(policy.note)}" placeholder="备注">
        </label>
        <div class="policy-editor-roots-wrap">
          <div class="policy-editor-roots-header">
            <div class="policy-editor-roots-title">roots</div>
            <button class="btn btn-outline btn-sm" type="button" onclick="addAdminPolicyRoot(${index})">新增目录</button>
          </div>
          ${rootsHtml}
        </div>
      </div>
    `;
  }).join("");
  policiesList.innerHTML = html;
  syncPolicyEditorBusyState();
}


function collectAdminPolicyStoreFromForm() {
  const versionInput = document.getElementById("policyEditorVersion");
  const updatedAtInput = document.getElementById("policyEditorUpdatedAt");
  const defaultDenyInput = document.getElementById("policyEditorDefaultDeny");
  const cards = Array.from(document.querySelectorAll(".policy-editor-policy-card"));
  const policies = cards.map((card) => {
    const getInput = (field) => card.querySelector(`[data-field="${field}"]`);
    const roots = Array.from(card.querySelectorAll(".policy-editor-root-input"))
      .map((input) => String(input.value || "").trim())
      .filter((value) => value);
    return {
      id: String((getInput("id") && getInput("id").value) || "").trim(),
      name: String((getInput("name") && getInput("name").value) || "").trim(),
      enabled: !!(getInput("enabled") && getInput("enabled").checked),
      is_admin: !!(getInput("is_admin") && getInput("is_admin").checked),
      password: String((getInput("password") && getInput("password").value) || "").trim(),
      roots,
      note: String((getInput("note") && getInput("note").value) || "").trim(),
    };
  });
  return normalizeAdminPolicyStore({
    version: Number.parseInt(versionInput && versionInput.value ? versionInput.value : "2", 10),
    updated_at: String(updatedAtInput && updatedAtInput.value ? updatedAtInput.value : "").trim(),
    default_deny: !!(defaultDenyInput && defaultDenyInput.checked),
    policies,
  });
}


function syncAdminPolicyStoreFromForm() {
  adminPolicyConfigStore = collectAdminPolicyStoreFromForm();
  return adminPolicyConfigStore;
}


function closePolicyEditorModal(resetSession = true) {
  if (resetSession) {
    resetPolicyEditorSession();
  }
  setPolicyEditorOpen(false);
}


function openAdminPolicyEditor() {
  if (!isCurrentUserAdmin()) {
    setAdminPolicySectionStatus("仅管理员可进入权限配置界面。");
    return;
  }
  bindPolicyEditorEvents();
  resetPolicyEditorSession();
  setPolicyEditorOpen(true);
  const { passwordInput } = getPolicyEditorElements();
  if (passwordInput) passwordInput.focus();
  setAdminPolicySectionStatus("请再次输入管理员密码后进入配置界面。");
}


async function submitAdminPolicyReverify() {
  if (adminPolicyConfigBusy) return;
  const { passwordInput } = getPolicyEditorElements();
  const password = String(passwordInput && passwordInput.value ? passwordInput.value : "").trim();
  if (!password) {
    setPolicyEditorVerifyStatus("请输入当前管理员密码。");
    if (passwordInput) passwordInput.focus();
    return;
  }
  adminPolicyConfigBusy = true;
  syncPolicyEditorBusyState();
  setPolicyEditorVerifyStatus("正在验证管理员密码...", true);
  try {
    const data = await apiFetch(`${apiBase}/auth/admin/reverify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    adminPolicyConfigToken = String(data && data.token ? data.token : "").trim();
    if (!adminPolicyConfigToken) {
      throw new Error("管理员二次验证未返回有效令牌");
    }
    setPolicyEditorVerifyStatus("管理员验证通过，正在读取配置...", true);
    await loadAdminPolicyStore();
    if (passwordInput) passwordInput.value = "";
    setAdminPolicySectionStatus("已进入权限配置界面。", true);
  } catch (err) {
    adminPolicyConfigToken = "";
    setPolicyEditorVerifyStatus(`验证失败：${err.message}`);
  } finally {
    adminPolicyConfigBusy = false;
    syncPolicyEditorBusyState();
  }
}


async function loadAdminPolicyStore() {
  if (!adminPolicyConfigToken) {
    throw new Error("请先再次验证管理员密码。");
  }
  adminPolicyConfigBusy = true;
  syncPolicyEditorBusyState();
  try {
    const data = await apiFetch(`${apiBase}/auth/admin/policies`, {
      headers: { "X-Admin-Config-Token": adminPolicyConfigToken },
    });
    adminPolicyConfigStore = normalizeAdminPolicyStore(data && data.store ? data.store : null);
    adminPolicyConfigPath = String(data && data.config_path ? data.config_path : "");
    adminPolicyConfigDirty = false;
    renderAdminPolicyEditor();
    setPolicyEditorSaveStatus("已读取当前权限配置。", true);
    return data;
  } catch (err) {
    if (err && err.status === 403) {
      adminPolicyConfigToken = "";
      const { verifyPanel, content } = getPolicyEditorElements();
      if (verifyPanel) verifyPanel.hidden = false;
      if (content) content.hidden = true;
      setPolicyEditorVerifyStatus(err.message || "管理员二次验证已失效，请重新验证。");
    }
    throw err;
  } finally {
    adminPolicyConfigBusy = false;
    syncPolicyEditorBusyState();
  }
}


async function reloadAdminPolicyStore() {
  setPolicyEditorSaveStatus("");
  try {
    await loadAdminPolicyStore();
  } catch (err) {
    setPolicyEditorSaveStatus(`重新读取失败：${err.message}`);
  }
}


function addAdminPolicyItem() {
  syncAdminPolicyStoreFromForm();
  adminPolicyConfigStore.policies.push(buildDefaultAdminPolicyItem());
  adminPolicyConfigDirty = true;
  renderAdminPolicyEditor();
  window.requestAnimationFrame(() => {
    const cards = document.querySelectorAll(".policy-editor-policy-card");
    const lastCard = cards && cards.length ? cards[cards.length - 1] : null;
    if (!lastCard || !(lastCard instanceof HTMLElement)) return;
    lastCard.scrollIntoView({ behavior: "smooth", block: "start" });
    const firstInput = lastCard.querySelector('input[data-field="id"]');
    if (firstInput && firstInput instanceof HTMLElement) {
      window.setTimeout(() => {
        firstInput.focus();
        if ("select" in firstInput && typeof firstInput.select === "function") {
          firstInput.select();
        }
      }, 180);
    }
  });
}


function removeAdminPolicyItem(index) {
  syncAdminPolicyStoreFromForm();
  const safeIndex = Number(index);
  if (!Array.isArray(adminPolicyConfigStore.policies)) return;
  if (safeIndex < 0 || safeIndex >= adminPolicyConfigStore.policies.length) return;
  adminPolicyConfigStore.policies.splice(safeIndex, 1);
  adminPolicyConfigDirty = true;
  renderAdminPolicyEditor();
}


function addAdminPolicyRoot(index) {
  syncAdminPolicyStoreFromForm();
  const safeIndex = Number(index);
  const policy = adminPolicyConfigStore && Array.isArray(adminPolicyConfigStore.policies)
    ? adminPolicyConfigStore.policies[safeIndex]
    : null;
  if (!policy) return;
  if (!Array.isArray(policy.roots)) policy.roots = [];
  policy.roots.push("");
  adminPolicyConfigDirty = true;
  renderAdminPolicyEditor();
}


function removeAdminPolicyRoot(index, rootIndex) {
  syncAdminPolicyStoreFromForm();
  const safeIndex = Number(index);
  const safeRootIndex = Number(rootIndex);
  const policy = adminPolicyConfigStore && Array.isArray(adminPolicyConfigStore.policies)
    ? adminPolicyConfigStore.policies[safeIndex]
    : null;
  if (!policy || !Array.isArray(policy.roots)) return;
  if (safeRootIndex < 0 || safeRootIndex >= policy.roots.length) return;
  policy.roots.splice(safeRootIndex, 1);
  adminPolicyConfigDirty = true;
  renderAdminPolicyEditor();
}


async function saveAdminPolicyStore() {
  if (!adminPolicyConfigToken) {
    setPolicyEditorSaveStatus("管理员二次验证已失效，请重新进入配置界面。");
    return;
  }
  if (adminPolicyConfigBusy) return;
  const payload = syncAdminPolicyStoreFromForm();
  adminPolicyConfigBusy = true;
  syncPolicyEditorBusyState();
  setPolicyEditorSaveStatus("正在保存配置并生成备份...", true);
  try {
    const data = await apiFetch(`${apiBase}/auth/admin/policies`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Config-Token": adminPolicyConfigToken,
      },
      body: JSON.stringify(payload),
    });
    adminPolicyConfigStore = normalizeAdminPolicyStore(data && data.store ? data.store : payload);
    adminPolicyConfigPath = String(data && data.config_path ? data.config_path : adminPolicyConfigPath);
    adminPolicyConfigDirty = false;
    renderAdminPolicyEditor();
    const backupPath = String(data && data.backup_path ? data.backup_path : "").trim();
    const backupText = backupPath ? ` 备份：${backupPath}` : "";
    setPolicyEditorSaveStatus(`保存成功，当前配置已即时生效。${backupText}`, true);
    setAdminPolicySectionStatus("用户权限配置已保存并即时生效。", true);
    await loadAuthStatus();
  } catch (err) {
    setPolicyEditorSaveStatus(`保存失败：${err.message}`);
  } finally {
    adminPolicyConfigBusy = false;
    syncPolicyEditorBusyState();
  }
}


async function loadAuthStatus() {
  try {
    const data = await apiFetch(`${apiBase}/auth/status`);
    currentAuthState = data && typeof data === "object" ? data : null;
  } catch (err) {
    currentAuthState = null;
  } finally {
    updateAdminPolicySettingsVisibility();
  }
}


async function loadStandardPhotoPool(silent = false) {
  try {
    const data = await apiFetch(`${apiBase}/standard`);
    renderStandardPhotoPool(data);
    if (!silent) {
      setStandardActionStatus(`标准照片列表已刷新，共 ${getStandardPhotoIds().length} 张。`);
      setStandardPoolStatus("");
    }
  } catch (err) {
    setStandardActionStatus(`读取标准照片列表失败：${err.message}`);
  }
}


async function setStandardPhoto(photoId) {
  if (!photoId) return false;
  try {
    setStandardPoolStatus("正在添加标准照片...");
    const data = await apiFetch(`${apiBase}/standard`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_id: Number(photoId) }),
    });
    renderStandardPhotoPool(data);
    setStandardPoolStatus(`已添加到“已添加标准照片”列表，当前共 ${getStandardPhotoIds().length} 张。`);
    return true;
  } catch (err) {
    setStandardPoolStatus(`添加标准照片失败：${err.message}`);
    return false;
  }
}


async function deleteSelectedStandardPhotos() {
  const boxes = document.querySelectorAll(".std-select:checked");
  const ids = [];
  boxes.forEach((box) => {
    const id = parseInt(box.dataset.photoId || "", 10);
    if (!Number.isNaN(id)) ids.push(id);
  });
  const removedUploaded = removeSelectedUploadedQueryFiles();
  if (!ids.length && !removedUploaded) {
    setStandardActionStatus("请先勾选要删除的标准照片。");
    return;
  }
  if (!ids.length) {
    setStandardActionStatus(`已删除上传标准照片 ${removedUploaded} 张。`);
    return;
  }
  try {
    await apiFetch(`${apiBase}/standard`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_ids: ids }),
    });
    await loadStandardPhotoPool(true);
    if (removedUploaded > 0) {
      setStandardActionStatus(`已删除标准照片 ${ids.length} 张，上传标准照片 ${removedUploaded} 张。`);
    } else {
      setStandardActionStatus(`已删除 ${ids.length} 张标准照片。`);
    }
    setStandardPoolStatus("");
  } catch (err) {
    if (removedUploaded > 0) {
      setStandardActionStatus(`已删除上传标准照片 ${removedUploaded} 张；删除标准照片失败：${err.message}`);
    } else {
      setStandardActionStatus(`删除标准照片失败：${err.message}`);
    }
  }
}


async function clearAllStandardPhotos() {
  try {
    await apiFetch(`${apiBase}/standard`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    renderStandardPhotoPool({ items: [] });
    setStandardActionStatus("已清空标准照片。");
    setStandardPoolStatus("");
  } catch (err) {
    setStandardActionStatus(`清空标准照片失败：${err.message}`);
  }
}

function clearUploadedStandardPhotos() {
  const fileInput = document.getElementById("faceFile");
  uploadedQueryFiles = [];
  selectedUploadedQueryFileSigns.clear();
  if (fileInput) fileInput.value = "";
  renderQueryPreviewFiles([]);
  updateUploadedQueryFileCount();
  updateActionButtons();
}

async function clearAllStandardPhotosAndUploads() {
  try {
    await apiFetch(`${apiBase}/standard`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    renderStandardPhotoPool({ items: [] });
    clearUploadedStandardPhotos();
    clearGpsCenterState(true);
    setStandardActionStatus("已一键清空：添加的标准照片 + 上传的标准照片 + GPS中心及其结果。");
    setStandardPoolStatus("");
  } catch (err) {
    setStandardActionStatus(`清空所有失败：${err.message}`);
  }
}

function getDownloadDir() {
  const el = document.getElementById("downloadDir");
  return el ? el.value.trim() : "";
}

function initDownloadDir() {
  const el = document.getElementById("downloadDir");
  if (!el) return;
  const saved = localStorage.getItem("photo_search_download_dir") || "";
  if (saved && !el.value) {
    el.value = saved;
  }
  el.addEventListener("input", () => {
    localStorage.setItem("photo_search_download_dir", el.value.trim());
  });
}

function initQueryPreview() {
  const fileInput = document.getElementById("faceFile");
  const addBtn = document.getElementById("faceFileAddBtn");
  if (!fileInput) return;
  if (addBtn) {
    addBtn.addEventListener("click", () => fileInput.click());
  }

  fileInput.addEventListener("change", () => {
    const files = (fileInput.files && Array.from(fileInput.files)) || [];
    if (!files.length) return;
    const existed = new Set(uploadedQueryFiles.map((f) => makeFileSignature(f)));
    for (const file of files) {
      const sig = makeFileSignature(file);
      if (!existed.has(sig)) {
        uploadedQueryFiles.push(file);
        existed.add(sig);
      }
    }
    syncSelectedUploadedQueryFiles(uploadedQueryFiles);
    updateUploadedQueryFileCount();
    renderQueryPreviewFiles(uploadedQueryFiles);
    fileInput.value = "";
    updateActionButtons();
  });
}

function getSelectedElements() {
  const boxes = document.querySelectorAll(".element-check:checked");
  const values = [];
  boxes.forEach((box) => values.push(box.value));
  return values;
}

function ensureDualCheckboxMode(andEl, orEl, preferred = "and") {
  if (!andEl || !orEl) return preferred === "or" ? "or" : "and";
  let mode = preferred === "or" ? "or" : "and";
  if (andEl.checked && !orEl.checked) {
    mode = "and";
  } else if (!andEl.checked && orEl.checked) {
    mode = "or";
  }
  andEl.checked = mode === "and";
  orEl.checked = mode === "or";
  return mode;
}

function ensureElementModeState(preferred = "and") {
  const andEl = document.getElementById("elementModeAnd");
  const orEl = document.getElementById("elementModeOr");
  ensureDualCheckboxMode(andEl, orEl, preferred);
}

function ensureFaceModeState(preferred = "or") {
  const andEl = document.getElementById("faceModeAnd");
  const orEl = document.getElementById("faceModeOr");
  faceModeState = ensureDualCheckboxMode(andEl, orEl, preferred === "and" ? "and" : "or");
  return faceModeState;
}

function ensureTextModeState(preferred = "and") {
  const andEl = document.getElementById("textModeAnd");
  const orEl = document.getElementById("textModeOr");
  textModeState = ensureDualCheckboxMode(andEl, orEl, preferred);
  return textModeState;
}

function getElementMode() {
  ensureElementModeState("and");
  const orEl = document.getElementById("elementModeOr");
  return orEl && orEl.checked ? "or" : "and";
}

function syncFaceSearchCardVisibility() {
  const card = document.getElementById("faceSearchCard");
  if (!card) return;
  const faceEnabled = !!document.querySelector('.element-check[value="face"]:checked');
  card.hidden = !faceEnabled;
  card.setAttribute("aria-hidden", faceEnabled ? "false" : "true");
  const faceModeAndEl = document.getElementById("faceModeAnd");
  const faceModeOrEl = document.getElementById("faceModeOr");
  if (faceModeAndEl) faceModeAndEl.disabled = !faceEnabled;
  if (faceModeOrEl) faceModeOrEl.disabled = !faceEnabled;
  const faceModeEl = document.getElementById("faceMode");
  if (faceModeEl) faceModeEl.disabled = !faceEnabled;
  const minMatchEl = document.getElementById("faceMinMatch");
  if (minMatchEl) minMatchEl.disabled = !faceEnabled;
  const pruneEl = document.getElementById("facePruneToggle");
  if (pruneEl) pruneEl.disabled = !faceEnabled;
  syncFaceMinMatchModeConstraint();
  updateFaceMinMatchHint();
}

function syncSceneSearchCardVisibility() {
  const card = document.getElementById("sceneSearchCard");
  if (!card) return;
  const sceneEnabled = !!document.querySelector('.element-check[value="scene"]:checked');
  card.hidden = !sceneEnabled;
  card.setAttribute("aria-hidden", sceneEnabled ? "false" : "true");
}

function syncFocusSearchCardVisibility() {
  const card = document.getElementById("focusSearchCard");
  if (!card) return;
  const focusEnabled = !!document.querySelector('.element-check[value="focus"]:checked');
  card.hidden = !focusEnabled;
  card.setAttribute("aria-hidden", focusEnabled ? "false" : "true");
  const boxes = document.querySelectorAll(".focus-mode-check");
  boxes.forEach((box) => {
    box.disabled = !focusEnabled;
  });
  if (!focusEnabled) return;
  const checked = Array.from(boxes).filter((box) => box.checked);
  if (!checked.length) {
    const center = document.querySelector('.focus-mode-check[value="center"]');
    if (center) center.checked = true;
  }
}

function syncTextSearchCardVisibility() {
  const card = document.getElementById("textSearchCard");
  if (!card) return;
  const textEnabled = !!document.querySelector('.element-check[value="text"]:checked');
  card.hidden = !textEnabled;
  card.setAttribute("aria-hidden", textEnabled ? "false" : "true");
  const textQueryEl = document.getElementById("textQuery");
  const textModeAndEl = document.getElementById("textModeAnd");
  const textModeOrEl = document.getElementById("textModeOr");
  const textAllTypesEl = document.getElementById("textAllTypes");
  const lockToAllTypes = textEnabled && !!(textAllTypesEl && textAllTypesEl.checked);
  if (lockToAllTypes && textModeAndEl && textModeOrEl) {
    textModeAndEl.checked = false;
    textModeOrEl.checked = true;
    textModeState = "or";
  }
  if (textModeAndEl) textModeAndEl.disabled = !textEnabled || lockToAllTypes;
  if (textModeOrEl) textModeOrEl.disabled = !textEnabled;
  if (textAllTypesEl) textAllTypesEl.disabled = !textEnabled;
  const textModeEl = document.getElementById("textMode");
  const textScopeEl = document.getElementById("textScopeAny");
  if (textModeEl) textModeEl.disabled = !textEnabled || lockToAllTypes;
  if (textScopeEl) textScopeEl.disabled = !textEnabled;
  if (textQueryEl) {
    textQueryEl.readOnly = lockToAllTypes;
    if (lockToAllTypes) textQueryEl.value = SUPPORTED_IMAGE_SUFFIX_QUERY;
  }
  if (lockToAllTypes) ensureTextModeState("or");
}

function getTextQuery() {
  if (isTextAllTypesEnabled()) {
    return SUPPORTED_IMAGE_SUFFIX_QUERY;
  }
  const el = document.getElementById("textQuery");
  return el ? el.value.trim() : "";
}

function getTextScope() {
  const el = document.getElementById("textScopeAny");
  return el && el.checked ? "any" : "parent";
}

function isTextAllTypesEnabled() {
  const el = document.getElementById("textAllTypes");
  return !!(el && el.checked);
}

function normalizeKeywordQuery(text) {
  return String(text || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

function getTextModeRaw() {
  const textModeAndEl = document.getElementById("textModeAnd");
  const textModeOrEl = document.getElementById("textModeOr");
  if (textModeAndEl && textModeOrEl) {
    if (textModeAndEl.checked && !textModeOrEl.checked) {
      textModeState = "and";
      return textModeState;
    }
    if (!textModeAndEl.checked && textModeOrEl.checked) {
      textModeState = "or";
      return textModeState;
    }
    return ensureTextModeState(textModeState);
  }
  const el = document.getElementById("textMode");
  const value = el ? String(el.value || "").toLowerCase() : "and";
  return value === "or" ? "or" : "and";
}

function getTextMode() {
  if (isTextAllTypesEnabled()) {
    return ensureTextModeState("or");
  }
  return getTextModeRaw();
}

function getFaceMode() {
  const faceModeAndEl = document.getElementById("faceModeAnd");
  const faceModeOrEl = document.getElementById("faceModeOr");
  if (faceModeAndEl && faceModeOrEl) {
    if (faceModeAndEl.checked && !faceModeOrEl.checked) {
      faceModeState = "and";
      return faceModeState;
    }
    if (!faceModeAndEl.checked && faceModeOrEl.checked) {
      faceModeState = "or";
      return faceModeState;
    }
    return ensureFaceModeState(faceModeState);
  }
  const el = document.getElementById("faceMode");
  const value = el ? String(el.value || "").toLowerCase() : "or";
  return value === "and" ? "and" : "or";
}

function getFacePruneEnabled() {
  const el = document.getElementById("facePruneToggle");
  return !el || !!el.checked;
}

function syncFaceMinMatchModeConstraint(options = {}) {
  const el = document.getElementById("faceMinMatch");
  if (!el) return;
  const coerceValue = options.coerceValue !== false;
  const faceEnabled = !!document.querySelector('.element-check[value="face"]:checked');
  const faceMode = getFaceMode();
  const lockToOne = faceEnabled && faceMode !== "and";
  el.step = "1";
  if (lockToOne) {
    el.min = "1";
    if (String(el.value || "").trim() !== "1") el.value = "1";
    el.max = "1";
    el.readOnly = true;
    el.placeholder = "固定 1";
    el.setAttribute("aria-readonly", "true");
    return;
  }
  // Keep HTML min at 1 to avoid some mobile browsers blocking delete/edit when value is a single digit.
  // AND-mode lower bound is still enforced by JS normalization + backend validation.
  el.min = "1";
  if (coerceValue && faceEnabled && faceMode === "and") {
    const raw = String(el.value || "").trim();
    if (raw && Number.parseInt(raw, 10) < 2) el.value = "2";
  }
  el.max = "";
  el.readOnly = false;
  el.placeholder = "自动";
  el.removeAttribute("aria-readonly");
}

function getFocusModes() {
  const boxes = Array.from(document.querySelectorAll(".focus-mode-check"));
  if (!boxes.length) return ["center"];
  const values = boxes
    .filter((box) => box.checked)
    .map((box) => String(box.value || "").toLowerCase())
    .filter((v) => ["center", "vertical", "cross", "horizontal"].includes(v));
  if (values.length) return values;
  const center = boxes.find((box) => String(box.value || "").toLowerCase() === "center");
  if (center) center.checked = true;
  return ["center"];
}

function getFaceMinMatchValue(options = {}) {
  const el = document.getElementById("faceMinMatch");
  const normalizeInput = options.normalizeInput !== false;
  const fallbackToDefault = options.fallbackToDefault !== false;
  const faceMode = getFaceMode();
  const raw = el ? String(el.value || "").trim() : "";
  if (!raw) {
    if (!fallbackToDefault) {
      return null;
    }
    const fallbackValue = faceMode !== "and" ? 1 : 2;
    if (normalizeInput && el && String(el.value || "") !== String(fallbackValue)) {
      el.value = String(fallbackValue);
    }
    return fallbackValue;
  }
  let value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value < 1) value = 1;
  if (faceMode !== "and") value = 1;
  else if (value < 2) value = 2;
  value = Math.max(1, Math.trunc(value));
  if (normalizeInput && el && String(el.value || "") !== String(value)) el.value = String(value);
  return value;
}

function getKnownStandardFaceCount() {
  let total = 0;
  for (const it of standardPhotoPool || []) {
    const count = Number(it && it.face_count);
    if (Number.isFinite(count) && count > 0) {
      total += Math.trunc(count);
    }
  }
  return Math.max(0, total);
}

function getFaceAndConstraintGuard(files = null) {
  const elements = getSelectedElements();
  const wantsFace = elements.includes("face");
  if (!wantsFace) return { blocked: false, message: "" };
  if (getFaceMode() !== "and") return { blocked: false, message: "" };
  const uploaded = Array.isArray(files) ? files : getUploadedQueryFiles();
  if (uploaded.length > 0) return { blocked: false, message: "" };
  const knownFaceCount = getKnownStandardFaceCount();
  if (knownFaceCount > 0 && knownFaceCount < 2) {
    return {
      blocked: true,
      message: "人脸 AND 模式至少需要 2 张可匹配人脸。当前标准照片总脸数不足 2，请补充标准照片或改为 OR。",
    };
  }
  return { blocked: false, message: "" };
}

function updateFaceMinMatchHint() {
  const hintEl = document.getElementById("faceMinMatchHint");
  if (!hintEl) return;
  const wantsFace = !!document.querySelector('.element-check[value="face"]:checked');
  const faceMode = getFaceMode();
  const currentValue = getFaceMinMatchValue({ normalizeInput: false, fallbackToDefault: false });
  const currentText = currentValue == null ? "自动" : String(currentValue);
  const knownFaceCount = getKnownStandardFaceCount();
  const hasUploads = getUploadedQueryFiles().length > 0;
  if (!wantsFace) {
    hintEl.classList.remove("text-danger", "fw-bold");
    hintEl.textContent = `范围：1..待检测（当前 ${currentText}）`;
    return;
  }
  if (faceMode !== "and") {
    hintEl.classList.remove("text-danger", "fw-bold");
    hintEl.textContent = "范围：1（OR 模式固定为 1）";
    return;
  }
  const faceGuard = getFaceAndConstraintGuard();
  if (faceGuard.blocked) {
    hintEl.classList.add("text-danger", "fw-bold");
    hintEl.textContent = `范围：2（标准图总脸数不足 2，当前 ${currentText}）`;
    return;
  }
  hintEl.classList.remove("text-danger", "fw-bold");
  if (knownFaceCount > 0 && !hasUploads) {
    hintEl.textContent = `范围：2..${knownFaceCount}（当前 ${currentText}）`;
    return;
  }
  if (knownFaceCount > 0) {
    hintEl.textContent = `范围：2..待检测（标准图已知 ${knownFaceCount}，当前 ${currentText}）`;
    return;
  }
  hintEl.textContent = `范围：2..待检测（当前 ${currentText}）`;
}

function buildFaceMinMatchParam(wantsFace, files = null) {
  if (!wantsFace) return { ok: true, param: "" };
  const requested = getFaceMinMatchValue();
  if (requested == null) {
    return { ok: true, requested: null, param: "" };
  }
  const uploaded = Array.isArray(files) ? files : getUploadedQueryFiles();
  const hasUploads = uploaded.length > 0;
  const knownFaceCount = getKnownStandardFaceCount();
  if (!hasUploads && knownFaceCount > 0 && requested > knownFaceCount) {
    return {
      ok: false,
      message: `至少匹配人脸数不能大于标准照片总脸数（当前 ${knownFaceCount}）。`,
      param: "",
    };
  }
  return {
    ok: true,
    requested,
    param: `&min_match_faces=${encodeURIComponent(requested)}`,
  };
}

function formatSearchDebugText(debug) {
  if (!debug || typeof debug !== "object") return "";
  const counts = debug.element_counts && typeof debug.element_counts === "object" ? debug.element_counts : null;
  const elementOrder = ["face", "scene", "focus", "object", "building", "location", "text"];
  const countParts = [];
  if (counts) {
    elementOrder.forEach((key) => {
      const val = Number(counts[key]);
      if (Number.isFinite(val)) {
        countParts.push(`${key}:${Math.max(0, Math.trunc(val))}`);
      }
    });
  }
  const metricParts = [];
  const candidateCount = Number(debug.candidate_count);
  if (Number.isFinite(candidateCount)) {
    metricParts.push(`候选:${Math.max(0, Math.trunc(candidateCount))}`);
  }
  const overlapCount = Number(debug.face_text_overlap);
  if (Number.isFinite(overlapCount)) {
    metricParts.push(`face∩text:${Math.max(0, Math.trunc(overlapCount))}`);
  }
  const overlapDbCount = Number(debug.face_text_overlap_db);
  if (Number.isFinite(overlapDbCount)) {
    metricParts.push(`DB复核:${Math.max(0, Math.trunc(overlapDbCount))}`);
  }
  if (debug.face_text_overlap_db_sampled) {
    metricParts.push("DB复核(采样)");
  }
  if (typeof debug.face_prune_scores === "boolean") {
    metricParts.push(`人脸预裁剪:${debug.face_prune_scores ? "开" : "关"}`);
  }
  if (debug.face_mode) {
    metricParts.push(`人脸逻辑:${String(debug.face_mode).toUpperCase()}`);
  }
  const queryFaceCount = Number(debug.query_face_count);
  if (Number.isFinite(queryFaceCount)) {
    metricParts.push(`标准脸数:${Math.max(0, Math.trunc(queryFaceCount))}`);
  }
  const minMatchFaces = Number(debug.min_match_faces);
  if (Number.isFinite(minMatchFaces)) {
    metricParts.push(`至少匹配:${Math.max(1, Math.trunc(minMatchFaces))}`);
  }
  const minMatchFacesRequested = Number(debug.min_match_faces_requested);
  if (Number.isFinite(minMatchFacesRequested) && (!Number.isFinite(minMatchFaces) || Math.trunc(minMatchFacesRequested) !== Math.trunc(minMatchFaces))) {
    metricParts.push(`请求匹配:${Math.max(1, Math.trunc(minMatchFacesRequested))}`);
  }
  if (debug.text_mode) {
    metricParts.push(`文字逻辑:${String(debug.text_mode).toUpperCase()}`);
  }
  if (debug.text_scope) {
    metricParts.push(`文字范围:${debug.text_scope}`);
  }
  if (Array.isArray(debug.focus_modes) && debug.focus_modes.length) {
    metricParts.push(`聚焦:${debug.focus_modes.join("+")}`);
  }
  if (debug.date_from || debug.date_to) {
    metricParts.push(`日期:${debug.date_from || "起始不限"}~${debug.date_to || "结束不限"}`);
  }
  const faceDbTotal = Number(debug.face_db_total);
  const faceIndexTotal = Number(debug.face_index_total);
  const faceCoverage = Number(debug.face_index_coverage);
  if (Number.isFinite(faceDbTotal) && Number.isFinite(faceIndexTotal)) {
    metricParts.push(`人脸索引:${Math.trunc(faceIndexTotal)}/${Math.trunc(faceDbTotal)}`);
  }
  if (Number.isFinite(faceCoverage)) {
    metricParts.push(`覆盖率:${(faceCoverage * 100).toFixed(2)}%`);
  }
  const computedCount = Number(debug.computed_count);
  if (Number.isFinite(computedCount)) {
    metricParts.push(`计算:${Math.max(0, Math.trunc(computedCount))}`);
  }
  const combinedCount = Number(debug.combined_count);
  if (Number.isFinite(combinedCount)) {
    metricParts.push(`返回:${Math.max(0, Math.trunc(combinedCount))}`);
  }
  if (!countParts.length && !metricParts.length) return "";
  const modeText = String(debug.element_mode || "").toUpperCase() || "N/A";
  const blocks = [];
  if (countParts.length) blocks.push(countParts.join(", "));
  if (metricParts.length) blocks.push(metricParts.join(", "));
  return ` ｜ 调试[${modeText}] ${blocks.join(" ｜ ")}`;
}

function isGpsRadiusValid() {
  const radiusEl = document.getElementById("gpsRadius");
  const radiusValue = radiusEl ? parseFloat(radiusEl.value) : 5;
  return Number.isFinite(radiusValue) && radiusValue >= 1 && radiusValue <= 50;
}

function canRunSearch() {
  const files = getUploadedQueryFiles();
  const standardIds = getStandardPhotoIds();
  const elements = getSelectedElements();
  if (!elements.length) return false;
  const wantsText = elements.includes("text");
  const wantsFace = elements.includes("face");
  const wantsFocus = elements.includes("focus");
  const hasNonText = elements.some((e) => e !== "text");
  const textQuery = getTextQuery();
  if (wantsText && !textQuery) return false;
  if (hasNonText && !files.length && !standardIds.length) return false;
  if (wantsFace) {
    const faceGuard = getFaceAndConstraintGuard(files);
    if (faceGuard.blocked) return false;
    const faceMinMatch = buildFaceMinMatchParam(true, files);
    if (!faceMinMatch.ok) return false;
  }
  if (wantsFocus && !getFocusModes().length) return false;
  return true;
}

function canRunGpsSearch() {
  return !!(gpsCenter && gpsCenter.photoId) && isGpsRadiusValid();
}

function canRunGpsElementSearch() {
  return canRunGpsSearch() && canRunSearch();
}

function resetSearchSessionState() {
  const oldSearchId = String(searchSessionState.searchId || "");
  if (oldSearchId) {
    clearSearchBatchClientCache(oldSearchId);
  } else {
    clearSearchBatchClientCache();
  }
  searchBatchQueuedTarget = 0;
  searchBatchLastNavTs = 0;
  searchBatchNavToken += 1;
  searchSessionState = {
    searchId: "",
    batch: 1,
    totalBatches: 1,
    total: 0,
    batchSize: 55,
  };
}

function setSearchBatchInfoText(text) {
  ["searchBatchInfo", "searchBatchInfoBottom", "searchBatchInfoSticky"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  });
}

function updateResultsGuideVisibility() {
  const guideEl = document.getElementById("resultsGuide");
  const toolbarEl = document.querySelector("#searchResultsContent .results-toolbar");
  if (!guideEl) {
    if (toolbarEl) toolbarEl.classList.remove("results-toolbar-guide-mode");
    return;
  }
  const hasResults = !!(currentResultsData && Array.isArray(currentResultsData.results) && currentResultsData.results.length > 0);
  const hasSearchSession = !!(searchSessionState && searchSessionState.searchId);
  const showGuide = !(hasResults || hasSearchSession);
  guideEl.hidden = !showGuide;
  if (toolbarEl) toolbarEl.classList.toggle("results-toolbar-guide-mode", showGuide);
}

function updateSearchBatchInfo() {
  const batchSize = Number(searchSessionState.batchSize || 55);
  const total = Number(searchSessionState.total || 0);
  const totalBatches = Math.max(1, Number(searchSessionState.totalBatches || 1));
  const batch = Math.max(1, Math.min(Number(searchSessionState.batch || 1), totalBatches));
  const hasSession = !!searchSessionState.searchId;
  const infoText = hasSession
    ? `\u7b2c ${batch}/${totalBatches} \u6279 \uff5c \u5171 ${total} \u6761 \uff5c \u6bcf\u6279 ${batchSize} \u5f20`
    : `\u6bcf\u6279${batchSize}\u5f20\uff0c\u7b49\u5f85\u641c\u7d22`;
  setSearchBatchInfoText(infoText);
  const bottomWrap = document.getElementById("searchBatchBottomWrap");
  if (bottomWrap) {
    bottomWrap.hidden = !hasSession;
  }
  updateResultsGuideVisibility();
}

function updateSearchBatchButtons(busy) {
  const hasSession = !!searchSessionState.searchId;
  const totalBatches = Math.max(1, Number(searchSessionState.totalBatches || 1));
  const batch = Math.max(1, Math.min(Number(searchSessionState.batch || 1), totalBatches));
  [
    [["btnSearchBatchFirst", "btnSearchBatchFirstBottom", "btnSearchBatchFirstMobile", "btnSearchBatchFirstDesktop"], busy || !hasSession || batch <= 1],
    [["btnSearchBatchPrev", "btnSearchBatchPrevBottom", "btnSearchBatchPrevMobile", "btnSearchBatchPrevDesktop"], busy || !hasSession || batch <= 1],
    [["btnSearchBatchNext", "btnSearchBatchNextBottom", "btnSearchBatchNextMobile", "btnSearchBatchNextDesktop"], busy || !hasSession || batch >= totalBatches],
    [["btnSearchBatchLast", "btnSearchBatchLastBottom", "btnSearchBatchLastMobile", "btnSearchBatchLastDesktop"], busy || !hasSession || batch >= totalBatches],
  ].forEach(([ids, disabled]) => {
    (ids || []).forEach((id) => {
      const btn = document.getElementById(id);
      if (btn) btn.disabled = disabled;
    });
  });
  const bottomWrap = document.getElementById("searchBatchBottomWrap");
  if (bottomWrap) {
    bottomWrap.hidden = !hasSession;
  }
}

function applySearchBatchStateFromResponse(data) {
  const oldSearchId = String(searchSessionState.searchId || "");
  const nextSearchId = String((data && data.search_id) || "");
  if (oldSearchId && oldSearchId !== nextSearchId) {
    clearSearchBatchClientCache(oldSearchId);
  }
  searchSessionState.searchId = nextSearchId;
  searchSessionState.batch = Math.max(1, Number((data && data.batch) || 1));
  searchSessionState.totalBatches = Math.max(1, Number((data && data.total_batches) || 1));
  searchSessionState.total = Math.max(0, Number((data && data.total) || 0));
  searchSessionState.batchSize = Math.max(1, Number((data && data.batch_size) || 55));
  if (nextSearchId) {
    const sortMode = getServerGlobalSortMode();
    const faceCountExact = sortMode === "face_count_exact" ? getResultFaceCountExactValue() : null;
    putSearchBatchCache(data, { sortMode, faceCountExact });
  }
  updateSearchBatchInfo();
}

async function loadSearchBatch(batch) {
  if (!searchSessionState.searchId) {
    setText("searchStatus", "当前没有可翻页的搜索结果。");
    return;
  }
  const totalBatches = Math.max(1, Number(searchSessionState.totalBatches || 1));
  const targetBatch = Math.max(1, Math.min(Number(batch || 1), totalBatches));
  if (searchBusy || gpsBusy || gpsElementBusy) {
    if (searchBusy && !gpsBusy && !gpsElementBusy) {
      searchBatchQueuedTarget = targetBatch;
      setText("searchStatus", `正在切换批次，已排队到第 ${targetBatch} 批...`);
    } else {
      setText("searchStatus", "已有查询任务进行中，请稍候。");
    }
    return;
  }
  if (targetBatch === Number(searchSessionState.batch || 1)) {
    setText("searchStatus", `已在第 ${targetBatch}/${totalBatches} 批。`);
    return;
  }
  const nowTs = Date.now();
  if (nowTs - searchBatchLastNavTs < SEARCH_BATCH_NAV_COOLDOWN_MS) {
    await sleep(SEARCH_BATCH_NAV_COOLDOWN_MS - (nowTs - searchBatchLastNavTs));
  }
  searchBatchLastNavTs = Date.now();
  const navToken = ++searchBatchNavToken;
  searchBusy = true;
  updateActionButtons();
  try {
    const sortMode = getServerGlobalSortMode();
    const faceCountExact = sortMode === "face_count_exact" ? getResultFaceCountExactValue() : null;
    const data = await fetchSearchBatchData(searchSessionState.searchId, targetBatch, {
      preferCache: true,
      sortMode,
      faceCountExact,
    });
    if (navToken !== searchBatchNavToken) return;
    renderResults(data);
    applySearchBatchStateFromResponse(data);
    setText("searchStatus", `已切换到第 ${searchSessionState.batch}/${searchSessionState.totalBatches} 批。`);
    prefetchSearchBatchAround();
  } catch (err) {
    if (navToken !== searchBatchNavToken) return;
    if (err && Number(err.status) === 404) {
      resetSearchSessionState();
      updateSearchBatchInfo();
      setText("searchStatus", "搜索结果会话已过期，请重新搜索。");
    } else {
      setText("searchStatus", `翻页失败：${err.message}`);
    }
  } finally {
    if (navToken === searchBatchNavToken) {
      searchBusy = false;
      updateActionButtons();
    }
    if (!searchBusy && searchBatchQueuedTarget && searchBatchQueuedTarget !== Number(searchSessionState.batch || 1)) {
      const queuedTarget = searchBatchQueuedTarget;
      searchBatchQueuedTarget = 0;
      await loadSearchBatch(queuedTarget);
    }
  }
}

async function goSearchBatchFirst() {
  await loadSearchBatch(1);
}

async function goSearchBatchPrev() {
  await loadSearchBatch(Math.max(1, Number(searchSessionState.batch || 1) - 1));
}

async function goSearchBatchNext() {
  await loadSearchBatch(Math.max(1, Number(searchSessionState.batch || 1) + 1));
}

async function goSearchBatchLast() {
  await loadSearchBatch(Math.max(1, Number(searchSessionState.totalBatches || 1)));
}

function updateActionButtons() {
  const searchButtons = [document.getElementById("btnRunSearch")].filter(Boolean);
  const gpsBtn = document.getElementById("btnRunGpsSearch");
  const gpsElementBtn = document.getElementById("btnRunGpsElementSearch");
  const downloadBtn = document.getElementById("btnDownloadSelected");
  const trashBtn = document.getElementById("btnTrashSelected");
  const standardDeleteBtn = document.getElementById("btnDeleteSelectedStandard");
  const standardClearBtn = document.getElementById("btnClearStandardPool");
  const standardClearAllBtn = document.getElementById("btnClearAllStandard");
  const standardRefreshBtn = document.getElementById("btnRefreshStandardPool");
  const busy = searchBusy || gpsBusy || gpsElementBusy;
  const warmReady = !!searchWarmReady;
  const warmTitle = searchWarmMessage || "系统预热中，请稍候...";

  if (searchButtons.length) {
    const faceGuard = getFaceAndConstraintGuard();
    const ready = warmReady && !busy && canRunSearch();
    searchButtons.forEach((searchBtn) => {
      searchBtn.disabled = !ready;
      searchBtn.classList.toggle("btn-ready", ready);
      searchBtn.textContent = searchRequestActive
        ? formatSearchRunningButtonText()
        : (searchBusy ? "处理中..." : "开始搜索");
      if (!warmReady) searchBtn.title = warmTitle;
      else if (faceGuard.blocked) searchBtn.title = faceGuard.message;
      else searchBtn.removeAttribute("title");
    });
  }

  if (gpsBtn) {
    const ready = warmReady && !busy && canRunGpsSearch();
    gpsBtn.disabled = !ready;
    gpsBtn.classList.toggle("btn-ready", ready);
    if (!warmReady) gpsBtn.title = warmTitle;
    else gpsBtn.removeAttribute("title");
  }

  if (gpsElementBtn) {
    const faceGuard = getFaceAndConstraintGuard();
    const ready = warmReady && !busy && canRunGpsElementSearch();
    gpsElementBtn.disabled = !ready;
    gpsElementBtn.classList.toggle("btn-ready", ready);
    if (!warmReady) gpsElementBtn.title = warmTitle;
    else if (faceGuard.blocked) gpsElementBtn.title = faceGuard.message;
    else gpsElementBtn.removeAttribute("title");
  }

  if (downloadBtn) {
    const selected = getSelectedPhotoIds().length;
    downloadBtn.disabled = downloadBusy || trashBusy || busy || selected <= 0;
  }
  if (trashBtn) {
    const selected = getSelectedPhotoIds().length;
    trashBtn.disabled = trashBusy || downloadBusy || busy || selected <= 0;
  }
  if (standardDeleteBtn) {
    const ready = selectedStandardPhotoIds.size > 0 || selectedUploadedQueryFileSigns.size > 0;
    standardDeleteBtn.classList.toggle("btn-function-active", ready);
  }
  if (standardClearBtn) {
    const ready = standardPhotoPool.length > 0;
    standardClearBtn.classList.toggle("btn-function-active", ready);
  }
  if (standardClearAllBtn) {
    const ready = standardPhotoPool.length > 0 || uploadedQueryFiles.length > 0 || !!(gpsCenter && gpsCenter.photoId);
    standardClearAllBtn.classList.toggle("btn-function-active", ready);
  }
  if (standardRefreshBtn) {
    standardRefreshBtn.classList.add("btn-function-active");
  }
  updateSearchBatchButtons(busy);
  updateSearchBatchInfo();
  updateIndexCompactButtons();
  refreshPcSidebarLayout();
}

function applySearchWarmStatus(data) {
  const ready = !(data && data.search_ready === false);
  const message = (data && data.search_ready_message) ? String(data.search_ready_message) : "系统预热中，请稍候...";
  searchWarmReady = !!ready;
  searchWarmMessage = message;
  const el = document.getElementById("searchWarmStatus");
  if (el) {
    el.hidden = !!ready;
    el.textContent = message;
  }
  updateActionButtons();
}

function ensureSearchWarmReady() {
  if (searchWarmReady) return true;
  setText("searchStatus", searchWarmMessage || "系统预热中，请稍候...");
  loadStatus();
  return false;
}

function updateIndexCompactButtons() {
  const ids = [
    "btnIndexCompactDryRun",
    "btnIndexCompactFace",
    "btnIndexCompactVision",
    "btnIndexCompactAll",
  ];
  const scanActive = isScanActiveStatus(latestScanProgress && latestScanProgress.status);
  const compactRunning = latestIndexCompactState && latestIndexCompactState.status === "running";
  ids.forEach((id) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.disabled = !!scanActive || !!compactRunning || !!indexCompactBusy;
  });
}

function bindActionStateWatchers() {
  const ids = [
    "faceFile",
    "faceMode",
    "faceMinMatch",
    "facePruneToggle",
    "textQuery",
    "textAllTypes",
    "textScopeAny",
    "textMode",
    "gpsRadius",
    "stage",
    "dateFrom",
    "dateTo",
    "resultSortMode",
    "resultFaceCountExact",
    "elementModeAnd",
    "elementModeOr",
  ];
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", updateActionButtons);
    el.addEventListener("change", updateActionButtons);
  });
  const handleFaceModeChange = () => {
    syncFaceMinMatchModeConstraint();
    updateFaceMinMatchHint();
    updateActionButtons();
  };
  const faceModeEl = document.getElementById("faceMode");
  if (faceModeEl) {
    faceModeEl.addEventListener("change", handleFaceModeChange);
  }
  const faceModeAndEl = document.getElementById("faceModeAnd");
  const faceModeOrEl = document.getElementById("faceModeOr");
  if (faceModeAndEl && faceModeOrEl) {
    faceModeAndEl.addEventListener("change", () => {
      ensureFaceModeState("and");
      handleFaceModeChange();
    });
    faceModeOrEl.addEventListener("change", () => {
      ensureFaceModeState("or");
      handleFaceModeChange();
    });
  }
  const textModeEl = document.getElementById("textMode");
  if (textModeEl) {
    textModeEl.addEventListener("change", updateActionButtons);
  }
  const textModeAndEl = document.getElementById("textModeAnd");
  const textModeOrEl = document.getElementById("textModeOr");
  if (textModeAndEl && textModeOrEl) {
    textModeAndEl.addEventListener("change", () => {
      ensureTextModeState("and");
      updateActionButtons();
    });
    textModeOrEl.addEventListener("change", () => {
      ensureTextModeState("or");
      updateActionButtons();
    });
  }
  const textAllTypesEl = document.getElementById("textAllTypes");
  if (textAllTypesEl) {
    textAllTypesEl.addEventListener("change", () => {
      const textQueryEl = document.getElementById("textQuery");
      const textModeAndEl = document.getElementById("textModeAnd");
      const textModeOrEl = document.getElementById("textModeOr");
      if (textAllTypesEl.checked) {
        textAllTypesPrevQuery = textQueryEl ? String(textQueryEl.value || "") : "";
        textAllTypesPrevMode = getTextModeRaw();
        if (textQueryEl) textQueryEl.value = SUPPORTED_IMAGE_SUFFIX_QUERY;
        if (textModeAndEl && textModeOrEl) {
          textModeAndEl.checked = false;
          textModeOrEl.checked = true;
        }
        textModeState = "or";
        ensureTextModeState("or");
      } else {
        const currentText = textQueryEl ? normalizeKeywordQuery(textQueryEl.value) : "";
        if (textQueryEl && currentText === SUPPORTED_IMAGE_SUFFIX_QUERY) {
          textQueryEl.value = textAllTypesPrevQuery;
        }
        textModeState = textAllTypesPrevMode === "or" ? "or" : "and";
        ensureTextModeState(textAllTypesPrevMode === "or" ? "or" : "and");
      }
      syncTextSearchCardVisibility();
      updateActionButtons();
    });
  }
  const elementModeAnd = document.getElementById("elementModeAnd");
  const elementModeOr = document.getElementById("elementModeOr");
  if (elementModeAnd) {
    elementModeAnd.addEventListener("change", () => {
      ensureElementModeState("and");
      updateActionButtons();
    });
  }
  if (elementModeOr) {
    elementModeOr.addEventListener("change", () => {
      ensureElementModeState("or");
      updateActionButtons();
    });
  }
  document.querySelectorAll(".element-check").forEach((el) => {
    el.addEventListener("change", () => {
      syncSceneSearchCardVisibility();
      syncFocusSearchCardVisibility();
      syncFaceSearchCardVisibility();
      syncTextSearchCardVisibility();
      updateActionButtons();
    });
  });
  document.querySelectorAll(".focus-mode-check").forEach((el) => {
    el.addEventListener("change", () => {
      if (!document.querySelector('.element-check[value="focus"]:checked')) return;
      const checkedCount = document.querySelectorAll(".focus-mode-check:checked").length;
      if (!checkedCount) {
        const center = document.querySelector('.focus-mode-check[value="center"]');
        if (center) center.checked = true;
      }
      updateActionButtons();
    });
  });
  const faceMinMatchEl = document.getElementById("faceMinMatch");
  if (faceMinMatchEl) {
    const syncFaceMinMatchInput = () => {
      // Keep raw typing on mobile; avoid forcing value while user is entering digits.
      syncFaceMinMatchModeConstraint({ coerceValue: false });
      updateFaceMinMatchHint();
      updateActionButtons();
    };
    const syncFaceMinMatchChange = () => {
      syncFaceMinMatchModeConstraint();
      getFaceMinMatchValue();
      updateFaceMinMatchHint();
      updateActionButtons();
    };
    faceMinMatchEl.addEventListener("input", syncFaceMinMatchInput);
    faceMinMatchEl.addEventListener("change", syncFaceMinMatchChange);
  }
  const textQueryEl = document.getElementById("textQuery");
  if (textQueryEl) {
    textQueryEl.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter") return;
      if (ev.isComposing) return;
      ev.preventDefault();
      runSearch();
    });
  }
  const sortEl = document.getElementById("resultSortMode");
  if (sortEl) {
    sortEl.addEventListener("change", () => applyResultSort({ silent: true }));
  }
  const faceCountExactEl = document.getElementById("resultFaceCountExact");
  if (faceCountExactEl) {
    faceCountExactEl.addEventListener("input", () => applyResultSort({ silent: true }));
    faceCountExactEl.addEventListener("change", () => applyResultSort({ silent: false }));
  }
}

function initDateRangeDefaults() {
  const fromEl = document.getElementById("dateFrom");
  const toEl = document.getElementById("dateTo");
  if (!fromEl || !toEl) return;
  if (!fromEl.value) fromEl.value = "";
  if (!toEl.value) toEl.value = "";
}

function setQuickDateRange(mode) {
  const fromEl = document.getElementById("dateFrom");
  const toEl = document.getElementById("dateTo");
  if (!fromEl || !toEl) return;
  if (mode === "all") {
    fromEl.value = "";
    toEl.value = "";
    updateActionButtons();
    return;
  }
  const now = new Date();
  const to = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const from = new Date(to);
  switch (mode) {
    case "1m":
      from.setMonth(from.getMonth() - 1);
      break;
    case "6m":
      from.setMonth(from.getMonth() - 6);
      break;
    case "1y":
      from.setFullYear(from.getFullYear() - 1);
      break;
    case "3y":
      from.setFullYear(from.getFullYear() - 3);
      break;
    case "5y":
      from.setFullYear(from.getFullYear() - 5);
      break;
    case "10y":
      from.setFullYear(from.getFullYear() - 10);
      break;
    default:
      return;
  }
  const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  fromEl.value = fmt(from);
  toEl.value = fmt(to);
  updateActionButtons();
}

function getDateRangeParams() {
  const fromEl = document.getElementById("dateFrom");
  const toEl = document.getElementById("dateTo");
  const params = [];
  if (fromEl && fromEl.value) params.push(`date_from=${fromEl.value}`);
  if (toEl && toEl.value) params.push(`date_to=${toEl.value}`);
  return params.length ? `&${params.join("&")}` : "";
}

function updateSelectedCount() {
  const countEl = document.getElementById("selectedCount");
  if (!countEl) return;
  countEl.textContent = `已选 ${globalPhotoSelection.size}`;
  updateActionButtons();
}

function selectAll(checked) {
  const boxes = document.querySelectorAll(".select-photo");
  boxes.forEach((box) => {
    box.checked = checked;
    const id = Number(box.dataset.photoId);
    if (checked) globalPhotoSelection.add(id); else globalPhotoSelection.delete(id);
  });
  updateSelectedCount();
}

async function applyResultSort(options = {}) {
  const silent = !!options.silent;
  updateResultFaceCountExactControl();
  updateSortModeTip();
  const hasSession = !!searchSessionState.searchId;
  const hasResults = currentResultsData && Array.isArray(currentResultsData.results) && currentResultsData.results.length > 0;
  if (!hasResults && !hasSession) {
    if (!silent) setText("searchStatus", "当前没有可排序的搜索结果。");
    return;
  }
  const sortMode = getResultSortMode();
  const serverSortMode = getServerGlobalSortMode(sortMode);
  const faceCountExact = serverSortMode === "face_count_exact" ? getResultFaceCountExactValue() : null;
  if (serverSortMode && searchSessionState.searchId) {
    try {
      const currentBatch = Math.max(1, Number(searchSessionState.batch || 1));
      const data = await fetchSearchBatchData(searchSessionState.searchId, currentBatch, {
        preferCache: false,
        sortMode: serverSortMode,
        faceCountExact,
      });
      renderResults(data);
      applySearchBatchStateFromResponse(data);
    } catch (err) {
      setText("searchStatus", `切换排序失败：${err.message}`);
      return;
    }
  } else {
    renderResults(currentResultsData);
  }
  if (!silent) {
    const sortLabel = document.getElementById("resultSortMode")?.selectedOptions?.[0]?.textContent || "当前规则";
    if (sortMode === "face_count_exact") {
      const exactCount = getResultFaceCountExactValue(currentResultsData.results);
      setText("searchStatus", `已按“${sortLabel}（${exactCount}）”筛选。`);
    } else {
      setText("searchStatus", `已按“${sortLabel}”排序。`);
    }
  }
}

function getSelectedPhotoIds() { return Array.from(globalPhotoSelection); }

async function browseDir() {
  const el = document.getElementById("downloadDir");
  if (!el) return;
  const current = String(el.value || "").trim();
  const input = window.prompt(
    "请输入下载目录完整路径（例如 D:\\Downloads\\photos）",
    current,
  );
  if (input === null) {
    setText("searchStatus", "已取消选择目录。");
    return;
  }
  const picked = String(input || "").trim().replace(/\//g, "\\").replace(/[\\]+$/, "");
  if (!picked) {
    setText("searchStatus", "目录不能为空。");
    return;
  }
  el.value = picked;
  localStorage.setItem("photo_search_download_dir", picked);
  setText("searchStatus", `已设置下载目录：${picked}`);
}

async function downloadSinglePhoto(photoId, filePath) {
  const id = Number(photoId);
  if (!Number.isFinite(id) || id <= 0) return;
  const fallbackName = `photo_${id}.jpg`;
  const downloadName = shortPath(filePath || "") || fallbackName;
  try {
    const res = await fetch(`${apiBase}/photos/${id}/file`);
    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || res.statusText || "下载失败");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1200);
    setText("searchStatus", `已开始下载：${downloadName}`);
  } catch (err) {
    setText("searchStatus", `单图下载失败：${err.message}`);
  }
}

function renderResults(data) {
  const container = document.getElementById("results");
  closeResultLightbox();
  const selectedBefore = new Set(getSelectedPhotoIds());
  const normalized = {
    stage: Number(data && data.stage ? data.stage : 0),
    total: Number(data && data.total ? data.total : 0),
    results: Array.isArray(data && data.results) ? data.results.slice() : [],
    debug: data && typeof data.debug === "object" ? data.debug : null,
  };
  currentResultsData = normalized;
  refreshPcSidebarLayout();
  updateResultsGuideVisibility();
  resultLightboxItems = [];
  container.innerHTML = "";
  updateSelectedCount();
  if (!normalized.results.length) {
    resultLightboxItems = [];
    clearLightboxCacheAll();
    updateResultFaceCountExactControl([]);
    container.innerHTML = "<div class='muted'>没有结果</div>";
    updateActionButtons();
    return;
  }
  const sortMode = getResultSortMode();
  updateResultFaceCountExactControl(normalized.results);
  const sortedResults = sortResults(normalized.results, sortMode);
  if (!sortedResults.length) {
    resultLightboxItems = [];
    clearLightboxCacheAll();
    if (sortMode === "face_count_exact") {
      const exactCount = getResultFaceCountExactValue(normalized.results);
      container.innerHTML = `<div class='muted'>没有脸数为 ${exactCount} 的结果</div>`;
    } else {
      container.innerHTML = "<div class='muted'>没有结果</div>";
    }
    updateActionButtons();
    return;
  }
  const fragment = document.createDocumentFragment();
  sortedResults.forEach((item, idx) => {
    const card = document.createElement("div");
    card.className = "card";
    const photoId = item.photo_id;
    const thumbUrl = photoId ? `${apiBase}/photos/${photoId}/thumb?size=256` : "";
    const lightboxSize = getLightboxQualitySize();
    const lightboxUrl = photoId ? `${apiBase}/photos/${photoId}/thumb?size=${lightboxSize}` : thumbUrl;
    const fileUrl = photoId ? `${apiBase}/photos/${photoId}/file` : "";
    const fileName = shortPath(item.file_path || "");
    const exifText = item.exif_datetime || "未知";
    const filePathText = String(item.file_path || "");
    const scoreValue = Number(item.score);
    const scoreText = Number.isFinite(scoreValue) ? scoreValue.toFixed(4) : "0.0000";
    resultLightboxItems.push({
      photoId: Number(photoId || 0),
      thumbUrl,
      lightboxUrl,
      fileUrl,
      filePath: item.file_path || "",
      exifDatetime: item.exif_datetime || "",
    });
    const gpsLat = Number.isFinite(item.gps_lat) ? Number(item.gps_lat) : null;
    const gpsLon = Number.isFinite(item.gps_lon) ? Number(item.gps_lon) : null;
    const faceCountVal = Number(item.face_count);
    const faceCountText = Number.isFinite(faceCountVal) && faceCountVal >= 0 ? String(Math.trunc(faceCountVal)) : "0";
    const gpsPoint = gpsLat !== null && gpsLon !== null ? `${gpsLat.toFixed(6)}, ${gpsLon.toFixed(6)}` : "暂无";
    const distanceText = Number.isFinite(item.distance_km) ? `距离: ${Number(item.distance_km).toFixed(3)} km` : "";
    const referenceText = gpsLat !== null && gpsLon !== null
      ? `距参考点: ${haversineKm(gpsLat, gpsLon, REFERENCE_GPS.lat, REFERENCE_GPS.lon).toFixed(3)} km`
      : "";
    const distanceTags = [distanceText, referenceText].filter(Boolean).join(" ｜ ");
    const openBtn = photoId
      ? `<a class="btn btn-outline btn-sm" href="${fileUrl}" target="_blank" rel="noopener">原图</a>`
      : "";
    const renameBtn = photoId
      ? `<button class="btn btn-outline btn-sm rename-photo" data-photo-id="${photoId}" data-file-path="${encodeURIComponent(item.file_path || "")}">重命名</button>`
      : "";
    const downloadBtn = photoId
      ? `<button class="btn btn-outline btn-sm download-single-photo" data-photo-id="${photoId}" data-file-path="${encodeURIComponent(item.file_path || "")}">下载</button>`
      : "";
    const gpsBtn = photoId
      ? `<button class="btn btn-outline btn-sm set-gps-center" data-photo-id="${photoId}" data-file-path="${encodeURIComponent(item.file_path || "")}" data-gps-lat="${gpsLat ?? ""}" data-gps-lon="${gpsLon ?? ""}">GPS中心</button>`
      : "";
    const standardBtn = photoId
      ? `<button class="btn btn-outline btn-sm set-standard-photo" data-photo-id="${photoId}">标准照片</button>`
      : "";
    const isChecked = photoId && selectedBefore.has(Number(photoId));
    const selectBox = photoId
      ? `<label class="select-row"><input type="checkbox" class="select-photo" data-photo-id="${photoId}" ${isChecked ? "checked" : ""} onchange="toggleResultPhotoSelection(this)" /> 选择</label>`
      : "";
    const thumbBlock = thumbUrl
      ? `<div class="result-thumb-wrap"><img class="thumb result-thumb" data-lightbox-index="${idx}" src="${thumbUrl}" loading="lazy" /></div>`
      : "";

    card.innerHTML = `
      <div class="card-body">
        <div class="result-card-main${thumbBlock ? " has-thumb" : ""}">
          ${thumbBlock}
          <div class="result-card-info">
            <div class="result-meta-row">
              <div class="result-file-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
              <div class="thumb-meta">EXIF: ${escapeHtml(exifText)}</div>
            </div>
            <div class="result-stat-row">
              <span class="result-stat-pill">相似度 ${scoreText}</span>
              <span class="result-stat-pill result-stat-pill-soft">脸数 ${faceCountText}</span>
            </div>
            <div class="result-path" title="${escapeHtml(filePathText)}">${escapeHtml(filePathText)}</div>
            ${distanceTags ? `<div class="result-extra-row">${escapeHtml(distanceTags)}</div>` : ""}
            <div class="result-extra-row">GPS: ${escapeHtml(gpsPoint)}</div>
          </div>
        </div>
        <div class="actions result-actions">${openBtn}${renameBtn}${downloadBtn}${standardBtn}${gpsBtn}${selectBox}</div>
      </div>
    `;
    fragment.appendChild(card);
  });
  container.appendChild(fragment);
  container.querySelectorAll(".set-gps-center").forEach((btn) => {
    btn.addEventListener("click", () => {
      const photoId = parseInt(btn.dataset.photoId || "", 10);
      if (Number.isNaN(photoId)) return;
      if (btn.disabled) return;
      const filePath = decodeURIComponent(btn.dataset.filePath || "");
      const gpsLat = btn.dataset.gpsLat ? parseFloat(btn.dataset.gpsLat) : NaN;
      const gpsLon = btn.dataset.gpsLon ? parseFloat(btn.dataset.gpsLon) : NaN;
      setGpsCenter(photoId, filePath, gpsLat, gpsLon);
      setResultActionFlash("gps", photoId, "success", RESULT_ACTION_FLASH_MS);
      refreshResultActionButtons(container);
    });
  });
  container.querySelectorAll(".set-standard-photo").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const photoId = parseInt(btn.dataset.photoId || "", 10);
      if (Number.isNaN(photoId)) return;
      if (btn.disabled) return;
      const actionKey = makeResultActionKey("standard", photoId);
      if (resultActionPendingKeys.has(actionKey)) return;
      setResultActionPending("standard", photoId, true);
      refreshResultActionButtons(container);
      try {
        const ok = await setStandardPhoto(photoId);
        if (ok) {
          setResultActionFlash("standard", photoId, "success", RESULT_ACTION_FLASH_MS);
        } else {
          setResultActionFlash("standard", photoId, "error", RESULT_ACTION_ERROR_FLASH_MS);
        }
      } finally {
        setResultActionPending("standard", photoId, false);
        refreshResultActionButtons(container);
      }
    });
  });
  container.querySelectorAll(".rename-photo").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const photoId = parseInt(btn.dataset.photoId || "", 10);
      if (Number.isNaN(photoId)) return;
      if (btn.disabled) return;
      const filePath = decodeURIComponent(btn.dataset.filePath || "");
      await renameSinglePhoto(photoId, filePath);
    });
  });
  container.querySelectorAll(".download-single-photo").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const photoId = parseInt(btn.dataset.photoId || "", 10);
      if (Number.isNaN(photoId)) return;
      const filePath = decodeURIComponent(btn.dataset.filePath || "");
      btn.disabled = true;
      try {
        await downloadSinglePhoto(photoId, filePath);
      } finally {
        btn.disabled = false;
      }
    });
  });
  container.querySelectorAll(".result-thumb").forEach((img) => {
    img.addEventListener("click", (ev) => {
      if (getLightboxTriggerMode() !== "click") return;
      if (resultLightboxActive || Date.now() < resultLightboxClosingUntil) return;
      ev.preventDefault();
      ev.stopPropagation();
      const index = parseInt(img.dataset.lightboxIndex || "", 10);
      if (Number.isNaN(index)) return;
      openResultLightbox(index);
    });
    img.addEventListener("dblclick", (ev) => {
      if (getLightboxTriggerMode() !== "dblclick") return;
      if (resultLightboxActive || Date.now() < resultLightboxClosingUntil) return;
      ev.preventDefault();
      ev.stopPropagation();
      const index = parseInt(img.dataset.lightboxIndex || "", 10);
      if (Number.isNaN(index)) return;
      openResultLightbox(index);
    });
    img.addEventListener("touchend", (ev) => {
      if (getLightboxTriggerMode() !== "dblclick") return;
      if (resultLightboxActive || Date.now() < resultLightboxClosingUntil) return;
      const now = Date.now();
      const index = parseInt(img.dataset.lightboxIndex || "", 10);
      if (Number.isNaN(index)) return;
      const touch = ev.changedTouches && ev.changedTouches.length ? ev.changedTouches[0] : null;
      const currentX = touch ? touch.clientX : 0;
      const lastTs = Number(img.dataset.lastTapTs || "0");
      const lastX = Number(img.dataset.lastTapX || "0");
      if (now - lastTs <= 320 && Math.abs(currentX - lastX) <= 24) {
        ev.preventDefault();
        img.dataset.lastTapTs = "0";
        openResultLightbox(index);
        return;
      }
      img.dataset.lastTapTs = String(now);
      img.dataset.lastTapX = String(currentX);
    }, { passive: false });
  });
  syncLightboxImageCache();
  if (resultLightboxItems.length) {
    preloadLightboxUrl(resultLightboxItems[0].lightboxUrl, { priority: LIGHTBOX_PRELOAD_PRIORITY.current });
    preloadLightboxNeighbors(0, 1);
  }
  refreshResultActionButtons(container);
  updateSelectedCount();
  updateActionButtons();
}

async function fetchDownloadBlobWithProgress(url, onProgress) {
  const res = await fetch(url);
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(msg || res.statusText);
  }
  const total = parseInt(res.headers.get("content-length") || "0", 10);
  if (!res.body || !res.body.getReader) {
    const blob = await res.blob();
    if (onProgress) onProgress(blob.size, blob.size, true);
    return blob;
  }
  const reader = res.body.getReader();
  const chunks = [];
  let received = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.byteLength;
    if (onProgress) onProgress(received, total, false);
  }
  if (onProgress) onProgress(received, total, true);
  return new Blob(chunks, { type: res.headers.get("content-type") || "application/zip" });
}

function applyPhotoRenameToCurrentResults(photoId, newPath) {
  const targetId = Number(photoId || 0);
  if (!targetId || !currentResultsData || !Array.isArray(currentResultsData.results)) return;
  currentResultsData.results = currentResultsData.results.map((item) => {
    if (Number(item && item.photo_id) !== targetId) return item;
    const next = Object.assign({}, item);
    next.file_path = newPath;
    return next;
  });
  if (gpsCenter && Number(gpsCenter.photoId) === targetId) {
    gpsCenter.filePath = newPath;
    updateGpsCenterInfo();
  }
}

async function renameSinglePhoto(photoId, filePath) {
  const id = Number(photoId || 0);
  if (!Number.isFinite(id) || id <= 0) return;
  if (trashBusy || downloadBusy || searchBusy || gpsBusy || gpsElementBusy) {
    setText("searchStatus", "当前有任务进行中，请稍后重命名。");
    return;
  }
  if (isRenameBlockedByScan()) {
    setText("searchStatus", "扫描进行中，禁止重命名。");
    refreshResultActionButtons();
    return;
  }
  const actionKey = makeResultActionKey("rename", id);
  if (resultActionPendingKeys.has(actionKey)) return;
  const oldFileName = shortPath(filePath || "");
  const split = splitFileNameExt(oldFileName);
  const oldStem = String(split.stem || "").trim();
  const ext = String(split.ext || "");
  const input = window.prompt(`请输入新文件名（不含后缀）\n当前：${oldFileName}`, oldStem);
  if (input === null) return;
  const newStem = String(input || "").trim();
  if (!newStem) {
    setText("searchStatus", "重命名取消：新名称不能为空。");
    return;
  }
  if (newStem === oldStem) {
    setText("searchStatus", "名称未改变，无需重命名。");
    return;
  }
  setResultActionPending("rename", id, true);
  refreshResultActionButtons();
  try {
    const data = await apiFetch(`${apiBase}/photos/${id}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_stem: newStem }),
    });
    const newPath = String(data && data.new_path ? data.new_path : "");
    const newName = String(data && data.new_name ? data.new_name : `${newStem}${ext}`);
    if (newPath) {
      applyPhotoRenameToCurrentResults(id, newPath);
      renderResults(currentResultsData);
    } else {
      refreshResultActionButtons();
    }
    setResultActionFlash("rename", id, "success", RESULT_ACTION_FLASH_MS);
    setText("searchStatus", `重命名成功：${oldFileName} → ${newName}`);
  } catch (err) {
    setResultActionFlash("rename", id, "error", RESULT_ACTION_ERROR_FLASH_MS);
    setText("searchStatus", `重命名失败：${err.message}`);
  } finally {
    setResultActionPending("rename", id, false);
    refreshResultActionButtons();
  }
}

async function trashSelected() {
  if (trashBusy || downloadBusy || searchBusy || gpsBusy || gpsElementBusy) {
    setText("searchStatus", "当前有任务进行中，请稍后再执行移入回收箱。");
    return;
  }
  const ids = getSelectedPhotoIds();
  if (!ids.length) {
    setText("searchStatus", "未选择任何照片。");
    return;
  }
  const ok = window.confirm(
    `确认将选中的 ${ids.length} 张照片移入回收箱吗？\n\n目标目录：${PRE_DELETED_DIR}\n\n该操作会同步清理数据库中的对应记录。`
  );
  if (!ok) return;

  trashBusy = true;
  updateActionButtons();
  try {
    setText("searchStatus", `正在移入回收箱：${ids.length} 张...`);
    const data = await apiFetch(`${apiBase}/photos/trash`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_ids: ids }),
    });
    const moved = Number(data && data.processed ? data.processed : 0);
    const failed = Number(data && data.failed ? data.failed : 0);
    const deletedIds = new Set(
      Array.isArray(data && data.processed_ids) ? data.processed_ids.map((v) => Number(v)).filter((v) => Number.isFinite(v) && v > 0) : []
    );
    if (deletedIds.size > 0) {
      const prevResults = Array.isArray(currentResultsData.results) ? currentResultsData.results : [];
      const nextResults = prevResults.filter((item) => !deletedIds.has(Number(item && item.photo_id)));
      const nextTotal = Math.max(0, Number(currentResultsData.total || 0) - deletedIds.size);
      resetSearchSessionState();
      renderResults({
        stage: Number(currentResultsData.stage || 0),
        total: nextTotal,
        results: nextResults,
        debug: currentResultsData.debug || null,
      });
      await loadStandardPhotoPool(true);
    }
    let msg = `已移入回收箱 ${moved} 张`;
    if (failed > 0) {
      const details = Array.isArray(data && data.details) ? data.details : [];
      const failedSample = details
        .filter((item) => !item || item.ok !== true)
        .slice(0, 2)
        .map((item) => {
          const pid = Number(item && item.photo_id);
          const base = Number.isFinite(pid) && pid > 0 ? `ID ${pid}` : "未知ID";
          const reason = item && item.message ? String(item.message) : "失败";
          return `${base}：${reason}`;
        })
        .join("；");
      msg += `，失败 ${failed} 张`;
      if (failedSample) msg += `（${failedSample}）`;
    }
    msg += "。如需完整刷新分页，请重新点击“开始搜索”。";
    setText("searchStatus", msg);
  } catch (err) {
    setText("searchStatus", `移入回收箱失败：${err.message}`);
  } finally {
    trashBusy = false;
    updateActionButtons();
  }
}

async function downloadSelected() {
  if (downloadBusy) {
    setText("searchStatus", "已有下载任务进行中，请稍候。");
    return;
  }
  if (trashBusy) {
    setText("searchStatus", "正在执行移入回收箱，请稍候。");
    return;
  }
  const ids = getSelectedPhotoIds();
  if (!ids.length) {
    setText("searchStatus", "未选择任何照片。");
    return;
  }
  downloadBusy = true;
  updateActionButtons();
  try {
    setText("searchStatus", `已提交 ${ids.length} 张，正在后台打包...`);
    const prep = await apiFetch(`${apiBase}/photos/download_zip_prepare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_ids: ids }),
    });
    const taskId = prep.task_id;
    if (!taskId) throw new Error("未返回任务ID");

    let readyInfo = null;
    for (let i = 0; i < 900; i += 1) {
      const status = await apiFetch(`${apiBase}/photos/download_zip_status?task_id=${encodeURIComponent(taskId)}`);
      const state = String(status.status || "").toLowerCase();
      if (state === "ready") {
        readyInfo = status;
        break;
      }
      if (state === "error") {
        throw new Error(status.message || "后台打包失败");
      }
      const total = Number(status.total_files || 0);
      const processed = Number(status.processed_files || 0);
      const percent = Number.isFinite(Number(status.percent)) ? Number(status.percent).toFixed(1) : "0.0";
      setText("searchStatus", `后台打包中：${processed}/${total}${total ? `（${percent}%）` : ""}...`);
      await sleep(1000);
    }
    if (!readyInfo) throw new Error("打包超时，请重试");

    const zipName = readyInfo.zip_name || `photos_${Date.now()}.zip`;
    const packed = Number(readyInfo.packed_files || ids.length);
    const sizeHint = Number(readyInfo.size_bytes || 0);
    setText("searchStatus", `打包完成（${packed}张，${formatBytes(sizeHint)}），正在下载...`);

    const blob = await fetchDownloadBlobWithProgress(
      `${apiBase}/photos/download_zip_file?task_id=${encodeURIComponent(taskId)}`,
      (received, total, done) => {
        if (done) return;
        if (total > 0) {
          const pct = ((received / total) * 100).toFixed(1);
          setText("searchStatus", `下载中：${formatBytes(received)} / ${formatBytes(total)}（${pct}%）...`);
        } else {
          setText("searchStatus", `下载中：${formatBytes(received)}...`);
        }
      }
    );

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = zipName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);

    setText("searchStatus", `下载完成：${zipName}（${formatBytes(blob.size)}）。临时压缩包已自动清理。`);
  } catch (err) {
    setText("searchStatus", `下载失败：${err.message}`);
  } finally {
    downloadBusy = false;
    updateActionButtons();
  }
}

async function runSearch() {
  if (!ensureSearchWarmReady()) return;
  if (searchBusy || gpsBusy || gpsElementBusy) {
    setText("searchStatus", "已有查询任务进行中，请稍候。");
    return;
  }
  const elements = getSelectedElements();
  if (!elements.length) {
    setText("searchStatus", "请至少选择一个搜索要素。");
    updateActionButtons();
    return;
  }
  const wantsText = elements.includes("text");
  const wantsFace = elements.includes("face");
  const wantsFocus = elements.includes("focus");
  const hasNonText = elements.some((e) => e !== "text");
  const faceMode = getFaceMode();
  const facePrune = getFacePruneEnabled();
  const focusModes = wantsFocus ? getFocusModes() : [];
  const textQuery = getTextQuery();
  const textScope = getTextScope();
  const textMode = getTextMode();
  const files = getUploadedQueryFiles();
  const standardIds = getStandardPhotoIds();
  const faceMinMatch = buildFaceMinMatchParam(wantsFace, files);
  if (wantsText && !textQuery) {
    setText("searchStatus", "请输入文字关键词。" );
    updateActionButtons();
    return;
  }
  if (hasNonText && !files.length && !standardIds.length) {
    setText("searchStatus", "请先上传标准照片，或在结果中“设为标准照片”。" );
    updateActionButtons();
    return;
  }
  if (wantsFace) {
    const faceGuard = getFaceAndConstraintGuard(files);
    if (faceGuard.blocked) {
      setText("searchStatus", faceGuard.message);
      updateActionButtons();
      return;
    }
  }
  if (!faceMinMatch.ok) {
    setText("searchStatus", faceMinMatch.message || "人脸匹配参数无效。");
    updateActionButtons();
    return;
  }
  const stage = document.getElementById("stage").value || 3;
  const dateParams = getDateRangeParams();
  const elementParams = elements.map((e) => `elements=${encodeURIComponent(e)}`).join("&");
  const elementModeParam = `&element_mode=${encodeURIComponent(getElementMode())}`;
  const faceParam = wantsFace ? `&face_mode=${encodeURIComponent(faceMode)}` : "";
  const facePruneParam = wantsFace ? `&face_prune=${encodeURIComponent(facePrune ? "true" : "false")}` : "";
  const focusParam = wantsFocus ? `&${focusModes.map((mode) => `focus_modes=${encodeURIComponent(mode)}`).join("&")}` : "";
  const minMatchParam = wantsFace ? faceMinMatch.param : "";
  const textParam = wantsText
    ? `&text_query=${encodeURIComponent(textQuery)}&text_scope=${encodeURIComponent(textScope)}&text_mode=${encodeURIComponent(textMode)}`
    : "";
  const serverSortParam = buildServerSortQueryParam();
  const standardParams = standardIds.map((id) => `standard_photo_ids=${id}`).join("&");

  let form = null;
  if (files.length) {
    form = new FormData();
    files.forEach((file) => form.append("files", file));
  }

  searchBusy = true;
  startSearchElapsedTicker();
  updateActionButtons();
  try {
    const options = { method: "POST" };
    if (form) {
      options.body = form;
    }
    const data = await apiFetch(
      `${apiBase}/search/multi?stage=${stage}${dateParams}${elementParams ? `&${elementParams}` : ""}${standardParams ? `&${standardParams}` : ""}${elementModeParam}${faceParam}${facePruneParam}${focusParam}${minMatchParam}${textParam}${serverSortParam}`,
      options
    );
    renderResults(data);
    applySearchBatchStateFromResponse(data);
    prefetchSearchBatchAround();
    toggleSearchResultsPanel(true, { skipMobileScroll: true });
    if (isMobileViewport()) {
      window.setTimeout(scrollSearchResultsCardToTop, 40);
    }
    const debugText = formatSearchDebugText(data && data.debug);
    const elapsedSeconds = getSearchElapsedSeconds();
    stopSearchElapsedTicker();
    setText(
      "searchStatus",
      `完成，共 ${data.total} 条。当前第 ${searchSessionState.batch}/${searchSessionState.totalBatches} 批。总用时：${elapsedSeconds}秒。${debugText}`
    );
  } catch (err) {
    const elapsedSeconds = getSearchElapsedSeconds();
    stopSearchElapsedTicker();
    setText("searchStatus", `搜索失败：${err.message}。总用时：${elapsedSeconds}秒。`);
  } finally {
    stopSearchElapsedTicker();
    searchBusy = false;
    updateActionButtons();
  }
}

function normalizeScanType(scanType) {
  const value = String(scanType || "").toLowerCase();
  if (value === "full") return "full";
  if (value === "incremental") return "incremental";
  return "";
}

function isScanActiveStatus(status) {
  const value = String(status || "").toLowerCase();
  return value === "running" || value === "counting";
}

function isRenameBlockedByScan() {
  return !!(scanTriggerBusy || isScanActiveStatus(latestScanProgress && latestScanProgress.status));
}

function applyScanTriggerButtonState(btn, label, { enabled, locked }) {
  if (!btn) return;
  btn.textContent = label;
  btn.disabled = !enabled;
  btn.classList.toggle("btn-ready", enabled);
  btn.classList.toggle("btn-scan-locked", locked);
}

function updateScanTriggerButtons() {
  const fullBtn = document.getElementById("btnScanFull");
  const incBtn = document.getElementById("btnScanIncremental");
  const resumeBtn = document.getElementById("btnScanResume");
  const repairBtn = document.getElementById("btnRepairExifIphoneWch");
  const pickRepairDirBtn = document.getElementById("btnPickExifRepairDir");
  if (!fullBtn || !incBtn || !resumeBtn) return;

  const status = String(latestScanProgress && latestScanProgress.status ? latestScanProgress.status : "").toLowerCase();
  const scanType = normalizeScanType(latestScanProgress && latestScanProgress.scan_type);
  const running = scanTriggerBusy || isScanActiveStatus(status);

  if (!running) {
    activeScanTrigger = "";
    applyScanTriggerButtonState(fullBtn, "全扫描", { enabled: true, locked: false });
    applyScanTriggerButtonState(incBtn, "增量扫描", { enabled: true, locked: false });
    applyScanTriggerButtonState(resumeBtn, "断点扫描", { enabled: true, locked: false });
    if (repairBtn) {
      const canRepair = !!(exifRepairDirs.length && getSelectedExifRepairDir());
      applyScanTriggerButtonState(repairBtn, "时间修复", { enabled: canRepair, locked: !canRepair });
    }
    if (pickRepairDirBtn) pickRepairDirBtn.disabled = !exifRepairDirs.length;
    return;
  }

  let active = activeScanTrigger;
  if (!active) {
    active = scanType === "full" ? "full" : "incremental";
  }
  const fullLabel = active === "full" ? "全扫描（进行中）" : "全扫描（锁定）";
  const incLabel = active === "incremental" ? "增量扫描（进行中）" : "增量扫描（锁定）";
  const resumeLabel = active === "resume" ? "断点扫描（进行中）" : "断点扫描（锁定）";
  const repairLabel = active === "repair_exif" ? "时间修复（进行中）" : "时间修复（锁定）";
  applyScanTriggerButtonState(fullBtn, fullLabel, { enabled: false, locked: true });
  applyScanTriggerButtonState(incBtn, incLabel, { enabled: false, locked: true });
  applyScanTriggerButtonState(resumeBtn, resumeLabel, { enabled: false, locked: true });
  if (repairBtn) {
    applyScanTriggerButtonState(repairBtn, repairLabel, { enabled: false, locked: true });
  }
  if (pickRepairDirBtn) pickRepairDirBtn.disabled = true;
}


async function runGpsSearch() {
  if (!ensureSearchWarmReady()) return;
  if (searchBusy || gpsBusy || gpsElementBusy) {
    setText("searchStatus", "已有查询任务进行中，请稍候。");
    return;
  }
  if (!gpsCenter || !gpsCenter.photoId) {
    setText("searchStatus", "请先在结果卡片点击“设为GPS中心”。");
    updateActionButtons();
    return;
  }
  const radiusEl = document.getElementById("gpsRadius");
  const radiusValue = radiusEl ? parseFloat(radiusEl.value) : 5;
  if (!Number.isFinite(radiusValue) || radiusValue < 1 || radiusValue > 50) {
    setText("searchStatus", "GPS半径请输入 1-50 之间的数字。");
    updateActionButtons();
    return;
  }
  const stage = document.getElementById("stage").value || 3;
  const dateParams = getDateRangeParams();
  const elements = getSelectedElements();
  const wantsText = elements.includes("text");
  const textQuery = getTextQuery();
  const textScope = getTextScope();
  const textMode = getTextMode();
  if (wantsText && !textQuery) {
    setText("searchStatus", "已勾选文字要素，请先输入关键词。");
    updateActionButtons();
    return;
  }
  const textParam = (wantsText && textQuery)
    ? `&text_query=${encodeURIComponent(textQuery)}&text_scope=${encodeURIComponent(textScope)}&text_mode=${encodeURIComponent(textMode)}`
    : "";
  const serverSortParam = buildServerSortQueryParam();
  gpsBusy = true;
  updateActionButtons();
  setText("searchStatus", `正在进行GPS查询（${radiusValue}km）...`);
  try {
    const data = await apiFetch(
      `${apiBase}/search/gps?center_photo_id=${gpsCenter.photoId}&radius_km=${radiusValue}&stage=${stage}${dateParams}${textParam}${serverSortParam}`
    );
    renderResults(data);
    applySearchBatchStateFromResponse(data);
    prefetchSearchBatchAround();
    setText("searchStatus", `GPS查询完成，共 ${data.total} 条。当前第 ${searchSessionState.batch}/${searchSessionState.totalBatches} 批。`);
  } catch (err) {
    setText("searchStatus", `GPS查询失败：${err.message}`);
  } finally {
    gpsBusy = false;
    updateActionButtons();
  }
}

async function runGpsElementSearch() {
  if (!ensureSearchWarmReady()) return;
  if (searchBusy || gpsBusy || gpsElementBusy) {
    setText("searchStatus", "已有查询任务进行中，请稍候。");
    return;
  }
  if (!gpsCenter || !gpsCenter.photoId) {
    setText("searchStatus", "请先在结果卡片点击“设为GPS中心”。");
    updateActionButtons();
    return;
  }
  const radiusEl = document.getElementById("gpsRadius");
  const radiusValue = radiusEl ? parseFloat(radiusEl.value) : 5;
  if (!Number.isFinite(radiusValue) || radiusValue < 1 || radiusValue > 50) {
    setText("searchStatus", "GPS半径请输入 1-50 之间的数字。");
    updateActionButtons();
    return;
  }

  const elements = getSelectedElements();
  if (!elements.length) {
    setText("searchStatus", "请至少选择一个搜索要素。");
    updateActionButtons();
    return;
  }
  const wantsText = elements.includes("text");
  const wantsFace = elements.includes("face");
  const wantsFocus = elements.includes("focus");
  const hasNonText = elements.some((e) => e !== "text");
  const faceMode = getFaceMode();
  const facePrune = getFacePruneEnabled();
  const focusModes = wantsFocus ? getFocusModes() : [];
  const textQuery = getTextQuery();
  const textScope = getTextScope();
  const textMode = getTextMode();
  const files = getUploadedQueryFiles();
  const standardIds = getStandardPhotoIds();
  const faceMinMatch = buildFaceMinMatchParam(wantsFace, files);
  if (wantsText && !textQuery) {
    setText("searchStatus", "请输入文字关键词。");
    updateActionButtons();
    return;
  }
  if (hasNonText && !files.length && !standardIds.length) {
    setText("searchStatus", "请先上传标准照片，或在结果中“设为标准照片”。");
    updateActionButtons();
    return;
  }
  if (wantsFace) {
    const faceGuard = getFaceAndConstraintGuard(files);
    if (faceGuard.blocked) {
      setText("searchStatus", faceGuard.message);
      updateActionButtons();
      return;
    }
  }
  if (!faceMinMatch.ok) {
    setText("searchStatus", faceMinMatch.message || "人脸匹配参数无效。");
    updateActionButtons();
    return;
  }

  const stage = document.getElementById("stage").value || 3;
  const dateParams = getDateRangeParams();
  const elementParams = elements.map((e) => `elements=${encodeURIComponent(e)}`).join("&");
  const elementModeParam = `&element_mode=${encodeURIComponent(getElementMode())}`;
  const faceParam = wantsFace ? `&face_mode=${encodeURIComponent(faceMode)}` : "";
  const facePruneParam = wantsFace ? `&face_prune=${encodeURIComponent(facePrune ? "true" : "false")}` : "";
  const focusParam = wantsFocus ? `&${focusModes.map((mode) => `focus_modes=${encodeURIComponent(mode)}`).join("&")}` : "";
  const minMatchParam = wantsFace ? faceMinMatch.param : "";
  const textParam = wantsText
    ? `&text_query=${encodeURIComponent(textQuery)}&text_scope=${encodeURIComponent(textScope)}&text_mode=${encodeURIComponent(textMode)}`
    : "";
  const serverSortParam = buildServerSortQueryParam();
  const standardParams = standardIds.map((id) => `standard_photo_ids=${id}`).join("&");

  let form = null;
  if (files.length) {
    form = new FormData();
    files.forEach((file) => form.append("files", file));
  }

  gpsElementBusy = true;
  updateActionButtons();
  setText("searchStatus", `正在执行GPS叠加要素查询（${radiusValue}km）...`);
  try {
    const options = { method: "POST" };
    if (form) {
      options.body = form;
    }
    const data = await apiFetch(
      `${apiBase}/search/gps_multi?center_photo_id=${gpsCenter.photoId}&radius_km=${radiusValue}&stage=${stage}${dateParams}${elementParams ? `&${elementParams}` : ""}${standardParams ? `&${standardParams}` : ""}${elementModeParam}${faceParam}${facePruneParam}${focusParam}${minMatchParam}${textParam}${serverSortParam}`,
      options
    );
    renderResults(data);
    applySearchBatchStateFromResponse(data);
    prefetchSearchBatchAround();
    const debugText = formatSearchDebugText(data && data.debug);
    setText("searchStatus", `GPS叠加要素查询完成，共 ${data.total} 条（半径 ${radiusValue}km）。当前第 ${searchSessionState.batch}/${searchSessionState.totalBatches} 批。${debugText}`);
  } catch (err) {
    setText("searchStatus", `GPS叠加要素查询失败：${err.message}`);
  } finally {
    gpsElementBusy = false;
    updateActionButtons();
  }
}

async function loadStatus() {
  try {
    const data = await apiFetch(`${apiBase}/status`);
    setText("systemStatus", JSON.stringify(data, null, 2));
    applySearchWarmStatus(data);
  } catch (err) {
    setText("systemStatus", `状态获取失败：${err.message}`);
    applySearchWarmStatus({ search_ready: false, search_ready_message: `状态获取失败：${err.message}` });
  }
}

function renderIndexCompactState(state) {
  latestIndexCompactState = state && typeof state === "object" ? state : null;
  const statusEl = document.getElementById("indexCompactStatus");
  const detailWrap = document.getElementById("indexCompactDetailWrap");
  const detailEl = document.getElementById("indexCompactDetail");
  if (!statusEl) return;
  if (!latestIndexCompactState) {
    statusEl.textContent = "压实任务：未开始";
    if (detailWrap) detailWrap.hidden = true;
    if (detailEl) detailEl.textContent = "";
    updateIndexCompactButtons();
    return;
  }
  const status = String(latestIndexCompactState.status || "idle");
  const message = String(latestIndexCompactState.message || "");
  const target = String(latestIndexCompactState.target || "");
  const dryRun = latestIndexCompactState.dry_run ? "（体检）" : "";
  statusEl.textContent = `压实任务：${status}${target ? ` / ${target}` : ""}${dryRun} ${message ? `｜ ${message}` : ""}`;
  if (detailEl) {
    detailEl.textContent = JSON.stringify(latestIndexCompactState, null, 2);
  }
  if (detailWrap) {
    detailWrap.hidden = false;
  }
  updateIndexCompactButtons();
}

async function loadIndexCompactStatus(silent = true) {
  try {
    const data = await apiFetch(`${apiBase}/index/compact/status`);
    renderIndexCompactState(data);
    return data;
  } catch (err) {
    if (!silent) {
      setText("indexCompactStatus", `压实状态获取失败：${err.message}`);
    }
    updateIndexCompactButtons();
    return null;
  }
}

async function startIndexCompaction(target, dryRun) {
  if (indexCompactBusy) return;
  const scanActive = isScanActiveStatus(latestScanProgress && latestScanProgress.status);
  if (scanActive) {
    setText("indexCompactStatus", "扫描任务运行中，禁止执行索引压实。请先停止扫描。");
    return;
  }
  const kindText = target === "face" ? "人脸索引" : target === "vision" ? "视觉索引" : "人脸+视觉索引";
  if (dryRun) {
    const ok = window.confirm(`将执行“${kindText}体检（不改写索引）”。\n\n用途：评估压实规模与风险，不会替换索引文件。\n确认继续？`);
    if (!ok) return;
  } else {
    const ok = window.confirm(
      `将执行“${kindText}压实（会改写索引）”。\n\n关键提醒：\n1) 请确认已做备份；\n2) 扫描任务必须停止；\n3) 执行期间检索可能变慢。\n\n确认继续？`
    );
    if (!ok) return;
  }

  indexCompactBusy = true;
  updateIndexCompactButtons();
  try {
    const latest = await loadIndexCompactStatus(true);
    if (latest && latest.status === "running") {
      setText("indexCompactStatus", "已有压实任务运行中，请稍后。");
      return;
    }
    let confirmText = "";
    if (!dryRun) {
      const required = String((latest && latest.confirm_text_required) || "我已备份并确认压实");
      const typed = window.prompt(`为避免误操作，请输入确认短语：\n${required}`, "");
      if (typed === null) {
        setText("indexCompactStatus", "已取消压实。");
        return;
      }
      if (String(typed).trim() !== required) {
        setText("indexCompactStatus", "确认短语不正确，已取消压实。");
        return;
      }
      confirmText = required;
    }

    const data = await apiFetch(`${apiBase}/index/compact/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target,
        dry_run: !!dryRun,
        confirm_text: confirmText,
      }),
    });
    renderIndexCompactState(data);
    setText("indexCompactStatus", `压实任务已启动：${kindText}${dryRun ? "体检" : "压实"}。`);
  } catch (err) {
    setText("indexCompactStatus", `压实启动失败：${err.message}`);
  } finally {
    indexCompactBusy = false;
    updateIndexCompactButtons();
  }
}

async function loadVisionStatus() {
  try {
    const data = await apiFetch(`${apiBase}/vision/status`);
    const bar = document.getElementById("visionProgressBar");
    const text = document.getElementById("visionProgressText");
    if (bar) {
      const pct = Math.max(0, Math.min(100, data.percent || 0));
      bar.style.width = `${pct}%`;
      bar.textContent = `${pct}%`;
    }
    if (text) {
      text.textContent = `已完成 ${data.vision_photos}/${data.photos_total}（${data.percent}%）`;
    }
  } catch (err) {
    const text = document.getElementById("visionProgressText");
    if (text) text.textContent = `进度获取失败：${err.message}`;
  }
}

async function loadFaceStatus() {
  try {
    const data = await apiFetch(`${apiBase}/scan/progress`);
    latestScanProgress = data || null;
    const bar = document.getElementById("faceProgressBar");
    const text = document.getElementById("faceProgressText");
    const pct = Math.max(0, Math.min(100, data.percent || 0));
    if (bar) {
      if (!data.total_photos && (data.processed_photos || data.status === "counting")) {
        bar.classList.add("indeterminate");
        bar.style.width = "100%";
        bar.textContent = "";
      } else {
        bar.classList.remove("indeterminate");
        bar.style.width = `${pct}%`;
        bar.textContent = `${pct}%`;
      }
    }
    if (text) {
      if (!data.total_photos) {
        if (data.processed_photos) {
          const last = data.last_path ? `最后: ${shortPath(data.last_path)}` : "";
          text.textContent = `已处理 ${data.processed_photos}（总数统计中）${last ? "，" + last : ""}`;
        } else if (data.status === "counting") {
          text.textContent = "正在统计照片总数...";
        } else if (data.status) {
          text.textContent = `状态: ${data.status}`;
        } else {
          text.textContent = "暂无扫描任务";
        }
      } else {
        const status = data.status ? `状态: ${data.status}` : "";
        const last = data.last_path ? `最后: ${shortPath(data.last_path)}` : "";
        const extra = [status, last].filter(Boolean).join("，");
        text.textContent = `已处理 ${data.processed_photos}/${data.total_photos}（${pct}%）${extra ? "，" + extra : ""}`;
      }
    }
    updateScanTriggerButtons();
    updateIndexCompactButtons();
    refreshResultActionButtons();
  } catch (err) {
    const text = document.getElementById("faceProgressText");
    if (text) text.textContent = `进度获取失败：${err.message}`;
    updateScanTriggerButtons();
    updateIndexCompactButtons();
    refreshResultActionButtons();
  }
}

async function loadFavorites() {
  try {
    const items = await apiFetch(`${apiBase}/favorites`);
    const sel = document.getElementById("favoriteSelect");
    sel.innerHTML = "";
    for (const it of items) {
      const opt = document.createElement("option");
      opt.value = it.id;
      opt.textContent = `${it.id} - ${it.name}`;
      sel.appendChild(opt);
    }
  } catch (err) {
    setText("searchStatus", `收藏夹加载失败：${err.message}`);
  }
}

async function createFavorite() {
  const name = document.getElementById("favoriteName").value.trim();
  if (!name) {
    setText("searchStatus", "请输入收藏夹名称。" );
    return;
  }
  try {
    await apiFetch(`${apiBase}/favorites`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    await loadFavorites();
    setText("searchStatus", "收藏夹已创建。" );
  } catch (err) {
    setText("searchStatus", `创建失败：${err.message}`);
  }
}

async function searchFavorite() {
  const sel = document.getElementById("favoriteSelect");
  const id = sel.value;
  if (!id) {
    setText("searchStatus", "请先选择收藏夹。" );
    return;
  }
  try {
    const data = await apiFetch(`${apiBase}/search/favorite/${id}`);
    setText("searchStatus", `收藏夹就绪，embedding_id=${data.embedding_id}`);
  } catch (err) {
    setText("searchStatus", `搜索失败：${err.message}`);
  }
}

async function startScanByMode(mode) {
  const modeMap = {
    full: { path: `${apiBase}/scan?full=true`, label: "全扫描", fallbackType: "full" },
    incremental: { path: `${apiBase}/scan`, label: "增量扫描", fallbackType: "incremental" },
    resume: { path: `${apiBase}/scan?resume=true`, label: "断点扫描", fallbackType: normalizeScanType(latestScanProgress && latestScanProgress.scan_type) || "incremental" },
  };
  const confirmMap = {
    full: "将执行【全扫描】。\n用途：重新遍历全部照片并更新索引。\n提示：耗时最长，建议空闲时执行。\n\n确认开始吗？",
    incremental: "将执行【增量扫描】。\n用途：仅处理新增或变更的照片。\n提示：速度较快，日常推荐。\n\n确认开始吗？",
    resume: "将执行【断点扫描】。\n用途：从上次中断位置继续处理。\n提示：若没有可续任务，可能不会启动。\n\n确认开始吗？",
  };
  const cfg = modeMap[mode];
  if (!cfg) return;
  if (!window.confirm(confirmMap[mode] || `确认执行${cfg.label}吗？`)) {
    setText("scanStatus", `已取消${cfg.label}。`);
    return;
  }

  if (scanTriggerBusy || isScanActiveStatus(latestScanProgress && latestScanProgress.status)) {
    setText("scanStatus", "当前已有扫描任务在运行，请稍候。");
    updateScanTriggerButtons();
    return;
  }

  scanTriggerBusy = true;
  activeScanTrigger = mode;
  updateScanTriggerButtons();
  try {
    const data = await apiFetch(cfg.path, { method: "POST" });
    if (data && data.running) {
      latestScanProgress = Object.assign({}, latestScanProgress || {}, {
        status: "running",
        scan_type: cfg.fallbackType,
      });
      setText("scanStatus", `${cfg.label}已触发：${data.message || "任务已启动"}`);
    } else {
      activeScanTrigger = "";
      setText("scanStatus", `${cfg.label}未启动：${(data && data.message) || "返回状态异常"}`);
    }
  } catch (err) {
    activeScanTrigger = "";
    setText("scanStatus", `${cfg.label}失败：${err.message}`);
  } finally {
    scanTriggerBusy = false;
    updateScanTriggerButtons();
    await loadFaceStatus();
  }
}

async function startFullScan() {
  await startScanByMode("full");
}

async function startIncrementalScan() {
  await startScanByMode("incremental");
}

async function startResumeScan() {
  await startScanByMode("resume");
}

function getSelectedExifRepairDir() {
  return String(exifRepairTargetDir || "").trim();
}

function normalizeExifRepairDir(value) {
  return String(value || "").trim().replace(/\//g, "\\").replace(/[\\]+$/, "");
}

function isExifRepairDirAllowed(dirPath) {
  const target = normalizeExifRepairDir(dirPath).toLowerCase();
  if (!target) return false;
  return exifRepairDirs.some((rootRaw) => {
    const root = normalizeExifRepairDir(rootRaw).toLowerCase();
    return !!root && (target === root || target.startsWith(`${root}\\`));
  });
}

function updateExifRepairTargetDirLabel() {
  const labelEl = document.getElementById("exifRepairTargetDirLabel");
  if (!labelEl) return;
  labelEl.textContent = exifRepairTargetDir
    ? `时间修复目录：${exifRepairTargetDir}`
    : "时间修复目录：未选择";
}

async function loadExifRepairDirs() {
  const pickBtn = document.getElementById("btnPickExifRepairDir");
  try {
    const data = await apiFetch(`${apiBase}/scan/exif_repair_dirs`);
    const dirs = Array.isArray(data && data.dirs) ? data.dirs.map((v) => normalizeExifRepairDir(v)).filter(Boolean) : [];
    const defaultDir = normalizeExifRepairDir(data && data.default_dir ? data.default_dir : "");
    exifRepairDirs = dirs;
    if (!dirs.length) {
      exifRepairTargetDir = "";
      updateExifRepairTargetDirLabel();
      if (pickBtn) pickBtn.disabled = true;
      updateScanTriggerButtons();
      return;
    }
    if (!isExifRepairDirAllowed(exifRepairTargetDir)) {
      exifRepairTargetDir = isExifRepairDirAllowed(defaultDir) ? defaultDir : dirs[0];
      updateExifRepairTargetDirLabel();
    }
    if (pickBtn) pickBtn.disabled = false;
    updateScanTriggerButtons();
  } catch (err) {
    exifRepairDirs = [];
    exifRepairTargetDir = "";
    updateExifRepairTargetDirLabel();
    if (pickBtn) pickBtn.disabled = true;
    updateScanTriggerButtons();
    setText("scanStatus", `时间修复目录加载失败：${err.message}`);
  }
}

function getDirPickerElements() {
  return {
    modal: document.getElementById("dirPickerModal"),
    rootSelect: document.getElementById("dirPickerRootSelect"),
    pathEl: document.getElementById("dirPickerPath"),
    listEl: document.getElementById("dirPickerList"),
  };
}

function setDirPickerOpen(open) {
  const { modal } = getDirPickerElements();
  if (!modal) return;
  const visible = !!open;
  dirPickerState.open = visible;
  modal.hidden = !visible;
  document.body.classList.toggle("dir-picker-open", visible);
}

function ensureDirPickerEscBinding() {
  if (dirPickerEscBound) return;
  dirPickerEscBound = true;
  document.addEventListener("keydown", (ev) => {
    if (!dirPickerState.open) return;
    if (ev.key !== "Escape") return;
    ev.preventDefault();
    closeDirPickerModal(false);
  });
}

function getPathLeafName(path) {
  const normalized = normalizeExifRepairDir(path);
  if (!normalized) return "";
  const idx = normalized.lastIndexOf("\\");
  if (idx < 0) return normalized;
  return normalized.slice(idx + 1) || normalized;
}

function renderExifDirPicker(payload) {
  const { rootSelect, pathEl, listEl } = getDirPickerElements();
  const roots = Array.isArray(payload && payload.roots)
    ? payload.roots.map((v) => normalizeExifRepairDir(v)).filter(Boolean)
    : [];
  const currentPath = normalizeExifRepairDir(payload && payload.path ? payload.path : "");
  const parentPath = normalizeExifRepairDir(payload && payload.parent ? payload.parent : "");
  const subdirs = Array.isArray(payload && payload.subdirs)
    ? payload.subdirs
      .map((item) => ({
        name: String(item && item.name ? item.name : ""),
        path: normalizeExifRepairDir(item && item.path ? item.path : ""),
      }))
      .filter((item) => item.path)
    : [];

  dirPickerState.path = currentPath;
  dirPickerState.parent = parentPath;
  dirPickerState.roots = roots;
  dirPickerState.subdirs = subdirs;

  if (pathEl) {
    pathEl.textContent = currentPath ? `当前目录：${currentPath}` : "当前目录：未选择";
  }

  if (rootSelect) {
    const selectedRoot = roots.find((root) => {
      const lowRoot = root.toLowerCase();
      const lowPath = currentPath.toLowerCase();
      return lowPath === lowRoot || lowPath.startsWith(`${lowRoot}\\`);
    }) || roots[0] || "";

    rootSelect.innerHTML = "";
    roots.forEach((root) => {
      const opt = document.createElement("option");
      opt.value = root;
      opt.textContent = root;
      rootSelect.appendChild(opt);
    });
    rootSelect.value = selectedRoot;
  }

  const upBtn = document.getElementById("btnDirPickerUp");
  if (upBtn) upBtn.disabled = !parentPath;

  if (listEl) {
    listEl.innerHTML = "";
    if (!subdirs.length) {
      const empty = document.createElement("div");
      empty.className = "muted dir-picker-empty";
      empty.textContent = "（当前目录无子目录）";
      listEl.appendChild(empty);
    } else {
      const frag = document.createDocumentFragment();
      subdirs.forEach((item) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dir-picker-item";
        btn.title = item.path;
        const name = item.name || getPathLeafName(item.path);
        btn.innerHTML = `
          <span class="dir-picker-item-name">${escapeHtml(name)}</span>
          <span class="dir-picker-item-path">${escapeHtml(item.path)}</span>
        `;
        btn.addEventListener("click", () => {
          dirPickerEnterSubdir(item.path);
        });
        frag.appendChild(btn);
      });
      listEl.appendChild(frag);
    }
  }
}

async function loadExifDirPickerPath(path) {
  const normalized = normalizeExifRepairDir(path || "");
  const query = normalized ? `?path=${encodeURIComponent(normalized)}` : "";
  const data = await apiFetch(`${apiBase}/scan/exif_repair_browse${query}`);
  renderExifDirPicker(data || {});
}

function onDirPickerRootChange(rootPath) {
  const selected = normalizeExifRepairDir(rootPath || "");
  if (!selected) return;
  loadExifDirPickerPath(selected).catch((err) => {
    setText("scanStatus", `读取目录失败：${err.message}`);
  });
}

function dirPickerGoParent() {
  if (!dirPickerState.parent) return;
  loadExifDirPickerPath(dirPickerState.parent).catch((err) => {
    setText("scanStatus", `读取目录失败：${err.message}`);
  });
}

function dirPickerRefresh() {
  const target = dirPickerState.path || exifRepairTargetDir || exifRepairDirs[0] || "";
  if (!target) return;
  loadExifDirPickerPath(target).catch((err) => {
    setText("scanStatus", `读取目录失败：${err.message}`);
  });
}

function dirPickerEnterSubdir(path) {
  const target = normalizeExifRepairDir(path);
  if (!target) return;
  loadExifDirPickerPath(target).catch((err) => {
    setText("scanStatus", `读取目录失败：${err.message}`);
  });
}

function closeDirPickerModal(applySelection = false) {
  if (applySelection && dirPickerState.mode === DIR_PICKER_MODE_EXIF_REPAIR) {
    const picked = normalizeExifRepairDir(dirPickerState.path);
    if (picked && isExifRepairDirAllowed(picked)) {
      exifRepairTargetDir = picked;
      updateExifRepairTargetDirLabel();
      setText("scanStatus", `已选择时间修复目录：${picked}`);
      updateScanTriggerButtons();
    }
  }
  dirPickerState.mode = "";
  setDirPickerOpen(false);
}

function confirmDirPickerSelection() {
  closeDirPickerModal(true);
}

async function openExifRepairDirPicker() {
  try {
    if (!exifRepairDirs.length) {
      await loadExifRepairDirs();
    }
    if (!exifRepairDirs.length) {
      setText("scanStatus", "未配置可用目录，请先检查照片根目录设置。");
      return;
    }

    const startPath = isExifRepairDirAllowed(exifRepairTargetDir)
      ? exifRepairTargetDir
      : (exifRepairDirs[0] || "");
    if (!startPath) {
      setText("scanStatus", "没有可用目录。请先检查根目录配置。");
      return;
    }

    ensureDirPickerEscBinding();
    dirPickerState.mode = DIR_PICKER_MODE_EXIF_REPAIR;
    setDirPickerOpen(true);
    await loadExifDirPickerPath(startPath);
  } catch (err) {
    setText("scanStatus", `选择目录失败：${err.message}`);
    setDirPickerOpen(false);
  }
}

async function pickExifRepairDir() {
  await openExifRepairDirPicker();
}

async function repairExifIphoneWch() {
  const targetDir = getSelectedExifRepairDir();
  if (!targetDir) {
    setText("scanStatus", "请先选择时间修复目录。");
    return;
  }
  if (!isExifRepairDirAllowed(targetDir)) {
    setText("scanStatus", "当前目录不在允许范围，请重新点“选目录”。");
    updateScanTriggerButtons();
    return;
  }
  if (!window.confirm(`将执行【时间修复】\n目标目录：${targetDir}\n\n用途：仅重读该目录照片的EXIF时间并写回数据库，不重建人脸/向量。\n\n确认开始吗？`)) {
    setText("scanStatus", "已取消时间修复。");
    return;
  }
  if (scanTriggerBusy || isScanActiveStatus(latestScanProgress && latestScanProgress.status)) {
    setText("scanStatus", "当前已有扫描任务在运行，请稍候。");
    updateScanTriggerButtons();
    return;
  }
  scanTriggerBusy = true;
  activeScanTrigger = "repair_exif";
  updateScanTriggerButtons();
  try {
    setText("scanStatus", "正在启动时间修复任务，请稍候...");
    const data = await apiFetch(`${apiBase}/scan/exif_repair?target_dir=${encodeURIComponent(targetDir)}`, { method: "POST" });
    const taskId = String(data && data.task_id ? data.task_id : "").trim();
    if (!taskId) {
      throw new Error("时间修复任务启动失败：未返回task_id");
    }
    exifRepairTaskId = taskId;
    while (exifRepairTaskId === taskId) {
      const progress = await apiFetch(`${apiBase}/scan/exif_repair_status?task_id=${encodeURIComponent(taskId)}`);
      const status = String(progress && progress.status ? progress.status : "");
      const runningTotal = Number(progress && progress.total ? progress.total : 0);
      const runningProcessed = Number(progress && progress.processed ? progress.processed : 0);
      const runningUpdated = Number(progress && progress.updated ? progress.updated : 0);
      const runningUnchanged = Number(progress && progress.unchanged ? progress.unchanged : 0);
      const runningFallback = Number(progress && progress.fallback_mtime ? progress.fallback_mtime : 0);
      const runningFailed = Number(progress && progress.failed ? progress.failed : 0);
      const runningMissing = Number(progress && progress.missing ? progress.missing : 0);
      const runningPath = String(progress && progress.current_path ? progress.current_path : "");

      if (status === "running" || status === "idle") {
        const totalText = runningTotal > 0 ? String(runningTotal) : "?";
        const pathText = runningPath ? ` ｜ 当前：${shortPath(runningPath)}` : "";
        setText(
          "scanStatus",
          `时间修复中（${targetDir}）：${runningProcessed}/${totalText} 文件，已更新 ${runningUpdated}，未变化 ${runningUnchanged}，回退mtime ${runningFallback}，缺失 ${runningMissing}，失败 ${runningFailed}${pathText}`
        );
        await sleep(700);
        continue;
      }

      if (status !== "completed") {
        const message = String(progress && progress.message ? progress.message : "任务状态异常");
        throw new Error(message);
      }

      const total = Number(progress && progress.total ? progress.total : 0);
      const updated = Number(progress && progress.updated ? progress.updated : 0);
      const unchanged = Number(progress && progress.unchanged ? progress.unchanged : 0);
      const fallback = Number(progress && progress.fallback_mtime ? progress.fallback_mtime : 0);
      const failed = Number(progress && progress.failed ? progress.failed : 0);
      const missing = Number(progress && progress.missing ? progress.missing : 0);
      const doneDir = String(progress && progress.target_dir ? progress.target_dir : targetDir);
      setText(
        "scanStatus",
        `时间修复完成（${doneDir}）：总计 ${total}，已更新 ${updated}，未变化 ${unchanged}，回退mtime ${fallback}，缺失 ${missing}，失败 ${failed}。`
      );
      break;
    }
    if (exifRepairTaskId !== taskId) {
      throw new Error("时间修复进度轮询已中断。");
    }
  } catch (err) {
    setText("scanStatus", `时间修复失败：${err.message}`);
  } finally {
    exifRepairTaskId = "";
    scanTriggerBusy = false;
    activeScanTrigger = "";
    updateScanTriggerButtons();
    await loadFaceStatus();
  }
}

async function startScan() {
  await startIncrementalScan();
}

async function pauseScan() {
  try {
    const data = await apiFetch(`${apiBase}/scan/pause`, { method: "POST" });
    setText("scanStatus", data && data.paused ? "扫描已暂停。" : JSON.stringify(data));
  } catch (err) {
    setText("scanStatus", `暂停失败：${err.message}`);
  } finally {
    await loadFaceStatus();
  }
}

async function stopScan() {
  try {
    const data = await apiFetch(`${apiBase}/scan/stop`, { method: "POST" });
    setText("scanStatus", data && data.stopped ? "已请求停止扫描。" : JSON.stringify(data));
  } catch (err) {
    setText("scanStatus", `停止失败：${err.message}`);
  } finally {
    await loadFaceStatus();
  }
}

async function resumeScan() {
  try {
    const data = await apiFetch(`${apiBase}/scan/resume`, { method: "POST" });
    setText("scanStatus", data && data.paused === false ? "扫描已继续。" : JSON.stringify(data));
  } catch (err) {
    setText("scanStatus", `继续失败：${err.message}`);
  } finally {
    await loadFaceStatus();
  }
}

async function resumeBreakScan() {
  await startResumeScan();
}

loadStatus();
setInterval(loadStatus, 3000);
loadAuthStatus();
loadFavorites();
initMainTitleToday();
refreshMobileNavbarOffset();
syncResponsiveViewportMode();
bindMobileVisualViewportInsetsSync();
scheduleMobileVisualViewportInsetsSync();
window.setTimeout(refreshMobileNavbarOffset, 180);
window.setTimeout(syncResponsiveViewportMode, 180);
window.setTimeout(scheduleMobileVisualViewportInsetsSync, 220);
initDownloadDir();
initQueryPreview();
initMobileUiFontSizeControls();
bindActionStateWatchers();
ensureElementModeState("and");
ensureFaceModeState("or");
ensureTextModeState("and");
syncSceneSearchCardVisibility();
syncFocusSearchCardVisibility();
syncFaceSearchCardVisibility();
syncTextSearchCardVisibility();
initDateRangeDefaults();
updateGpsCenterInfo();
updateSortModeTip();
syncMobileSortBarPlacement();
syncSearchResultsHeaderRowVisibility();
syncMobileSearchResultsQuickButton();
syncTopSearchBatchRowVisibility();
initPcSidebarToggle();
window.addEventListener("resize", () => {
  if (mobileSortBarResizeTimer) {
    window.clearTimeout(mobileSortBarResizeTimer);
  }
  mobileSortBarResizeTimer = window.setTimeout(() => {
    mobileSortBarResizeTimer = 0;
    syncResponsiveViewportMode();
    refreshMobileNavbarOffset();
    scheduleMobileVisualViewportInsetsSync();
    syncMobileSortBarPlacement();
    syncSearchResultsHeaderRowVisibility();
    syncMobileSearchResultsQuickButton();
    syncTopSearchBatchRowVisibility();
    syncMobileFilterQuickButtons();
    syncMobileSystemSettingsQuickButton();
    refreshPcSidebarLayout();
  }, 80);
}, { passive: true });
window.addEventListener("orientationchange", () => {
  window.setTimeout(() => {
    syncResponsiveViewportMode();
    refreshMobileNavbarOffset();
    scheduleMobileVisualViewportInsetsSync();
    syncMobileSortBarPlacement();
    syncSearchResultsHeaderRowVisibility();
    syncMobileSearchResultsQuickButton();
    syncTopSearchBatchRowVisibility();
    syncMobileFilterQuickButtons();
    syncMobileSystemSettingsQuickButton();
    refreshPcSidebarLayout();
  }, 120);
}, { passive: true });
initSystemSettingsToggle();
initUsageGuideToggle();
initSearchResultsToggle();
initSystemStatusToggle();
initDateFiltersToggle();
initGpsFiltersToggle();
initPanelAutoCollapseSettings();
initPanelAutoCollapseIdleWatcher();
initElementHeaderFit();
initElementGridFit();
initLightboxTriggerMode();
initLightboxQuality();
initBackToTopButton();
updateResultsGuideVisibility();
loadExifRepairDirs().finally(updateScanTriggerButtons);
loadStandardPhotoPool(true);
updateActionButtons();
updateScanTriggerButtons();
loadVisionStatus();
setInterval(loadVisionStatus, 5000);
loadFaceStatus();
setInterval(loadFaceStatus, 5000);
loadIndexCompactStatus(true);
setInterval(() => { loadIndexCompactStatus(true); }, 3000);







function toggleResultPhotoSelection(box) { const id=Number(box.dataset.photoId); if(box.checked)globalPhotoSelection.add(id); else globalPhotoSelection.delete(id); updateSelectedCount(); }
