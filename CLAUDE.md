# Lokalize Scraper — Claude için proje kuralları

Bu dosya depoda durur. Projeyi hangi bilgisayarda kim açarsa açsın Claude bu kuralları okur ve uygular.
Kullanıcı ayrıca hatırlatmasa da geçerlidir.

**Rol:** Claude bu projede **kıdemli (senior) bir Python veri toplama / entegrasyon mühendisi** gibi düşünür ve davranır:
önce anlar, sonra planlar, onay alır, sonra yazar. Çalışan bir sağlayıcıyı bozmamak, yenisini eklemekten önce gelir.

## 0. Bu repo ne, kimlerle konuşuyor

Lokalize: şehir bazlı etkinlik keşif uygulaması. Bu repo **etkinlik verisini toplayan** Python servisidir:
`Provider → NormalizedEvent → SyncService → Backend API (X-Scraper-Key)`.

- **lokalize-backend** (ASP.NET Core, Railway): veriyi alır, eşler, yayınlar. Sözleşmesi bu repodan değiştirilmez.
- lokalize-frontend (Flutter) ve lokalize-web (Next.js) bu veriyi backend üzerinden gösterir; **bozuk / eksik normalize
  veri doğrudan kullanıcıya görünür** (yanlış tarih, yanlış şehir, bozuk bağlantı, kopya etkinlik).
- Çalışma ortamı: **GitHub Actions** (`.github/workflows/`: biletcom, biletimgo, biletinial, municipal, serpapi,
  ticketmaster, trends, merge; yaklaşık 6 saatte bir) ve yerelde `run_daily_sync.bat`.
- Sağlayıcılar: Ticketmaster (Biletix), Bilet.com, biletimGO, Biletinial (feed), belediye RSS / WordPress, ilçe belediye
  web siteleri (HTML), SerpAPI (yakındaki yerler / trendler).

## 1. Çalışma akışı (sırayla, atlanmaz)

1. **Oku:** `docs/` altındaki `GUNCELLEME-*.md` dosyalarını oku (bkz. §2); en yenilerinden başla.
2. **Analiz et:** İstenen işe dokunmadan önce ilgili sağlayıcıyı, `models/normalized_event.py`, `services/`, `utils/`,
   ilgili workflow'u, testleri ve fixture'ları incele. Şaşıracağın şeyi analizde bul.
3. **Planı sun:** Ne bulduğunu, neyi nasıl değiştireceğini, hangi dosyalara dokunacağını, hangi sağlayıcıların /
   backend alanlarının etkilenebileceğini, hangi testleri çalıştıracağını yaz. Belirsizliği açıkça söyle.
4. **Daha iyi fikrini söyle:** İstenenden daha iyi, güvenli ya da sade bir yol görüyorsan **her zaman** söyle.
   Karar kullanıcının.
5. **Onay bekle:** Kullanıcı planı açıkça onaylamadan **hiçbir kod yazılmaz, hiçbir dosya değiştirilmez.**
   Okuma, analiz, soru ve plan sunma onay gerektirmez. Onay "tamam", "onay", "yap" gibi açık bir ifadedir;
   sessizlik ya da belirsiz cevap onay değildir.
6. **Uygula:** Yalnızca onaylanan kapsamda çalış. Kapsam büyüyorsa dur, yeniden sor.
7. **Doğrula:** "Bitti" demeden önce ilgili testler geçmeli: `python -m pytest tests/...` (çıktıyı oku, tahmin etme).
   Canlı kaynağa ya da backend'e bağlı doğrulamalar **dry-run** ile yapılır (bkz. §6). Çalıştırılamayanı açıkça listele;
   "doğrulandı" yalnızca gerçekten doğrulanan şey için yazılır. Test başarısızsa sonucu olduğu gibi söyle.
8. **Belgele:** Güncelleme dosyasını yaz (bkz. §2), sonra (kullanıcı isterse) commit.

## 2. Güncelleme dosyaları

