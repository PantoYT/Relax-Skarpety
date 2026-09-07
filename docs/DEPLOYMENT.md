# Przenoszenie na serwer

Kod i konfiguracja prywatna mają dwie osobne drogi:

1. Kod aplikacji przechodzi przez Git.
2. Sekrety, pliki `.env`, klucze, dane PostgreSQL oraz prywatne kopie zapasowe nigdy nie trafiają do Git.

Przy pierwszym wdrożeniu tworzymy na serwerze katalog aplikacji oraz prywatny katalog runtime. Kod można pobrać przez `git clone`, a `.env` i inne potrzebne pliki przenieść osobno po lokalnym połączeniu kablowym (np. `scp` albo `rsync`). Po transferze należy ograniczyć prawa dostępu do plików z sekretami.

Przy kolejnych wdrożeniach Git aktualizuje wyłącznie kod. Prywatna konfiguracja pozostaje na serwerze i jest montowana do kontenerów. Zmiany w `.env.example` są jawą dokumentacją nowych nazw zmiennych; prawdziwe wartości uzupełnia się ręcznie lub przez bezpieczny transfer.

Przed uruchomieniem sprzedaży potrzebne będą osobne kopie zapasowe bazy i zdjęć produktów oraz test odtworzenia kopii na czystym środowisku.
