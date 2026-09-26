# Relax Skarpety

The new storefront for the Relax sock brand. The home page presents the company's own
production, collections, history, wholesale offer, socials and contact. The catalog
loads products from PostgreSQL, the cart works locally in the browser, and the admin
panel handles products, variants, stock, orders and CSV import. Payments and shipping
will be connected once the providers are chosen.

The site itself is in Polish (Polish market).

## Local preview

```powershell
python -m http.server 8123
```

Then open `http://localhost:8123`.

## Repository layout

- `index.html`, `styles.css`, `app.js` — the current front end.
- `assets/` — brand font, icons and current product photos.
- `data/product-import-template.csv` — an empty sheet for the first inventory of variants and stock.
- `legacy/site-2026-09-06/` — the complete previous site, kept for recovering content and materials.
- `docs/DEPLOYMENT.md` — rules for moving code, secrets and data to the server.
- `docs/PRODUCT-MODEL.md` — the model for products, variants, prices, stock, tags and popularity.
- `docs/LAUNCH-READINESS.md` — the current list of gaps before accepting real payments.

## Technical direction

The backend uses Django 5.2 LTS and PostgreSQL. Django provides login, permissions and
a staff panel, and transactional stock movements protect inventory when several people
work at once. Nginx still serves the current static storefront and forwards `/admin/`
and `/api/` to the backend.

Don't put credentials in the repository. A template of the public settings is in
`.env.example`.

## Running the full environment

1. Locally copy `.env.local.example` to `.env`. On the server use `.env.example` and set
   your own passwords and secret.
2. Run `docker compose up --build -d`.
3. Create the first administrator: `docker compose exec backend python manage.py createsuperuser`.
4. Open the storefront at `http://localhost:8080` and the panel at `http://localhost:8080/admin/`.

The public JSON catalog is at `/api/catalog/products/`, and the database health check at
`/api/health/`.

## Test checkout

The local `.env.local.example` sets `CHECKOUT_MODE=test`. The cart then opens a form,
and submitting it creates a real order record in the local database, reserves stock for
30 minutes and adds a test payment record. It takes no money, sends no messages and
books no shipment. Repeating the same request reuses the cart token and doesn't create
a second order.

On the server `CHECKOUT_MODE=disabled` stays mandatory until a payment provider,
shipping price list, terms of service and privacy policy are in place. The
configuration endpoint is `/api/orders/config/`, and orders are saved with
`POST /api/orders/` under CSRF protection.

## Product import

In the panel open `Katalog i magazyn → Produkty → Importuj CSV` (Catalog and stock →
Products → Import CSV). The import has two steps: it first validates the whole file and
shows a preview, and only a separate confirmation saves the data. An invalid row blocks
the whole write, so the database is never partially changed.

The empty template can be downloaded straight from the import screen. One row is one
variant. Re-importing the same `product_key` and variant updates the data and sets the
given online stock; it doesn't create a duplicate. Real stock changes go into the stock
movement history.

The panel also has orders. Creating an order reserves units for 30 minutes, a manual or
future automatic payment confirmation takes them off stock, and cancelling releases the
reservation. Every status and stock change leaves a history entry.
