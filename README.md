# EcoWebLab Lead Radar — wersja GitHub Actions

Automatyczny screening stron polskich firm B2B, bez VPS, karty i zewnętrznych płatnych API.

## Jak uruchomić

1. W repozytorium otwórz **Actions**.
2. Wybierz **EcoWebLab - codzienny radar**, następnie **Run workflow**.
3. Po wykonaniu otwórz **Summary** — tabela potencjalnych okazji.
4. W **Artifacts** pobierz plik `leady.csv` (Excel) i `raport.md`.

Automat będzie planowany codziennie o 06:17 UTC. GitHub może opóźniać harmonogram, a w publicznym nieaktywnym repozytorium może go czasowo wyłączyć.

## Co robi

Szuka producentów, firm CNC, dystrybutorów, firm technicznych i architektonicznych w publicznych wynikach RSS Bing. Dla maksymalnie 25 unikalnych domen sprawdza podstawowe elementy HTML strony głównej i wykonuje punktowany screening. Każda pozycja ma URL. Problemy z pobraniem są raportowane, nie ukrywane.

## Ograniczenia i prywatność

- To heurystyka, nie pełen Lighthouse i nie pentest. Brak CSP nie dowodzi podatności, a wolna odpowiedź w jednym pomiarze nie dowodzi stale wolnej strony.
- Nie ma modelu językowego AI ani identyfikacji decydentów. Nie są wysyłane wiadomości marketingowe.
- Wyszukanie domeny nie potwierdza, że firma chce kupić stronę. Wymaga ręcznej kwalifikacji.
- **Uwaga: to repozytorium jest PUBLICZNE.** Nie umieszczaj w nim poufnych danych, kontaktów, notatek CRM ani kluczy API. Artefakty uruchomień mogą być publicznie widoczne.
- Źródło Bing RSS może ograniczyć lub odmówić odpowiedzi. Raport pozostanie wtedy pusty lub częściowy, a błędy będą opisane.

## Dodatkowe strony do sprawdzenia

Opcjonalnie stwórz w głównym katalogu `seeds.csv` z nagłówkami `url,industry` i adresami **publicznych stron firm**. Nie dodawaj tam danych poufnych.
