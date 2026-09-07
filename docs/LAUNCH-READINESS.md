# Gotowość sklepu Relax

Stan dokumentu: 2026-09-07. Sklep pozostaje w trybie testowym. `CHECKOUT_MODE=disabled` jest wymagane na publicznym serwerze do zamknięcia sekcji „Blokery sprzedaży”.

## Co już działa

- responsywny storefront, katalog, warianty i zdjęcia;
- koszyk zapisany lokalnie w przeglądarce;
- panel pracowników z osobnymi kontami i uprawnieniami Django;
- osobny magazyn internetowy, rezerwacje, historia ruchów oraz ochrona przed sprzedażą tej samej sztuki dwa razy;
- progi cenowe, import CSV z podglądem, tagi i ręcznie zatwierdzane sugestie promocji;
- zamówienia testowe, historia statusów oraz przygotowany model płatności;
- Docker, PostgreSQL, Nginx, migracje i harmonogram zwalniania wygasłych rezerwacji;
- sekrety i dane runtime są ignorowane przez Git; repo zawiera wyłącznie bezpieczne przykłady `.env`;
- Google Maps ładuje się dopiero po decyzji użytkownika.

## Blokery sprzedaży

### Dane firmy i dokumenty

- [ ] pełna nazwa przedsiębiorcy, forma prawna, NIP, REGON/KRS, adres siedziby i adres zwrotów;
- [ ] regulamin sklepu, polityka prywatności, polityka plików cookies i wzór odstąpienia od umowy;
- [ ] opis reklamacji z tytułu niezgodności towaru z umową oraz pozasądowych sposobów rozwiązywania sporów;
- [ ] jawny koszt i termin dostawy, zasady zwrotu oraz przycisk finalny jasno wskazujący obowiązek zapłaty;
- [ ] lista podmiotów przetwarzających dane: operator płatności, przewoźnik, poczta, hosting i ewentualne narzędzia statystyczne;
- [ ] okresy przechowywania zamówień, zapytań, logów i zapisów newslettera;
- [ ] ostateczny przegląd dokumentów przez osobę znającą aktualną sytuację prawną i księgową firmy.

### Katalog 20 produktów

Każdy produkt najpierw trafia jako szkic. Publikacja następuje dopiero po sprawdzeniu:

- [ ] nazwy handlowej, typu, wariantów, rozmiarów, kolorów i liczby sztuk online;
- [ ] własnego identyfikatora produktu oraz SKU każdego wariantu; kod kreskowy jest opcjonalny;
- [ ] ceny brutto, stawki VAT oraz prawidłowego progu cenowego;
- [ ] dokładnego składu włókien, instrukcji pielęgnacji i kraju pochodzenia;
- [ ] nazwy, adresu pocztowego i e-maila producenta;
- [ ] podmiotu odpowiedzialnego w UE dla produktu spoza UE, jeżeli ma zastosowanie;
- [ ] wymaganych ostrzeżeń lub jawnej informacji, że dla danego produktu nie ustalono szczególnych ostrzeżeń;
- [ ] prawdziwych zdjęć przedstawiających oferowany wariant, sensownego tekstu alternatywnego i prawa do użycia zdjęć;
- [ ] opisu bez niepotwierdzonych obietnic, np. medycznych lub zdrowotnych;
- [ ] opakowania: jedna para, wielopak i liczba sztuk w zestawie muszą być jednoznaczne w nazwie i opisie.

Po wpisaniu pierwszych 20 produktów wykonujemy jedno zamówienie dla każdego rodzaju wariantu i osobno testujemy: ostatnią sztukę, brak stanu, równoczesny zakup, anulowanie, wygaśnięcie płatności, pełny zwrot i częściowy zwrot.

### Płatności

- [ ] podpisać umowę z operatorem i uzyskać konto testowe oraz produkcyjne;
- [ ] wdrożyć przekierowanie do operatora, BLIK, podpisane powiadomienia serwer-serwer, weryfikację kwoty i idempotencję;
- [ ] stan `PAID` może ustawić tylko poprawnie zweryfikowane powiadomienie operatora albo uprawniony pracownik z audytem;
- [ ] wdrożyć pełny i częściowy zwrot z osobnym identyfikatorem operacji oraz historią;
- [ ] wiadomość po zamówieniu nie może twierdzić, że płatność się udała, dopóki webhook tego nie potwierdzi;
- [ ] nie przechowywać numerów kart, kodów BLIK ani danych uwierzytelniających klienta.

