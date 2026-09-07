const header = document.querySelector("[data-header]");
const menuButton = document.querySelector("[data-menu-toggle]");
const mobileMenu = document.querySelector("[data-mobile-menu]");

const setHeaderState = () => {
  header?.classList.toggle("scrolled", window.scrollY > 24);
};

const closeMenu = () => {
  if (!menuButton || !mobileMenu) return;
  menuButton.setAttribute("aria-expanded", "false");
  mobileMenu.classList.remove("open");
  document.body.classList.remove("menu-open");
};

menuButton?.addEventListener("click", () => {
  const shouldOpen = menuButton.getAttribute("aria-expanded") !== "true";
  menuButton.setAttribute("aria-expanded", String(shouldOpen));
  mobileMenu?.classList.toggle("open", shouldOpen);
  document.body.classList.toggle("menu-open", shouldOpen);
});

mobileMenu?.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
window.addEventListener("resize", () => {
  if (window.innerWidth > 760) closeMenu();
});
window.addEventListener("scroll", setHeaderState, { passive: true });
setHeaderState();

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const revealElements = document.querySelectorAll(".reveal");

if (reduceMotion || !("IntersectionObserver" in window)) {
  revealElements.forEach((element) => element.classList.add("in-view"));
} else {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in-view");
      observer.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px -8%", threshold: 0.08 });

  revealElements.forEach((element) => observer.observe(element));
}

document.querySelectorAll("[data-year]").forEach((element) => {
  element.textContent = new Date().getFullYear();
});

const productRail = document.querySelector("[data-product-rail]");
const catalogFilters = document.querySelector("[data-catalog-filters]");
const filterSearch = document.querySelector("[data-filter-search]");
const filterCollection = document.querySelector("[data-filter-collection]");
const filterCategory = document.querySelector("[data-filter-category]");
const filterSize = document.querySelector("[data-filter-size]");
const filterCount = document.querySelector("[data-filter-count]");
const collectionRail = document.querySelector("[data-collection-rail]");
const collectionsPrev = document.querySelector("[data-collections-prev]");
const collectionsNext = document.querySelector("[data-collections-next]");
const productDialog = document.querySelector("[data-product-dialog]");
const productDetail = document.querySelector("[data-product-detail]");
const cartDrawer = document.querySelector("[data-cart-drawer]");
const cartBackdrop = document.querySelector(".cart-backdrop");
const cartItems = document.querySelector("[data-cart-items]");
const cartEmpty = document.querySelector("[data-cart-empty]");
const cartSummary = document.querySelector("[data-cart-summary]");
const cartSubtotal = document.querySelector("[data-cart-subtotal]");
const cartCountElements = document.querySelectorAll("[data-cart-count]");
const checkoutOpenButton = document.querySelector("[data-checkout-open]");
const checkoutButtonLabel = document.querySelector("[data-checkout-button-label]");
const checkoutNote = document.querySelector("[data-checkout-note]");
const checkoutDialog = document.querySelector("[data-checkout-dialog]");
const checkoutForm = document.querySelector("[data-checkout-form]");
const checkoutTotal = document.querySelector("[data-checkout-total]");
const checkoutError = document.querySelector("[data-checkout-error]");
const checkoutSuccess = document.querySelector("[data-checkout-success]");
const invoiceToggle = document.querySelector("[data-invoice-toggle]");
const invoiceFields = document.querySelector("[data-invoice-fields]");
const CART_STORAGE_KEY = "relax-cart-v1";

const categoryLabels = { SOCKS: "Skarpety", FOOTIES: "Stopki", TIGHTS: "Rajstopy", OTHER: "Inne" };
const priceFormatter = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });
const DEFAULT_LINE_LIMIT = 20;

let catalog = [];
let lastFocusedElement = null;
let productDialogTrigger = null;
let checkoutDialogTrigger = null;
let checkoutConfig = { enabled: false, mode: "loading" };
let checkoutToken = null;
let cart = loadCart();

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[character]);
}

