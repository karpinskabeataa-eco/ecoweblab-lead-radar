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