Rekomendacja dla pierwszej wersji: Przelewy24 w wariancie z przekierowaniem. Zapewnia BLIK, przelewy i karty, ogranicza zakres danych płatniczych po stronie Relax i ma API zwrotów. Przed podpisaniem umowy należy porównać ofertę handlową z PayU.

### Dostawa i obsługa zamówienia

- [ ] wybrać InPost/Furgonetkę lub innego operatora oraz podpisać umowę;
- [ ] ustalić paczkomat/kurier, ceny, obszar dostawy, granicę darmowej dostawy i maksymalny czas nadania;
- [ ] dodać wybór punktu odbioru, tworzenie etykiety, numer śledzenia i e-mail po nadaniu;
- [ ] opisać proces pakowania: kto drukuje listę, kto pakuje, kto potwierdza wysyłkę i co dzieje się przy braku produktu;
- [ ] uzgodnić z księgowością paragony, faktury, korekty oraz eksport danych do obecnego programu;
- [ ] sprawdzić obowiązki dotyczące opakowań i BDO dla konkretnej działalności.

## Zwroty i reklamacje

To dwa różne procesy:

1. **Odstąpienie bez podania przyczyny.** Klient zgłasza odstąpienie, odsyła towar na podany adres, a pracownik rejestruje odbiór i stan produktu. Panel wylicza zwrot, pracownik go zatwierdza, a operator płatności odsyła środki tą samą metodą. Koszt przesyłki zwrotnej może ponosić klient, jeśli został o tym wcześniej poprawnie poinformowany.
2. **Reklamacja niezgodnego towaru.** Zgłoszenie trafia do Relax jako sprzedawcy. Koszt odbioru, naprawy lub wymiany ponosi sprzedawca. Panel pilnuje terminu odpowiedzi, żądania klienta, przesyłek i wyniku sprawy.

Operator płatności nie rozstrzyga, czy zwrot lub reklamacja są zasadne. Realizuje przelew zwrotny po dyspozycji sklepu.

## Konta

Na start klienci kupują bez konta. Otrzymują podpisany, wygasający link do statusu zamówienia. Pozwala to uruchomić sprzedaż bez przechowywania kolejnych haseł i budowania odzyskiwania kont.

Pracownicy mają wyłącznie imienne konta. Nie używamy wspólnego administratora. Przed startem potrzebne są role: katalog, magazyn, zamówienia/zwroty oraz administrator; do panelu należy dodać ochronę przed próbami logowania i drugi składnik uwierzytelniania albo ograniczyć panel przez Cloudflare Access.

## Poczta, wsparcie i newsletter

Minimalny zestaw adresów:

- `kontakt@relax-skarpety.com` — pytania i kolejka wsparcia;
- `sklep@relax-skarpety.com` — potwierdzenia i odpowiedzi dotyczące zamówień;
- `zwroty@relax-skarpety.com` — alias do tej samej kolejki wsparcia;
- `newsletter@relax-skarpety.com` — osobny strumień wysyłkowy.

Cloudflare Email Routing może przyjmować pocztę domenową i przekazywać ją do istniejącej skrzynki. Do odpowiedzi, wiadomości transakcyjnych i masowej wysyłki konfigurujemy uwierzytelnionego dostawcę SMTP/API, SPF, DKIM i DMARC.

Pierwsza wersja wsparcia może działać jako wspólna skrzynka. Docelowy moduł zgłoszeń ma status, osobę przypisaną, historię przekazań, wiadomości i załączniki, termin odpowiedzi oraz akcje „przejmij”, „przekaż”, „oczekuje na klienta” i „rozwiązane”. Dane klienta widzi tylko właściwa rola; nie rozsyłamy pełnej treści wszystkim pracownikom.