function loadCart() {
  try {
    const stored = JSON.parse(localStorage.getItem(CART_STORAGE_KEY));
    return Array.isArray(stored) ? stored.filter((item) => item?.variantId && item.quantity > 0) : [];
  } catch {
    return [];
  }
}

function saveCart() {
  try {
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
  } catch {
    // Koszyk pozostaje aktywny w bieżącej karcie, nawet jeśli zapis jest zablokowany.
  }
}

function newCheckoutToken() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}

function csrfToken() {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="));
  return cookie ? decodeURIComponent(cookie.slice("csrftoken=".length)) : "";
}

function productImage(product) {
  const primary = product.images?.find((image) => image.primary) || product.images?.[0];
  return primary?.url || null;
}

function photoPlaceholder() {
  return '<span class="product-photo-placeholder"><strong>Relax</strong><small>Zdjęcie produktu<br>wkrótce</small></span>';
}

function variantLabel(variant) {
  return [variant.size, variant.color, variant.pattern].filter(Boolean).join(" · ");
}

function renderVariantOptions(variants) {
  let selectedAvailableVariant = false;
  return variants.map((variant) => {
    const unavailable = !variant.in_stock || variant.gross_price === null;
    const selected = !unavailable && !selectedAvailableVariant;
    if (selected) selectedAvailableVariant = true;
    const price = variant.gross_price === null ? "bez ceny" : priceFormatter.format(Number(variant.gross_price));
    return `<option value="${escapeHtml(variant.id)}" ${unavailable ? "disabled" : ""} ${selected ? "selected" : ""}>${escapeHtml(variantLabel(variant))} — ${escapeHtml(price)}${unavailable ? " · brak" : ""}</option>`;
  }).join("");
}

function renderCatalog(products, emptyText = "Nie ma jeszcze opublikowanych produktów.") {
  if (!productRail) return;
  productRail.setAttribute("aria-busy", "false");
  if (!products.length) {
    productRail.innerHTML = `<div class="catalog-error"><p>${escapeHtml(emptyText)}</p></div>`;
    return;
  }

  productRail.innerHTML = products.map((product, index) => {
    const variants = product.variants || [];
    const hasProductPhoto = Boolean(product.images?.length);
    const availableVariants = variants.filter((variant) => variant.in_stock && variant.gross_price !== null);
    const prices = availableVariants.map((variant) => Number(variant.gross_price));
    const minimumPrice = prices.length ? Math.min(...prices) : null;
    const sourceLabel = product.source === "RELAX" ? "Relax" : "W naszej ofercie";
    const productType = categoryLabels[product.category] || "Produkt";
    const optionMarkup = renderVariantOptions(variants);
    const imageUrl = productImage(product);

    return `
      <article class="product-card catalog-card in-view${hasProductPhoto ? " has-product-photo" : " is-placeholder"}" data-product-id="${escapeHtml(product.id)}">
        <button class="product-image" type="button" data-product-open aria-label="Zobacz szczegóły: ${escapeHtml(product.name)}">
          <span class="product-badge">${escapeHtml(sourceLabel)}</span>
          ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(product.name)}" width="1200" height="1600" loading="lazy">` : photoPlaceholder()}
          <span class="product-view">Zobacz <span aria-hidden="true">↗</span></span>
        </button>
        <div class="product-info">
          <div><h3>${escapeHtml(product.name)}</h3><p>${escapeHtml(productType)} · ${escapeHtml(product.materials || "różne materiały")}</p></div>
          <span class="product-number">${String(index + 1).padStart(2, "0")}</span>
        </div>
        <div class="product-stats" aria-label="Informacje o produkcie">
          <div class="product-stat"><span>Cena od</span><strong>${minimumPrice === null ? "—" : escapeHtml(priceFormatter.format(minimumPrice))}</strong></div>
          <div class="product-stat"><span>Rozmiary</span><strong>${variants.length}</strong></div>
          <div class="product-stat"><span>Pochodzenie</span><strong>${product.source === "RELAX" ? "Polska" : "Wybrane"}</strong></div>
        </div>
        <div class="product-buy">
          <label class="sr-only" for="variant-${escapeHtml(product.id)}">Wybierz wariant produktu ${escapeHtml(product.name)}</label>
          <select class="variant-picker" id="variant-${escapeHtml(product.id)}" data-variant-select ${availableVariants.length ? "" : "disabled"}>
            ${optionMarkup || '<option value="">Brak wariantów</option>'}
          </select>
          <button class="add-to-cart" type="button" data-add-to-cart ${availableVariants.length ? "" : "disabled"}>
            <span>${availableVariants.length ? "Dodaj do koszyka" : "Obecnie niedostępne"}</span><span aria-hidden="true">＋</span>
          </button>
        </div>
      </article>`;
  }).join("");
}

function normalizeSearch(value) {
  return String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pl");
}

function matchesCollection(product, collection) {
  if (!collection) return true;
  const tags = (product.tags || []).map(normalizeSearch);
  const name = normalizeSearch(product.name);
  const materials = normalizeSearch(product.materials);
  if (collection === "colorful") return tags.includes("kolorowe");
  if (collection === "footies") return product.category === "FOOTIES";
  if (collection === "children") return tags.some((tag) => tag.includes("dzieci")) || name.includes("dzieci");
  if (collection === "bamboo") return tags.some((tag) => tag.includes("bambus")) || materials.includes("bambus");
  if (collection === "tights") return product.category === "TIGHTS";
  if (collection === "relax") return product.source === "RELAX";
  return true;
}

function populateFilters() {
  if (filterCategory) {
    const categories = [...new Set(catalog.map((product) => product.category))]
      .sort((a, b) => (categoryLabels[a] || a).localeCompare(categoryLabels[b] || b, "pl"));
    filterCategory.innerHTML = '<option value="">Wszystkie</option>' + categories
      .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(categoryLabels[category] || category)}</option>`)
      .join("");
  }
  if (filterSize) {
    const sizes = [...new Set(catalog.flatMap((product) => product.variants.map((variant) => variant.size)).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "pl", { numeric: true }));
    filterSize.innerHTML = '<option value="">Wszystkie</option>' + sizes
      .map((size) => `<option value="${escapeHtml(size)}">${escapeHtml(size)}</option>`)
      .join("");
  }
}

