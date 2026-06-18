# Lokalize Scraper

Lokalize uygulamasının etkinlik verisini topladığı Python tabanlı veri toplama servisi. Birden fazla sağlayıcıdan (bilet platformları, belediye siteleri, arama motoru sonuçları) etkinlikleri çekip normalize eder ve [Lokalize Backend](https://github.com/erencettin/lokalize-backend)'e senkronize eder.

## Mimari

```
                 ┌──────────────────┐
 Providers  ──►  │  Normalized Event │ ──► SyncService ──► Backend API (X-Scraper-Key)
                 └──────────────────┘
```

Her sağlayıcı (`providers/`) kendi kaynağından veri çeker, ortak bir `NormalizedEvent` modeline dönüştürür. `services/sync_service.py` bu olayları toplu (bulk) olarak backend'e POST eder ve artık görünmeyen kayıtları pasifleştirir (stale cleanup).

## Sağlayıcılar (Providers)

| Provider | Kaynak | Tip |
|---|---|---|
| `TicketmasterProvider` | Ticketmaster Discovery API | Affiliate API |
| `BiletcomProvider` | Bilet.com Affiliate API | Affiliate API |
| `BiletimgoProvider` | biletimGO API | Affiliate API |
| `BiletinialProvider` | Biletinial Facebook/Google ürün feed'i | Affiliate Feed |
| `MunicipalRssProvider` | İBB ve bağlı kurumların RSS/WordPress feed'leri | RSS/Open Data |
| `MunicipalWebProvider` | İlçe belediyelerinin web siteleri | HTML Scraping |
| `EventsSyncService` (SerpAPI) | Google Search / Local sonuçları | Yakındaki mekanlar |

Her provider, `BiletixDetailFetcher` gibi yardımcı modüllerle fiyat/detay zenginleştirmesi de yapabilir (ilgili platformlardan izin alınan sayfalar için).

## Kurulum

```bash
git clone https://github.com/erencettin/lokalize-scraper.git
cd lokalize-scraper
pip install -r requirements.txt
cp .env.example .env   # değerleri doldur
```

`.env` dosyası **asla commit edilmez** (`.gitignore`'da). Gerekli ortam değişkenleri için `.env.example`'a bak.

## Kullanım

```bash
python main.py                              # tüm provider'ları sırayla çalıştır
python main.py --provider TicketmasterProvider
python main.py --parallel                   # provider'ları paralel çalıştır
python main.py --dry-run                    # sadece çek, DB'ye yazma
```

`SYNC_MODE=dry_run` ortam değişkeni de aynı etkiyi verir (CI/test ortamlarında kullanışlı).

## Otomasyon

`.github/workflows/` altında her sağlayıcı için ayrı bir GitHub Actions cron job'ı tanımlı (6 saatte bir). Her job kendi verisini çekip `data/<provider>/` altına commit eder, ardından `merge.yml` workflow'unu tetikleyerek tüm kaynakları birleştirir.

Gerekli GitHub Secrets:

| Secret | Açıklama |
|---|---|
| `BACKEND_URL` | Lokalize Backend API adresi |
| `SCRAPER_API_KEY` | Backend'e kimlik doğrulama için `X-Scraper-Key` |
| `TICKETMASTER_API_KEY` | Ticketmaster Discovery API key |
| `SERPAPI_API_KEY` | SerpAPI key |
| `BILETIMGO_ACCESS_TOKEN` | biletimGO erişim token'ı |
| `BILETCOM_CLIENT_ID` / `BILETCOM_CLIENT_SECRET` | Bilet.com affiliate API kimlik bilgileri |
| `BILETINIAL_FEED_URLS` / `BILETINIAL_AFFILIATE_ID` | Biletinial feed adresleri ve affiliate kimliği |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Bazı job'larda kullanılan eski env adları (bkz. not) |

> **Not:** Veritabanı artık Supabase değil, Railway üzerinde barındırılan PostgreSQL'dir. Bazı workflow'larda env adı tarihsel olarak `SUPABASE_*` kalmıştır.

## Test

```bash
pytest
```

`tests/` altında provider parser'ları, fiyat çıkarıcılar ve sync servisleri için birim testler bulunur. `fixtures/` ve `tests/fixtures/` klasörleri gerçek API/HTML yanıtlarının örnek (sanitize edilmiş) kopyalarını içerir.

## Proje Yapısı

```
providers/      # her veri kaynağı için izole modül (http_client, parser, event_builder, provider)
services/       # sync_service, events_sync_service, matching_service, trend_analysis_service
models/         # NormalizedEvent, NormalizedPlace
utils/          # tarih/fiyat parse, metin normalizasyonu, compliance (robots.txt, rate limit)
clients/        # backend_client, serpapi_client
scripts/        # her provider için tek başına çalıştırılabilir entry point'ler
data/           # her provider'ın son çektiği veri + istatistik (otomatik commit edilir)
```

## Lisans ve Kullanım

Bu repo, Lokalize uygulamasının özel (private) altyapı bileşenidir; harici kullanım için sağlanmamıştır.
