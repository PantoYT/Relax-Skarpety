# Relax Skarpety

Nowy storefront marki Relax. Strona główna prezentuje własną produkcję, kolekcje, historię firmy, ofertę hurtową, sociale i kontakt. Katalog pobiera produkty z PostgreSQL, koszyk działa lokalnie w przeglądarce, a panel obsługuje produkty, warianty, stany, zamówienia i import CSV. Płatności oraz dostawy zostaną podpięte po wyborze operatorów.

## Podgląd lokalny

```powershell
python -m http.server 8123
```

Następnie otwórz `http://localhost:8123`.

## Układ repozytorium

- `index.html`, `styles.css`, `app.js` — aktualny front strony.
- `assets/` — font firmowy, ikony i obecne fotografie produktów.
- `data/product-import-template.csv` — pusty arkusz do pierwszego spisu wariantów i stanów.
- `legacy/site-2026-09-06/` — komplet poprzedniej strony, zachowany do odzyskiwania treści i materiałów.
- `docs/DEPLOYMENT.md` — zasady przenoszenia kodu, sekretów i danych na serwer.
- `docs/PRODUCT-MODEL.md` — model produktu, wariantów, cen, magazynu, tagów i popularności.

## Kierunek techniczny sklepu

Backend korzysta z Django 5.2 LTS i PostgreSQL. Django zapewnia logowanie, uprawnienia oraz panel pracowników, a transakcyjne ruchy magazynowe chronią stan przy równoczesnej pracy kilku osób. Nginx nadal serwuje obecny statyczny storefront i przekazuje `/admin/` oraz `/api/` do backendu.

Nie wpisuj danych dostępowych do repozytorium. Wzór publicznych ustawień znajduje się w `.env.example`.

## Uruchomienie pełnego środowiska

1. Lokalnie skopiuj `.env.local.example` jako `.env`. Na serwerze użyj `.env.example` i ustaw własne hasła oraz sekret.
2. Uruchom `docker compose up --build -d`.
3. Utwórz pierwszego administratora: `docker compose exec backend python manage.py createsuperuser`.
4. Otwórz storefront pod `http://localhost:8080`, a panel pod `http://localhost:8080/admin/`.

Publiczny katalog JSON jest dostępny pod `/api/catalog/products/`, a kontrola działania bazy pod `/api/health/`.

## Testowy checkout

Lokalny `.env.local.example` ustawia `CHECKOUT_MODE=test`. Koszyk otwiera wtedy formularz, a jego wysłanie tworzy prawdziwy rekord zamówienia w lokalnej bazie, rezerwuje stan na 30 minut i dodaje testowy rekord płatności. Nie pobiera pieniędzy, nie wysyła wiadomości i nie zleca przesyłki. Powtórzenie tego samego żądania wykorzystuje token koszyka i nie tworzy drugiego zamówienia.

Na serwerze `CHECKOUT_MODE=disabled` pozostaje obowiązkowe do czasu wdrożenia operatora płatności, cennika dostawy, regulaminu i polityki prywatności. Endpoint konfiguracji to `/api/orders/config/`, a zapis zamówienia używa `POST /api/orders/` z ochroną CSRF.

## Import produktów

W panelu otwórz `Katalog i magazyn → Produkty → Importuj CSV`. Import ma dwa kroki: najpierw sprawdza cały plik i pokazuje podgląd, a dopiero osobne potwierdzenie zapisuje dane. Niepoprawny wiersz blokuje cały zapis, więc baza nie zostaje częściowo zmieniona.

Pusty szablon można pobrać bezpośrednio z ekranu importu. Jeden wiersz oznacza jeden wariant. Ponowny import tego samego `product_key` i wariantu aktualizuje dane oraz ustawia wskazany stan online; nie tworzy duplikatu. Rzeczywiste zmiany stanów trafiają do historii ruchów magazynowych.

Panel zawiera także zamówienia. Utworzenie zamówienia rezerwuje sztuki na 30 minut, ręczne lub przyszłe automatyczne potwierdzenie płatności zdejmuje je ze stanu, a anulowanie zwalnia rezerwację. Każda zmiana statusu i magazynu pozostawia historię.
