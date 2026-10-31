# Kvety pre Vás – Google Merchant Center feed

Produktový feed pre e-shop [kvetyprevas.sk](https://kvetyprevas.sk), ktorý spravuje NextLayer Studio.

- `kvety_feed.py` načíta produkty z verejných stránok kategórií e-shopu a vytvorí RSS feed s atribútmi pre Google.
- GitHub Actions ho generuje každý deň o 4:30 a zmeny uloží do `kvety-google-feed.xml`.
- Merchant Center (účet 5870831155) si feed sťahuje z adresy:
  `https://raw.githubusercontent.com/NextLayerStudio/kvety-google-feed/main/kvety-google-feed.xml`

Ručné spustenie: záložka Actions → Denný feed → Run workflow.
Ak e-shop vráti menej ako 350 produktov, feed sa neprepíše.