Newsletter uruchamiamy po transakcyjnej poczcie. Wymaga osobnej, dobrowolnej zgody, potwierdzenia zapisu, dowodu treści i czasu zgody, łatwego wypisu oraz listy blokad. Dodanie produktu lub zatwierdzenie promocji tworzy szkic kampanii; człowiek zawsze zatwierdza odbiorców, treść i wysyłkę.

## Promocje

Sugestia systemu nigdy sama nie zmienia ceny. Przed uruchomieniem promocji dodajemy historię cen wariantu i automatyczne obliczenie najniższej ceny z 30 dni przed obniżką. Ta informacja musi być pokazana wszędzie, gdzie komunikujemy obniżkę konkretnego produktu, także na liście produktów i w reklamie.

## Cookies, prywatność i dostępność

- Niezbędne cookies sesji i CSRF służą działaniu panelu i checkoutu.
- Mapa Google nie ładuje się bez kliknięcia użytkownika.
- Analityka, Meta Pixel, reklamy i inne narzędzia opcjonalne pozostają wyłączone do czasu wdrożenia granularnej zgody i możliwości jej wycofania.
- Formularz zamówienia zbiera tylko dane potrzebne do dostawy, kontaktu i opcjonalnej faktury. Zgoda marketingowa nie może być warunkiem zakupu.
- Przed startem wykonujemy test klawiaturą, czytnikiem ekranu, powiększeniem 200/400%, kontrastu, komunikatów błędów i urządzeń mobilnych. Status ewentualnego wyłączenia mikroprzedsiębiorcy z PAD trzeba potwierdzić, ale sklep i tak utrzymujemy dostępny.

## Serwer i publikacja

Audyt serwera z 2026-09-07:

- Ubuntu 24.04, Docker 29.8, Compose 5.5, 4 rdzenie, 31 GiB RAM i około 147 GiB wolnego miejsca — zasoby wystarczą;
- Cloudflare Tunnel działa i może wystawić sklep bez otwierania portów routera;
- port 80 hosta zajmuje Pi-hole, co nie przeszkadza przy Tunnel;
- nocny backup kończy się powodzeniem, ale repozytorium restic znajduje się na tym samym SSD i zakres trzeba rozszerzyć o bazę oraz media Relax;
- firewall wymaga osobnego sprawdzenia z uprawnieniami administratora;
- UPS jest przydatny, jeśli potrafi zgłosić zanik zasilania do serwera i uruchomić kontrolowane wyłączenie.

Przed publikacją:

- [ ] osobny katalog Compose i niekolidujący port tylko na `127.0.0.1`;
- [ ] trasa Tunnel dla `relax-skarpety.com` i `www`, później osobno chroniony panel;
- [ ] produkcyjny `.env` przeniesiony poza Git, losowe hasła i klucze z ograniczonymi prawami;
- [ ] HTTPS, bezpieczne cookies, redirect HTTP, HSTS po próbie na krótkim czasie oraz poprawne nagłówki proxy;
- [ ] dump PostgreSQL, media i konfiguracja w backupie lokalnym i zaszyfrowanym off-site;
- [ ] próbne odtworzenie na czystej bazie;
- [ ] monitoring strony, API, wygasania certyfikatu/tunelu, miejsca na dysku i powodzenia backupu;
- [ ] staging do testów płatności i dostawy oraz procedura wycofania wersji;
- [ ] usunięcie danych demo i testowych kont z produkcji.

## Kolejność prac

1. Uzupełnić 20 produktów jako szkice i uzyskać dane firmy, księgowości, dostawy oraz zwrotów.
2. Wybrać operatora płatności i przewoźnika; równolegle przygotować dokumenty i pocztę domenową.
3. Wdrożyć prawdziwy checkout, płatności, wysyłkę, wiadomości, status klienta i zwroty.
4. Dodać historię cen, polityki, zgodę cookies dla ewentualnego trackingu i zabezpieczenia panelu.
5. Wykonać testy procesu, dostępności, bezpieczeństwa, backupu i odtworzenia.
6. Opublikować najpierw dla małej grupy, wykonać prawdziwe zamówienie od płatności do zwrotu, a potem otworzyć sklep szerzej.
