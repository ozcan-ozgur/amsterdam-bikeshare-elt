# =============================================================================
# DONKEY BIKE (Amsterdam) -> DuckDB  |  dlt + rest_api_source ile ELT
#
# Bu dosya beş GBFS 3.0 feed'ini çeker. İki gruba ayrılırlar:
#
#   SNAPSHOT (anlık fotoğraf, sürekli değişir) -> "append" ile birikir:
#     - station_status       : her istasyonda şu an kaç bisiklet / boş yer var
#     - vehicle_status       : her bisikletin şu anki konumu ve durumu
#
#   REFERANS (nadiren değişir, "sözlük" gibi) -> "replace" ile her seferinde yenilenir:
#     - station_information  : istasyonların adı, konumu, kapasitesi
#     - system_pricing_plans : fiyat planları
#     - vehicle_types        : bisiklet türleri (elektrikli mi, menzil vb.)
#
# ELT'nin E (Extract) ve L (Load) adımlarını dlt yapar.
# T (Transform) adımı bu dosyada yok; onu sonra veritabanının içinde (ör. dbt) yaparız.
# =============================================================================


# -----------------------------------------------------------------------------
# 1) IMPORT'LAR VE SABİTLER
#
# - dlt              : pipeline'ı kuran ve veriyi hedefe yazan kütüphane.
# - rest_api_source  : dlt'nin hazır REST API kaynağı. elt.py'deki gibi
#                      requests.get(...) yazmak yerine bir AYAR SÖZLÜĞÜ veririz,
#                      HTTP isteğini, JSON çözmeyi ve satırlara bölmeyi o yapar.
# - datetime         : her satıra "ne zaman çektik" damgası basmak için.
#
# BASE_URL "/" ile bitiyor: aşağıdaki "station_status.json" gibi yollar
# bu adresin SONUNA eklenir. "/" olmasaydı son parça (donkey_am) silinirdi.
# -----------------------------------------------------------------------------
from datetime import datetime, timezone

import dlt
from dlt.sources.rest_api import rest_api_source

BASE_URL = "https://stables.donkey.bike/api/public/gbfs/3.0/donkey_am/"

# elt.py'de kullandığınız başlık. Sunucuya kim olduğumuzu kibarca söyler.
HEADERS = {"User-Agent": "This is an ELT learning project"}


# -----------------------------------------------------------------------------
# 2) SATIRA ZAMAN DAMGASI EKLEYEN FONKSİYON
#
# Sorun: JSON'un en dışında "last_updated" var, ama aşağıda data_selector ile
# sadece "data.stations" listesini alıyoruz. Dış kabuk (zarf) atılıyor.
#
# station_status ve vehicle_status "anlık fotoğraf" verisidir. Pipeline'ı her
# çalıştırdığımızda yeni bir fotoğraf eklenecek (append). Fotoğrafları birbirinden
# ayırmak için her satıra "fetched_at" (çekilme zamanı) ekliyoruz.
#
# Bu fonksiyon tek bir satır (sözlük) alır, değiştirip geri döndürür.
# Aşağıda processing_steps -> "map" ile her satıra uygulanacak.
#
# DİKKAT: Saati FONKSİYONUN DIŞINDA, dosya çalışırken BİR KEZ alıyoruz.
# datetime.now() fonksiyonun içinde olsaydı her satır mikrosaniye farkla
# farklı bir saat alırdı ve "aynı fotoğrafın satırları" birbirinden ayrılırdı.
# Tek bir sabit saat ile şunu yazabiliriz:
#   SELECT fetched_at, SUM(num_vehicles_available) FROM station_status GROUP BY 1
#
# BİLMEKTE FAYDA VAR:
# - dlt her satıra zaten "_dlt_load_id" yazar (her çalıştırmaya özel bir kimlik).
#   _dlt_loads tablosundaki inserted_at ile join yaparak da fotoğrafları
#   ayırabilirdik. fetched_at bu join'e gerek bırakmadığı için pratik.
# - fetched_at "BİZİM çektiğimiz" zamandır. Verinin "sunucuda güncellendiği" zaman
#   JSON'un dışındaki "last_updated" alanıdır; data_selector zarfı attığı için
#   onu kaybediyoruz. Bu proje için fark önemsiz (birkaç saniye).
# - FETCHED_AT dosya yüklenirken alınır. Aynı Python sürecinde pipeline'ı
#   döngüyle birden çok kez çalıştırırsanız hepsi aynı saati alır; o durumda
#   saati run'dan hemen önce almak gerekir.
# -----------------------------------------------------------------------------
FETCHED_AT = datetime.now(timezone.utc)