function applyFilters() {
  const query = normalizeSearch(filterSearch?.value);
  const collection = filterCollection?.value || "";
  const category = filterCategory?.value || "";
  const size = filterSize?.value || "";
  const filtered = catalog.filter((product) => {
    const haystack = normalizeSearch([
      product.name,
      product.description,
      product.materials,
      ...(product.tags || []),
      ...(product.variants || []).flatMap((variant) => [variant.color, variant.pattern]),
    ].join(" "));
    return (!query || haystack.includes(query))
      && matchesCollection(product, collection)
      && (!category || product.category === category)
      && (!size || product.variants.some((variant) => variant.size === size));
  });
  renderCatalog(filtered, "Nie znaleźliśmy produktów pasujących do tych filtrów.");
  if (filterCount) {
    const suffix = filtered.length === 1 ? "produkt" : (filtered.length >= 2 && filtered.length <= 4 ? "produkty" : "produktów");
    filterCount.textContent = `${filtered.length} ${suffix}`;
  }
  collectionRail?.querySelectorAll("[data-collection]").forEach((card) => {
    if (card.dataset.collection === collection && collection) card.setAttribute("aria-current", "true");
    else card.removeAttribute("aria-current");
  });
}

function updateCollectionControls() {
  if (!collectionRail) return;
  const maxScroll = Math.max(0, collectionRail.scrollWidth - collectionRail.clientWidth);
  if (collectionsPrev) collectionsPrev.disabled = collectionRail.scrollLeft <= 2;
  if (collectionsNext) collectionsNext.disabled = collectionRail.scrollLeft >= maxScroll - 2;
}

function scrollCollections(direction) {
  if (!collectionRail) return;
  const card = collectionRail.querySelector(".collection-card");
  const distance = card ? card.getBoundingClientRect().width + 16 : collectionRail.clientWidth * 0.8;
  collectionRail.scrollBy({ left: direction * distance, behavior: reduceMotion ? "auto" : "smooth" });
}