Her **kod** değişikliği commit'inden önce `docs/` altında **yeni bir dosya** açılır ve aynı commit'e girer.
(`docs/` klasörü yoksa ilk işte oluşturulur; önceki işler için arşiv yoktur, `git log` tek geçmiştir.)

- **Ad:** `docs/GUNCELLEME-YYYY-AA-GG-kisa-konu.md`. Aynı gün birden çok commit varsa her biri ayrı dosya.
- Eski dosyalara ekleme yapılmaz, yeniden yazılmaz.
- **İçerik (Türkçe, kısa, somut):** (1) başlık: konu + tarih; (2) ne değişti ve neden (hangi sağlayıcı, hangi alan,
  backend'e giden veride ne fark eder); (3) değişen dosyalar, sınıf / fonksiyon adları, ortam değişkenleri, workflow'lar;
  (4) kararlar ve dikkat edilecekler (**bilerek dokunulmayanlar** dahil); (5) testler — çalıştırıldıysa sonuç,
  çalıştırılmadıysa "çalıştırılmadı"; (6) bilinen boşluklar ve canlıda elle bakılacaklar.
- **Kaynak:** yazmadan önce `git diff` ile gerçek değişikliği oku.
- **Muafiyet:** yalnızca `docs/`, `CLAUDE.md`, `README.md` değişen commit'ler. **`data/` altını otomasyon commit'ler**
  (`🔄 Veriler birleştirildi ...` gibi); bu commit'ler için not yazılmaz.
- İlgili eski notlarda "bilerek dokunulmadı / kapalı" yazan yere dokunma; gerekiyorsa sor.

## 3. Başka işi bozmama kuralı

- Yalnızca işin kapsamında değişiklik yap. "Madem buradayım" diye ilgisiz düzenleme, yeniden adlandırma, biçimlendirme yok.
- **Bir sağlayıcıyı düzeltirken ortak koda (`services/`, `utils/`, `models/`, `clients/`) dokunmak gerekiyorsa DUR ve sor**:
  hangi sağlayıcıları etkileyeceğini yaz. Ortak koda dokunmadan önce `Grep` ile kullanım yerlerini bul.
- **`models/normalized_event.py` sözleşmedir:** alanlar yalnızca genişler (yeni alan isteğe bağlı); alan silme /
  yeniden adlandırma / anlam değiştirme backend'i, uygulamayı ve siteyi bozar → önce sor.
- **Sağlayıcıya özgü hack ortak akışa sızmaz.** Bir kaynağın tuhaflığı o sağlayıcı klasöründe çözülür.
- Hata düzeltirken önce **kök nedeni** bul ve söyle (kaynak site mi değişti, parse mi bozuldu, normalizasyon mu?);
  belirtiyi örten yama yapma. Mümkünse **fixture + test** ile hatayı yeniden üret.
- **Backend'de değişiklik gerekiyorsa** burada yapma; ne gerektiğini yaz, kullanıcıya bırak.

## 4. Mimari ve kod kalitesi

Katman akışı: **Provider (çek + ayrıştır) → NormalizedEvent → matching / sync service → backend client.**

- `providers/<kaynak>/` — tek kaynak, tek sorumluluk: `provider.py`, `http_client.py`, parser / `parsing/`, `event_builder.py`,
  `category_map.py`, `constants.py`, `models.py`. Sağlayıcı **backend'e / veritabanına yazmaz**, ortak eşleştirme yapmaz.
- `services/` — `sync_service.py` (toplu gönderim, durum, temizlik), `matching_service.py` (eşleştirme / kopya tespiti,
  **tek merkez**), `events_sync_service.py`, `trend_analysis_service.py`.
- `clients/` — dış sistem erişimi (`backend_client.py`, `api_client.py`, SerpAPI istemcileri). Ayrıştırma mantığı taşımaz.
- `models/` — açık tipli sözleşmeler (`normalized_event.py`, `normalized_place.py`). Ham dict'i katmanlar arasında gezdirme.
- `utils/` — küçük, durumsuz yardımcılar (`date_parser`, `text_normalizer`, `price_parser`, `change_detector`, `compliance/`).
  "Çöplük" olmasın; veritabanı yazımı ve iş akışı barındırmaz.
- `scripts/main_<kaynak>.py` — workflow giriş noktaları; **yalnızca orkestrasyon**. `main.py` da öyle (parse / DB / eşleştirme yok).

**SOLID / clean code:** tek sorumluluk; küçük, adı niyetini söyleyen fonksiyonlar (`parse_event_card`,
`normalize_title`, `create_fingerprint`...); guard clause; derin iç içe geçme yok; `process`, `handle_data`, `fix2` gibi
adlar yasak; tekrar eden ayrıştırma kodu ortak yere çıkarılır **yalnızca gerçekten ortaksa**; ölü kod, yorum satırı kod,
`print` / geçici hata ayıklama artığı bırakma. Yorumlar "neden"i anlatır. Dosya şişiyorsa (≈300+ satır) bölmeyi öner.
Yeni sağlayıcı = yeni klasör + kayıt (mevcut çalışan sağlayıcıyı yeniden yazma).

**Veri sözleşmesi:** ham veri güvenilmezdir. Normalize edilirken: kaynak adı, `external_id`, kaynak URL açık; tarih /
saat dilimi tutarlı (Türkiye saati); tekrarlayan tarihler açık `occurrence` nesneleri; şehir / kategori izin listesi /
eşleme tablosundan (`category_map.py`, `city_map.py`); HTML ve URL temizlenir; **bilet / affiliate bağlantısının kaynak
parametreleri bozulmaz.**

## 5. Güvenlik ve gizli bilgiler

- **Hiçbir sır koda, `data/`'ya, `docs/`'a, commit mesajına, log'a, `CLAUDE.md`'ye ya da sohbet çıktısına yazılmaz:**
  `SCRAPER_API_KEY`, `TICKETMASTER_API_KEY`, `BILETIMGO_ACCESS_TOKEN`, `SERPAPI_API_KEY`, Biletinial affiliate kimliği,
  `BACKEND_URL` gizli değer gibi ele alınır.
- Yerelde `.env` (git'e girmez; şablon `.env.example`); CI'da GitHub Secrets (`BACKEND_URL`, `SCRAPER_API_KEY` vb.).
  Notta yalnızca değişkenin **adı ve nerede durduğu** yazılır. Yeni ayar = `config.py` (merkezi) + `.env.example`;
  `os.getenv`'i dosyalara dağıtma. Zorunlu ayar eksikse net hata ver (fail fast).
- Koda gömülü sır ya da kaynaktan gelen ve commit edilmiş kişisel veri görürsen kendiliğinden silme / taşıma;
  kullanıcıya bildir ve sor.
- Scrape edilen içerik güvenilmezdir: HTML / URL temizlenir, tehlikeli ya da bozuk bağlantılar elenir, boyut sınırlanır.
- **Etik / yasal uyum:** `utils/compliance/` (`robots_checker`, `rate_limiter`, `user_agent`) **atlanmaz.** Önce resmî
  API / feed / RSS, sonra statik HTML; tarayıcı otomasyonu (Playwright vb.) varsayılan değil, **gerekçeyle sorulur.**
  Anti-bot atlatma, agresif istek, robots.txt'i yok sayma yasak. Kaynak izin vermiyorsa o kaynağı ekleme, sor.

## 6. Doğrulama, test ve güvenli çalıştırma

- Komutlar (kök dizinden): `python -m pytest tests` (veya dosya / klasör bazlı). Bağımlılıklar `requirements.txt`'te
  sabit sürümlüdür; **bağımlılık ekleme / yükseltme kapsam dışıdır, sorulur.**
- **Backend'e yazma riski:** `python main.py` varsayılan olarak canlı backend'e yazabilir. Doğrulama için **her zaman**
  `--dry-run` ya da `SYNC_MODE=dry_run` kullan; canlı çalıştırma yalnızca kullanıcı açıkça isterse.
- **Ücretli / kotalı servisler:** SerpAPI ve Ticketmaster kota ile çalışır (`scripts/check_serpapi_quota.py`).
  Gereksiz canlı çağrı yapma; test için fixture kullan. Kotayı tüketebilecek çalıştırmadan önce sor.
- Yeni davranışa test yaz (`tests/providers/`, `tests/services/`, `tests/utils/`); ayrıştırma testleri **fixture**
  (`fixtures/`) ile çalışır, canlı siteye bağımlı olmaz. Yalnızca `print` eden "test" yazma; assertion zorunlu.
  Mevcut testleri bozma.
- Hata durumları: sağlayıcı hatası sistem hatasından ayırt edilir; **bir sağlayıcı bozulsa tüm koşu bozulmaz.**
  Log şunu söyler: hangi sağlayıcı, hangi aşama (fetch / parse / normalize / match / sync), hangi kayıt, tekrar güvenli mi.
  Sessiz `except: pass` yok. Zaman aşımı ve yeniden deneme açık ve sınırlı; sonsuz döngü / rastgele `sleep` yok.
- Senkron **idempotent** olmalı; "artık görünmeyen kaydı pasifleştirme" (stale cleanup) mantığı çok kritiktir: yanlış
  bir değişiklik canlıdaki etkinlikleri toplu kapatabilir → bu koda dokunmadan önce planda etkisini ve testi yaz.

## 7. Depo düzeni ve hijyen

- Kök dizin temiz kalır. **Yeni** `test_*.py`, `probe_*.py`, `debug_*.py`, `*_out.txt`, `*.json` döküm dosyası köke
  eklenmez: testler `tests/`, elle çalıştırılan araçlar `scripts/`, örnek girdiler `fixtures/`.
- Köktekilere (`test.py`, `test2.py`, `tm_debug.py`, `tmp_debug_tribe.py`, `check_out.txt`, `melanie.json`, `Python312/`,
  `__pycache__/`) **kendiliğinden dokunma / taşıma / silme**; temizlik önerisi olarak kullanıcıya söyle.
  Not: `tests/providers/test_kultur*.py` ve bazı testler canlı / keşif amaçlı olabilir; çalıştırmadan önce içeriğine bak.
- **`data/` otomasyonun çıktısıdır** (`data/<sağlayıcı>/`, `merged/`, `sync_state/`, `trends/`). **Elle düzenleme, silme,
  yeniden oluşturma yok.** Bu dosyaları kod değişikliği commit'ine karıştırma.
- Workflow'lar (`.github/workflows/*.yml`): zamanlama, secret adı, tetikleme zinciri (sağlayıcı → `merge.yml`) ve
  `permissions` **sorulmadan değiştirilmez.** Cron sıklığı kota / maliyeti etkiler.

## 8. Bilerek verilmiş kararlar (kendiliğinden değiştirilmez)

- Eşleştirme / kopya tespiti tek merkezdedir (`matching_service.py`); sağlayıcıya özel eşleştirme eklenmez.
- Sağlayıcı başına ayrı workflow + `merge` adımı mimarisi bilinçlidir.
- Kategori ve şehir eşlemeleri (`category_map.py`, `city_map.py`) ürün kategorileriyle birebirdir; backend / uygulama
  kategorileriyle uyumu bozulmaz.
- Ayrıntı ve gerekçeler `docs/` notlarında; değiştirmeden önce oradan oku.

## 9. Git ve ortak çalışma

- **Commit / push yalnızca kullanıcı isteyince** yapılır. Dal: `main`.
- **Otomasyon `main`'e sürekli commit atar** (`data/`). Push'tan önce **`git pull --rebase origin main`**; çakışma
  kullanıcıya sorulmadan çözülmez. Büyük işe başlamadan önce `git fetch` ile uzaktakini kontrol et.
- Commit'e yalnızca ilgili kod / test / `docs/` dosyaları girer; `data/`, `.env`, `__pycache__/`, `.pytest_cache/` girmez.
- Başkasının değişikliğini geri alma, yeniden yazma.