def add_fetched_at(row: dict) -> dict:
    row["fetched_at"] = FETCHED_AT
    return row


# -----------------------------------------------------------------------------
# 3) REST API AYARLARI
#
# Bütün pipeline'ın tarifi bu sözlükte. Üç bölümü var:
#   a) client            : HER istek için ortak olan bilgiler (adres, başlıklar)
#   b) resource_defaults : her resource'a (tabloya) varsayılan olarak uygulanan ayarlar
#   c) resources         : tek tek tablolar ve onlara özel ayarlar
# -----------------------------------------------------------------------------
config = {
    # a) CLIENT ---------------------------------------------------------------
    "client": {
        "base_url": BASE_URL,
        "headers": HEADERS,
    },

    # b) RESOURCE_DEFAULTS -----------------------------------------------------
    # Buraya yazdığımız her şey aşağıdaki TÜM resource'lar için geçerli olur,
    # meğer ki bir resource aynı ayarı kendi içinde tekrar yazıp EZSİN
    # (aşağıda referans tablolarda write_disposition'ı böyle eziyoruz).
    # Aynı şeyi beş kez yazmamak için varsayılanları burada topluyoruz.
    "resource_defaults": {
        # "append": her çalıştırmada yeni satırları EKLE, eskileri silme.
        # Böylece zaman içinde bir geçmiş birikir (dün saat 10'da istasyonda kaç
        # bisiklet vardı? sorusunu cevaplayabiliriz).
        #   - "replace" olsaydı: her seferinde tablo silinip baştan yazılırdı.
        #   - "merge" olsaydı: aynı anahtarlı satır güncellenir, geçmiş kaybolurdu.
        "write_disposition": "append",

        "endpoint": {
            # GBFS'te sayfalama YOK: tek istekte bütün liste gelir.
            # Bunu söylemezsek dlt sayfalama türünü tahmin etmeye çalışır.
            "paginator": "single_page",
        },

        # Her satıra zaman damgası fonksiyonunu uygula (yukarıdaki 2. blok).
        "processing_steps": [{"map": add_fetched_at}],
    },

    # c) RESOURCES ------------------------------------------------------------
    # Her eleman = bir HTTP isteği = veritabanında bir tablo.
    "resources": [
        # ---- SNAPSHOT tabloları: varsayılan "append" geçerli ----------------
        {
            # "name" tablonun adı olur.
            "name": "station_status",
            "endpoint": {
                # İstek adresi: BASE_URL + path
                "path": "station_status.json",
                # JSON'un içinde satır listesinin yolu.
                # Elle yazsaydık: r.json()["data"]["stations"]
                "data_selector": "data.stations",
            },
        },
        {
            "name": "vehicle_status",
            "endpoint": {
                "path": "vehicle_status.json",
                # Burada liste "stations" değil "vehicles" anahtarının altında.
                # Bunu feed'i tarayıcıda açıp kendimiz keşfettik.
                "data_selector": "data.vehicles",
            },
        },

        # ---- REFERANS tabloları: "replace" ile varsayılanı eziyoruz ----------
        # Neden? Bu veriler neredeyse hiç değişmez. "append" kalsaydı pipeline
        # her çalıştığında her istasyon bir kez daha yazılırdı (100 çalıştırma =
        # her istasyondan 100 kopya). Sonra station_status ile join yapınca
        # satırlar 100'e katlanırdı.
        #
        # Sonraki öğrenme adımı: "replace" yerine
        #   "write_disposition": "merge", "primary_key": "station_id"
        # kullanmak. merge, aynı anahtarlı satırı günceller, yenisini ekler.
        # Değişikliklerin geçmişini de saklamak isterseniz dlt'nin
        # merge + "scd2" stratejisine bakın.
        {
            "name": "station_information",
            "write_disposition": "replace",
            "endpoint": {
                "path": "station_information.json",
                "data_selector": "data.stations",
            },
        },
        {
            "name": "system_pricing_plans",
            "write_disposition": "replace",
            "endpoint": {
                "path": "system_pricing_plans.json",
                "data_selector": "data.plans",
            },
        },
        {
            "name": "vehicle_types",
            "write_disposition": "replace",
            "endpoint": {
                "path": "vehicle_types.json",
                "data_selector": "data.vehicle_types",
            },
        },
    ],
}