function chooseCollection(key) {
  if (!filterCollection || !catalogFilters) return;
  catalogFilters.reset();
  filterCollection.value = key;
  applyFilters();
  catalogFilters.classList.remove("filter-arrival");
  void catalogFilters.offsetWidth;
  catalogFilters.classList.add("filter-arrival");
  document.querySelector("#produkty")?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  history.pushState(null, "", "#produkty");
}

function updateDetailVariant() {
  if (!productDetail) return;
  const product = catalog.find((item) => item.id === productDetail.dataset.productId);
  const variant = product?.variants.find((item) => item.id === productDetail.querySelector("[data-variant-select]")?.value);
  const price = productDetail.querySelector("[data-detail-price]");
  const stock = productDetail.querySelector("[data-detail-low-stock]");
  const addButton = productDetail.querySelector("[data-add-to-cart]");
  const available = Boolean(variant?.in_stock && variant.gross_price !== null);

  if (price) price.textContent = available ? priceFormatter.format(Number(variant.gross_price)) : "Niedostępny";
  if (stock) {
    stock.hidden = !(available && variant.low_stock && variant.low_stock_quantity !== null);
    stock.textContent = stock.hidden ? "" : `Ostatnie ${variant.low_stock_quantity} szt.`;
  }
  if (addButton) {
    addButton.disabled = !available;
    addButton.querySelector("span").textContent = available ? "Dodaj do koszyka" : "Obecnie niedostępne";
  }
}

function productHash(product) {
  return `#produkt/${encodeURIComponent(product.slug || product.key)}`;
}

function productFromHash() {
  if (!window.location.hash.startsWith("#produkt/")) return null;
  let slug = "";
  try {
    slug = decodeURIComponent(window.location.hash.slice(9));
  } catch {
    return null;
  }
  return catalog.find((product) => (product.slug || product.key) === slug) || null;
}

function renderProductDetail(product) {
  if (!productDetail) return;
  const variants = product.variants || [];
  const availableVariants = variants.filter((variant) => variant.in_stock && variant.gross_price !== null);
  const selectedVariant = availableVariants[0] || variants[0];
  const realImages = product.images || [];
  const galleryImages = realImages.map((image) => image.url);
  const tags = (product.tags || []).map((tag) => `<li>${escapeHtml(tag)}</li>`).join("");
  const sourceLabel = product.source === "RELAX" ? "Wyprodukowano przez Relax" : "Starannie wybrane do naszej oferty";
  const hasProductPhoto = Boolean(realImages.length);

  productDetail.dataset.productId = product.id;
  productDetail.innerHTML = `
    <div class="product-detail-media${hasProductPhoto ? " has-product-photo" : " is-placeholder"}">
      <div class="product-detail-main-image">
        <span class="product-badge">${escapeHtml(product.source === "RELAX" ? "Relax" : "W naszej ofercie")}</span>
        ${galleryImages.length ? `<img src="${escapeHtml(galleryImages[0])}" alt="${escapeHtml(product.name)}" width="1200" height="1600" data-detail-main-image>` : photoPlaceholder()}
      </div>
      ${galleryImages.length > 1 ? `<div class="product-thumbnails" aria-label="Zdjęcia produktu">${galleryImages.map((url, index) => `
        <button type="button" data-detail-image="${escapeHtml(url)}" aria-label="Pokaż zdjęcie ${index + 1}" ${index === 0 ? 'aria-current="true"' : ""}>
          <img src="${escapeHtml(url)}" alt="" width="100" height="125">
        </button>`).join("")}</div>` : ""}
    </div>
    <div class="product-detail-copy">
      <p class="product-detail-kicker">${escapeHtml(categoryLabels[product.category] || "Produkt")} · ${escapeHtml(sourceLabel)}</p>
      <h2 id="product-dialog-title">${escapeHtml(product.name)}</h2>
      <p class="product-detail-description">${escapeHtml(product.description || "Szczegóły produktu uzupełnimy wkrótce.")}</p>
      ${product.materials ? `<dl class="product-detail-facts"><div><dt>Skład</dt><dd>${escapeHtml(product.materials)}</dd></div></dl>` : ""}
      ${tags ? `<ul class="product-tags" aria-label="Cechy produktu">${tags}</ul>` : ""}
      <div class="product-detail-buy">
        <label for="detail-variant">Wybierz rozmiar i wariant</label>
        <select class="variant-picker" id="detail-variant" data-variant-select ${variants.length ? "" : "disabled"}>
          ${renderVariantOptions(variants) || '<option value="">Brak wariantów</option>'}
        </select>
        <div class="product-detail-price-row">
          <strong data-detail-price>${selectedVariant?.gross_price !== null && selectedVariant?.gross_price !== undefined ? escapeHtml(priceFormatter.format(Number(selectedVariant.gross_price))) : "Niedostępny"}</strong>
          <span class="low-stock" data-detail-low-stock hidden></span>
        </div>
        <button class="add-to-cart" type="button" data-add-to-cart ${availableVariants.length ? "" : "disabled"}>
          <span>${availableVariants.length ? "Dodaj do koszyka" : "Obecnie niedostępne"}</span><span aria-hidden="true">＋</span>
        </button>
      </div>
      <button class="copy-product-link" type="button" data-product-copy>Kopiuj link do produktu</button>
    </div>`;
  updateDetailVariant();
}

