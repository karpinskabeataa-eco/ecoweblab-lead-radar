# EcoWebLab — radar producentów w Polsce

Cel: producenci faktycznie wytwarzający w Polsce, których strona wymaga poprawy lub przebudowy. Wszystkie końcówki domen są dozwolone, w tym .com. Katalogi, agregatory, portale oraz sami dystrybutorzy nie są leadami.

## Kwalifikacja

RSS Bing nominuje kandydatów. Skrypt czyta stronę główną i do 3 podstron (firma, oferta, aktualności). Wymaga tekstowego dowodu produkcji w Polsce na witrynie firmy. Jest to heurystyka: dowód musi zostać sprawdzony w codziennym podsumowaniu; brak dowodu wyklucza firmę z CSV. Domena i język nie określają miejsca produkcji. Katalog factories.pl jest jawnie wykluczony. Plik seeds.csv (opcjonalny nagłówek url) może zawierać publiczne strony do sprawdzenia; podlegają tym samym kryteriom.

## Pomiary i dowody

Chromium wykonuje dwa wczytania bez cache: desktop 1365 px i mobile 390 px. Rejestruje czas load, TTFB, przesłane bajty, błędy HTTP zasobów własnej domeny, wyjątki JS, niedziałające obrazy i poziome przewijanie. Próg wolnego ładowania: >4 s w obu próbach; ciężka strona: >3 MB transferu w jednej. To laboratoryjny screening z GitHub (USA), bez symulacji łącza/CPU, nie terenowe Core Web Vitals. Błędy pomiarów są jawne. Blokady dostępu nie są wadą strony i nie są obchodzone.

Dodatkowo: starsze elementy HTML, mało tekstu, brak wyraźnej ścieżki do oferty/kontaktu, brak głównego nagłówka. Słabe proxy nie są automatyczną oceną estetyki. Wygląd, jasność oferty i kompletność informacji wymagają analizy zrzutów oraz treści. Zrzuty są dołączone do artefaktów. Punktacja >=20 daje kandydata, nie potwierdzony lead zakupowy.

Sygnały rozwoju: wzmianki o nowych halach, liniach, zakładach i zwiększeniu mocy. Skrypt zbiera je jako niepotwierdzone; codzienne podsumowanie sprawdza datę (ostatnie 12 miesięcy), źródło, skalę oraz problemy strony. Samo hasło o rozwoju lub zakładka Kariera nie wystarczają.

## Wyniki i harmonogram

GitHub Actions: 06:17 UTC codziennie (08:17 latem / 07:17 zimą w Polsce), ręcznie przez Run workflow oraz po zmianie kodu/workflow/seeds na main. Limit: 12 kandydatów na skan, 18 minut. Artefakty przez 30 dni: raport.md, leady.csv (tylko kandydaci), wyniki.json (także odrzucenia) i zrzuty PNG. Raport dostępny też w Summary i logach. Brak trafnych wyników jest raportowany, nie zastępowany przypadkowymi firmami.

Osobne zadanie w ChatGPT dostarcza podsumowanie około 09:00 czasu Europe/Warsaw i uzupełnia słabe wyniki źródła wyszukiwaniem oraz weryfikacją. Workflow sam nie wysyła wiadomości do ChatGPT.

GitHub może opóźniać skany i wyłącza harmonogram publicznego repo po 60 dniach bez aktywności. Brak płatnych API, VPS i karty. Żadnych wiadomości marketingowych ani logowania do stron firm. Repozytorium, logi i artefakty są publiczne: nie dodawaj kluczy, danych klientów ani notatek CRM.

## Poprawka kwalifikacji — 3 listopada 2026

Portal finansowy lub artykuł o inwestycji innej firmy nie jest producentem. Radar odrzuca znane portale, wydawców oznaczonych NewsMediaOrganization i strony redakcyjne. Dowód musi dotyczyć własnej produkcji w Polsce i pochodzić z głównej treści strony głównej lub strony o firmie/produkcji w tej samej domenie. Teksty artykułów na stronie głównej nie kwalifikują firmy. Sama polska siedziba, domena .pl, dystrybucja lub wzmianka o cudzej fabryce nie wystarczą. To celowo ostrożna heurystyka: może pominąć prawdziwego producenta, który opisuje się inaczej.

Dodano cztery jawne adresy startowe w seeds.csv (Leonium, MATMAT, Scandia Cosmetics, Grapol), znalezione na firmowych stronach o produkcji w Polsce. Są to adresy do ponownego sprawdzenia, nie gotowe leady ani dowód potrzeby przebudowy strony. Pomiar dotyczy zawsze strony głównej, nawet jeśli adresem źródłowym jest strona o firmie. Małe pokrycie wyszukiwania jest zgłaszane w raporcie.

Każdy przebieg zapisuje również **leady.xlsx**: arkusz Kandydaci, Pozostałe domeny i Przebieg. Odrzucenia nie znikają z pełnych wyników, ale nie trafiają do CSV ani arkusza kandydatów. Wyniki są w artefaktach uruchomienia przez 30 dni. Harmonogram i brak płatnych usług pozostają bez zmian.

Testy regresji: `python -m unittest -v test_radar`. Obejmują pomyłkę Bankier.pl, cudze fabryki, portale, dystrybutorów, polską siedzibę bez produkcji, deklaracje PL/EN, domeny obce, brak dowodu i bezpieczeństwo eksportu XLSX.