# -----------------------------------------------------------------------------
# 4) PIPELINE TANIMI
#
# Pipeline = "kaynaktan hedefe giden boru". Üç isim veriyoruz:
#   - pipeline_name : dlt'nin bu pipeline'ın durumunu sakladığı klasörün adı
#                     (kullanıcı klasöründe ~/.dlt/pipelines/donkey).
#   - destination   : verinin yazılacağı yer. "duckdb" -> proje klasöründe
#                     donkey.duckdb adlı tek bir veritabanı dosyası oluşur.
#                     BigQuery'ye geçmek için "bigquery" yazmanız ve
#                     .dlt/secrets.toml'a kimlik bilgisi eklemeniz yeterli.
#   - dataset_name  : veritabanındaki şema adı. Tablolar donkey_raw.station_status
#                     gibi oluşur. "raw" = henüz dönüştürülmemiş ham veri.
# -----------------------------------------------------------------------------
pipeline = dlt.pipeline(
    pipeline_name="donkey",
    destination="duckdb",
    dataset_name="donkey_raw",
)


# -----------------------------------------------------------------------------
# 5) ÇALIŞTIRMA
#
# `if __name__ == "__main__":` -> bu blok yalnızca dosya doğrudan çalıştırıldığında
# (python donkey_pipeline.py) çalışır, başka bir dosyadan import edildiğinde çalışmaz.
#
# pipeline.run(...) arka planda üç adım yapar:
#   1. EXTRACT   : config'e göre her resource için bir istek atar, satırları toplar.
#   2. NORMALIZE : JSON'dan tablo şeması çıkarır. İç içe listeleri alt tablolara böler.
#                  Örn. station_status içindeki "vehicle_types_available" listesi
#                  station_status__vehicle_types_available adlı ayrı bir tabloya gider.
#                  İki tablo _dlt_id / _dlt_parent_id sütunlarıyla birbirine bağlanır.
#                  DİKKAT: alt tablolarda fetched_at YOK; ona ulaşmak için
#                  alt._dlt_parent_id = üst._dlt_id ile üst tabloya join yapılır.
#                  Benzer şekilde GBFS 3.0'da istasyon adı bir dil listesidir
#                  ([{"text": ..., "language": "nl"}]), bu yüzden adlar
#                  station_information__name tablosuna düşer.
#
#                  Analiz notu: GBFS 3.0'da vehicle_id gizlilik için periyodik
#                  olarak değişir; aynı bisikleti günler boyunca takip edemezsiniz.
#   3. LOAD      : tabloları oluşturur ve satırları DuckDB'ye yazar.
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    source = rest_api_source(config)
    load_info = pipeline.run(source)

    # Yükleme özeti: hangi hedefe, kaç paket, hata var mı?
    print(load_info)

    # Normalize adımının özeti: hangi tabloya kaç satır yazıldı?
    print(pipeline.last_trace.last_normalize_info)