function openProduct(product, updateHash = true, trigger = null) {
  if (!productDialog || !productDetail) return;
  productDialogTrigger = trigger || document.activeElement;
  closeCart();
  renderProductDetail(product);
  if (!productDialog.open) productDialog.showModal();
  document.body.classList.add("product-open");
  document.title = `${product.name} — Relax`;
  if (updateHash && window.location.hash !== productHash(product)) history.pushState(null, "", productHash(product));
  productDialog.querySelector("[data-product-close]")?.focus();
}

function closeProduct(updateHash = true) {
  if (!productDialog?.open) return;
  productDialog.close();
  document.body.classList.remove("product-open");
  document.title = "Polskie skarpety od 1992 roku — Relax";
  if (updateHash && window.location.hash.startsWith("#produkt/")) history.replaceState(null, "", "#produkty");
  if (productDialogTrigger instanceof HTMLElement) productDialogTrigger.focus();
}

function syncProductRoute() {
  const product = productFromHash();
  if (product) openProduct(product, false);
  else if (productDialog?.open) closeProduct(false);
}

function syncCartWithCatalog() {
  const variants = new Map();
  catalog.forEach((product) => product.variants.forEach((variant) => variants.set(variant.id, { product, variant })));
  cart = cart.flatMap((item) => {
    const current = variants.get(item.variantId);
    if (!current || !current.variant.in_stock || current.variant.gross_price === null) return [];
    const purchaseLimit = current.variant.low_stock_quantity ?? DEFAULT_LINE_LIMIT;
    return [{
      ...item,
      productName: current.product.name,
      variantLabel: variantLabel(current.variant),
      unitPrice: Number(current.variant.gross_price),
      max: purchaseLimit,
      quantity: Math.min(item.quantity, purchaseLimit),
      image: productImage(current.product),
    }];
  });
  saveCart();
  renderCart();
}

function addSelectedVariant(card) {
  const product = catalog.find((item) => item.id === card.dataset.productId);
  const variantId = card.querySelector("[data-variant-select]")?.value;
  const variant = product?.variants.find((item) => item.id === variantId);
  if (!product || !variant || !variant.in_stock || variant.gross_price === null) return;

  const purchaseLimit = variant.low_stock_quantity ?? DEFAULT_LINE_LIMIT;

  const existing = cart.find((item) => item.variantId === variant.id);
  if (existing) {
    existing.quantity = Math.min(existing.quantity + 1, purchaseLimit);
    existing.max = purchaseLimit;
  } else {
    cart.push({
      variantId: variant.id,
      productName: product.name,
      variantLabel: variantLabel(variant),
      unitPrice: Number(variant.gross_price),
      quantity: 1,
      max: purchaseLimit,
      image: productImage(product),
    });
  }
  saveCart();
  renderCart();
  openCart();
}

function renderCart() {
  if (!cartItems || !cartEmpty || !cartSummary) return;
  const count = cart.reduce((sum, item) => sum + item.quantity, 0);
  cartCountElements.forEach((element) => { element.textContent = String(count); });
  cartEmpty.hidden = cart.length > 0;
  cartSummary.hidden = cart.length === 0;

  cartItems.innerHTML = cart.map((item) => `
    <article class="cart-line" data-cart-variant="${escapeHtml(item.variantId)}">
      <div class="cart-line-image${item.image ? " has-product-photo" : " is-placeholder"}">${item.image ? `<img src="${escapeHtml(item.image)}" alt="" width="100" height="125">` : '<span aria-hidden="true">R</span>'}</div>
      <div>
        <h3>${escapeHtml(item.productName)}</h3>
        <p>${escapeHtml(item.variantLabel)}</p>
        <div class="cart-line-actions">
          <div class="quantity-control" aria-label="Liczba sztuk">
            <button type="button" data-cart-action="decrease" aria-label="Zmniejsz liczbę">−</button>
            <span>${item.quantity}</span>
            <button type="button" data-cart-action="increase" aria-label="Zwiększ liczbę" ${item.quantity >= item.max ? "disabled" : ""}>＋</button>
          </div>
          <button class="remove-line" type="button" data-cart-action="remove">Usuń</button>
        </div>
      </div>
      <strong class="cart-line-price">${escapeHtml(priceFormatter.format(item.unitPrice * item.quantity))}</strong>
    </article>`).join("");

  const subtotal = cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0);
  if (cartSubtotal) cartSubtotal.textContent = priceFormatter.format(subtotal);
  updateCheckoutAvailability();
}

function updateCheckoutAvailability() {
  if (!checkoutOpenButton) return;
  const available = checkoutConfig.enabled && cart.length > 0;
  checkoutOpenButton.disabled = !available;
  if (checkoutButtonLabel) {
    checkoutButtonLabel.textContent = checkoutConfig.mode === "loading"
      ? "Ładujemy checkout…"
      : (checkoutConfig.enabled ? "Przejdź do danych" : "Checkout w przygotowaniu");
  }
  if (checkoutNote) {
    checkoutNote.textContent = checkoutConfig.enabled
      ? "Tryb testowy: zapisuje zamówienie i rezerwuje stan bez pobierania pieniędzy."
      : "Uruchomimy zamówienia po konfiguracji płatności i dostawy.";
  }
}

function openCart() {
  if (!cartDrawer || !cartBackdrop) return;
  lastFocusedElement = document.activeElement;
  cartDrawer.classList.add("open");
  cartBackdrop.classList.add("open");
  cartDrawer.setAttribute("aria-hidden", "false");
  document.querySelector("[data-cart-open]")?.setAttribute("aria-expanded", "true");
  document.body.classList.add("cart-open");
  cartDrawer.querySelector(".cart-close")?.focus();
}

function closeCart() {
  if (!cartDrawer || !cartBackdrop) return;
  cartDrawer.classList.remove("open");
  cartBackdrop.classList.remove("open");
  cartDrawer.setAttribute("aria-hidden", "true");
  document.querySelector("[data-cart-open]")?.setAttribute("aria-expanded", "false");
  document.body.classList.remove("cart-open");
  if (lastFocusedElement instanceof HTMLElement) lastFocusedElement.focus();
}

function showInvoiceFields() {
  if (!invoiceFields || !invoiceToggle) return;
  invoiceFields.hidden = !invoiceToggle.checked;
  invoiceFields.querySelectorAll("input").forEach((input) => { input.required = invoiceToggle.checked; });
}

function openCheckout() {
  if (!checkoutDialog || !checkoutForm || !checkoutConfig.enabled || !cart.length) return;
  checkoutDialogTrigger = document.activeElement;
  closeCart();
  checkoutForm.hidden = false;
  if (checkoutSuccess) checkoutSuccess.hidden = true;
  if (checkoutError) checkoutError.hidden = true;
  checkoutToken ||= newCheckoutToken();
  const subtotal = cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0);
  if (checkoutTotal) checkoutTotal.textContent = priceFormatter.format(subtotal);
  showInvoiceFields();
  checkoutDialog.showModal();
  document.body.classList.add("checkout-open");
  checkoutForm.querySelector("input")?.focus();
}

function closeCheckout() {
  if (!checkoutDialog?.open) return;
  checkoutDialog.close();
  document.body.classList.remove("checkout-open");
  if (checkoutDialogTrigger instanceof HTMLElement) checkoutDialogTrigger.focus();
}

async function submitCheckout(event) {
  event.preventDefault();
  if (!checkoutForm || !checkoutToken || !cart.length) return;
  const submitButton = checkoutForm.querySelector("[type='submit']");
  const formData = new FormData(checkoutForm);
  const payload = Object.fromEntries(formData.entries());
  payload.address_line_2 = payload.apartment_number || "";
  payload.tax_id = payload.invoice_tax_id || "";
  delete payload.apartment_number;
  delete payload.invoice_tax_id;
  payload.checkout_token = checkoutToken;
  payload.invoice_requested = invoiceToggle?.checked === true;
  payload.terms_accepted = formData.has("terms_accepted");
  payload.lines = cart.map((item) => ({ variant_id: item.variantId, quantity: item.quantity }));
  if (checkoutError) checkoutError.hidden = true;
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.querySelector("span").textContent = "Zapisujemy…";
  }

  try {
    const response = await fetch("/api/orders/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken(), Accept: "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.error || "Nie udało się zapisać zamówienia.");
      error.field = data.field;
      throw error;
    }

    cart = [];
    saveCart();
    renderCart();
    checkoutForm.hidden = true;
    if (checkoutSuccess) checkoutSuccess.hidden = false;
    const number = document.querySelector("[data-checkout-order-number]");
    const message = document.querySelector("[data-checkout-success-message]");
    if (number) number.textContent = data.order.number;
    if (message) {
      const expiry = data.order.reservation_expires_at
        ? new Date(data.order.reservation_expires_at).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" })
        : null;
      message.textContent = `${data.message}${expiry ? ` Rezerwacja stanu wygasa o ${expiry}.` : ""}`;
    }
    checkoutForm.reset();
    showInvoiceFields();
    checkoutToken = null;
    loadCatalog();
  } catch (error) {
    if (checkoutError) {
      checkoutError.textContent = error.message;
      checkoutError.hidden = false;
    }
    if (error.field) {
      const fieldAliases = { address_line_2: "apartment_number", tax_id: "invoice_tax_id" };
      checkoutForm.querySelector(`[name="${CSS.escape(fieldAliases[error.field] || error.field)}"]`)?.focus();
    }
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.querySelector("span").textContent = "Zapisz zamówienie testowe";
    }
  }
}

async function loadCheckoutConfig() {
  try {
    const response = await fetch("/api/orders/config/", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error();
    checkoutConfig = await response.json();
  } catch {
    checkoutConfig = { enabled: false, mode: "unavailable" };
  }
  updateCheckoutAvailability();
}

productRail?.addEventListener("click", (event) => {
  const openButton = event.target.closest("[data-product-open]");
  const openCard = openButton?.closest("[data-product-id]");
  if (openButton && openCard) {
    const product = catalog.find((item) => item.id === openCard.dataset.productId);
    if (product) openProduct(product, true, openButton);
    return;
  }
  const addButton = event.target.closest("[data-add-to-cart]");
  const card = addButton?.closest("[data-product-id]");
  if (addButton && card) addSelectedVariant(card);
});

collectionRail?.addEventListener("click", (event) => {
  const card = event.target.closest("[data-collection]");
  if (!card) return;
  event.preventDefault();
  chooseCollection(card.dataset.collection);
});
collectionsPrev?.addEventListener("click", () => scrollCollections(-1));
collectionsNext?.addEventListener("click", () => scrollCollections(1));
collectionRail?.addEventListener("scroll", updateCollectionControls, { passive: true });
window.addEventListener("resize", updateCollectionControls);
catalogFilters?.addEventListener("animationend", () => catalogFilters.classList.remove("filter-arrival"));
requestAnimationFrame(updateCollectionControls);

catalogFilters?.addEventListener("input", applyFilters);
catalogFilters?.addEventListener("change", applyFilters);
catalogFilters?.addEventListener("submit", (event) => {
  event.preventDefault();
  applyFilters();
});
catalogFilters?.addEventListener("reset", (event) => {
  event.preventDefault();
  catalogFilters.reset();
  applyFilters();
  filterSearch?.focus();
});

productDetail?.addEventListener("change", (event) => {
  if (event.target.matches("[data-variant-select]")) updateDetailVariant();
});

productDetail?.addEventListener("click", async (event) => {
  const imageButton = event.target.closest("[data-detail-image]");
  if (imageButton) {
    const mainImage = productDetail.querySelector("[data-detail-main-image]");
    if (mainImage) mainImage.src = imageButton.dataset.detailImage;
    productDetail.querySelectorAll("[data-detail-image]").forEach((button) => button.removeAttribute("aria-current"));
    imageButton.setAttribute("aria-current", "true");
    return;
  }
  const addButton = event.target.closest("[data-add-to-cart]");
  if (addButton) {
    const productContainer = productDetail;
    closeProduct();
    addSelectedVariant(productContainer);
    return;
  }
  const copyButton = event.target.closest("[data-product-copy]");
  if (copyButton) {
    const link = window.location.href;
    try {
      await navigator.clipboard.writeText(link);
      copyButton.textContent = "Link skopiowany ✓";
    } catch {
      window.prompt("Skopiuj link do produktu:", link);
    }
  }
});

document.querySelector("[data-product-close]")?.addEventListener("click", () => closeProduct());
productDialog?.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeProduct();
});
productDialog?.addEventListener("click", (event) => {
  if (event.target === productDialog) closeProduct();
});
window.addEventListener("hashchange", syncProductRoute);

cartItems?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-cart-action]");
  const line = button?.closest("[data-cart-variant]");
  const item = cart.find((entry) => entry.variantId === line?.dataset.cartVariant);
  if (!button || !item) return;
  if (button.dataset.cartAction === "increase") item.quantity = Math.min(item.quantity + 1, item.max);
  if (button.dataset.cartAction === "decrease") item.quantity = Math.max(item.quantity - 1, 1);
  if (button.dataset.cartAction === "remove") cart = cart.filter((entry) => entry.variantId !== item.variantId);
  saveCart();
  renderCart();
});

document.querySelectorAll("[data-cart-open]").forEach((button) => button.addEventListener("click", openCart));
document.querySelectorAll("[data-cart-close]").forEach((button) => button.addEventListener("click", closeCart));
checkoutOpenButton?.addEventListener("click", openCheckout);
document.querySelectorAll("[data-checkout-close]").forEach((button) => button.addEventListener("click", closeCheckout));
checkoutForm?.addEventListener("submit", submitCheckout);
invoiceToggle?.addEventListener("change", showInvoiceFields);
checkoutDialog?.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeCheckout();
});
checkoutDialog?.addEventListener("click", (event) => {
  if (event.target === checkoutDialog) closeCheckout();
});
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeCart(); });
renderCart();

async function loadCatalog() {
  try {
    const response = await fetch("/api/catalog/products/", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    catalog = Array.isArray(data.products) ? data.products : [];
    populateFilters();
    applyFilters();
    syncCartWithCatalog();
    syncProductRoute();
  } catch {
    if (!productRail) return;
    productRail.setAttribute("aria-busy", "false");
    productRail.innerHTML = '<div class="catalog-error"><p>Nie udało się pobrać katalogu.<br>Odśwież stronę za chwilę.</p></div>';
  }
}

loadCheckoutConfig();
loadCatalog();
