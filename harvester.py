import time
import logging
import json
from pddiktipy import api
from config import CF_CLEARANCE, USER_AGENT
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib
import cf_bypass
import db_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

PROVINSI_INDONESIA = [
    "Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Jambi", "Sumatera Selatan", "Bengkulu", 
    "Lampung", "Kepulauan Bangka Belitung", "Kepulauan Riau", "DKI Jakarta", "Jawa Barat", 
    "Jawa Tengah", "DI Yogyakarta", "Jawa Timur", "Banten", "Bali", "Nusa Tenggara Barat", 
    "Nusa Tenggara Timur", "Kalimantan Barat", "Kalimantan Tengah", "Kalimantan Selatan", 
    "Kalimantan Timur", "Kalimantan Utara", "Sulawesi Utara", "Sulawesi Tengah", "Sulawesi Selatan", 
    "Sulawesi Tenggara", "Gorontalo", "Sulawesi Barat", "Maluku", "Maluku Utara", "Papua", 
    "Papua Barat", "Papua Tengah", "Papua Pegunungan", "Papua Selatan", "Papua Barat Daya",
    "Universitas", "Institut", "Politeknik", "Sekolah Tinggi", "Akademi", "STIE", "STMIK", "STIKES", "UIN", "IAIN", "Poltekkes"
]

def enrich_all_pts(force_update=False):
    db_manager.init_db()
    
    target_pts = db_manager.get_pts_for_enrichment(force_update=force_update)
    all_pts = db_manager.get_saved_pts()
    
    print(f"\n================================================================================")
    print(f"🏛️ PEMUTAKHIRAN DETAIL PROFIL KAMPUS SE-INDONESIA")
    print(f"================================================================================")
    print(f"   • Total Kampus di DB   : {len(all_pts)} perguruan tinggi")
    print(f"   • Target Diperbarui     : {len(target_pts)} kampus yang belum lengkap / butuh update\n")
    
    if not target_pts:
        print("🎉 Selamat! Seluruh kampus di database Anda sudah lengkap atribut profilnya!")
        return

    print("⏳ Menyiapkan klien PDDIKTI untuk mendownload profil detail...")
    try:
        client = api(cf_clearance=CF_CLEARANCE, user_agent=USER_AGENT)
        with client as pddikti:
            berhasil = 0
            gagal = 0
            
            for idx, pt in enumerate(target_pts, 1):
                id_pt   = pt["id_pt"]
                kode_pt = pt["kode_pt"]
                nama_pt = pt["nama_pt"]
                
                print(f"   [{idx}/{len(target_pts)}] 🏛️ {nama_pt[:35]:<35} (Kode: {kode_pt})...", end=" ", flush=True)
                detail = pddikti.get_detail_pt(id_pt)
                
                data_detail = None
                if detail and isinstance(detail, dict) and "data" in detail:
                    data_detail = detail["data"]
                elif isinstance(detail, dict):
                    data_detail = detail
                
                if data_detail:
                    db_manager.update_pt_detail(id_pt, data_detail)
                    akred = str(data_detail.get("akreditasi_pt") or data_detail.get("akreditasi") or "-").strip()
                    lat   = str(data_detail.get("lintang_pt", "")).strip()
                    lon   = str(data_detail.get("bujur_pt", "")).strip()
                    koord = f"📍 ({lat}, {lon})" if lat and lon and lat != "None" else "📍 (Tanpa Koord)"
                    print(f"✅ [Akred: {akred:<3} | {koord}]", flush=True)
                    berhasil += 1
                else:
                    print("⚠️ (Detail belum tersedia)", flush=True)
                    gagal += 1
                time.sleep(0.25)

            print(f"\n🏆 PROSES PENGKAYAAN DETAIL SELESAI! (+{berhasil} diperbarui, {gagal} dilewati)")
            print_db_status()

    except Exception as e:
        logger.error(f"Error saat pengkayaan profil PT: {e}", exc_info=True)
        print(f"\n❌ Terjadi kendala saat melengkapi detail: {e}")
        print_db_status()

def harvest_indonesia(max_kampus=None, max_prodi_per_kampus=None, start_semester_filter="2019/2020"):
    """
    Menyapu dan mengunduh seluruh data Perguruan Tinggi se-Indonesia dengan
    teknologi Ultra-Fast Zero-Network Instant Resume & Stempel Keamanan 100% Akurat.
    """
    db_manager.init_db()
    print("⏳ Menyiapkan klien PDDIKTI (Mode Ultra-Fast Instant Resume Aktif)...")
    
    try:
        client = api(cf_clearance=CF_CLEARANCE, user_agent=USER_AGENT)
        
        with client as pddikti:
            kampus_terkumpul = {}
            saved_pts = db_manager.get_saved_pts()
            for spt in saved_pts:
                kampus_terkumpul[spt["kode_pt"]] = spt

            jalankan_tahap_1 = True
            if len(saved_pts) >= 500 and max_kampus is None:
                print(f"\n📦 Terdeteksi ada {len(saved_pts):,} Perguruan Tinggi sudah terdaftar di database SQLite Anda!")
                pilihan_skip = input("👉 Lewati (SKIP) pencarian nama 38 Provinsi di awal dan LANGSUNG TERUSKAN unduh prodi? (y/n) [Default: y]: ").strip().lower()
                if pilihan_skip in ["", "y", "yes"]:
                    jalankan_tahap_1 = False
                    print("⚡ Tahap 1 dilewati! Langsung melompat ke pemutakhiran Program Studi & Student Body...\n")
                else:
                    print("▶️ Tetap menjalankan Tahap 1 (Pemindaian ulang wilayah)...\n")

            if jalankan_tahap_1:
                print(f"\n🇮🇩 [TAHAP 1] Sapuan Nusantara: Memindai Seluruh 38 Provinsi & Kategori PT se-Indonesia...")
                lokasi_api = pddikti.get_pt_locations()
                daftar_kata_kunci = list(PROVINSI_INDONESIA)
                
                if lokasi_api and isinstance(lokasi_api, dict) and "data" in lokasi_api:
                    for lok in lokasi_api["data"]:
                        nm = str(lok.get("nama_wilayah") or lok.get("nama") or "").strip()
                        if nm and nm not in daftar_kata_kunci:
                            daftar_kata_kunci.append(nm)
                            
                print(f"   Total {len(daftar_kata_kunci)} titik sapuan kata kunci nasional disiapkan.\n")
                
                for idx_kw, kw in enumerate(daftar_kata_kunci, 1):
                    print(f"   [{idx_kw}/{len(daftar_kata_kunci)}] 🔎 Memindai Nusantara untuk: '{kw}'...", end=" ", flush=True)
                    hasil = pddikti.search_pt(kw)
                    
                    if not hasil:
                        print("⚠️ (0 hasil / Timeout, menerus...)", flush=True)
                        continue
                    
                    if isinstance(hasil, dict) and hasil.get("error"):
                        print(f"❌ Error Server: {hasil.get('error')}", flush=True)
                        continue

                    daftar_raw = []
                    if isinstance(hasil, dict) and "data" in hasil:
                        daftar_raw = hasil["data"]
                    elif isinstance(hasil, list):
                        daftar_raw = hasil
                        
                    if not daftar_raw:
                        print("⚠️ (0 kampus ditemukan)", flush=True)
                        continue
                    
                    count_baru = 0
                    for pt in daftar_raw:
                        kode = str(pt.get("kode_pt") or pt.get("kode") or "").strip()
                        id_pt = pt.get("id_pt") or pt.get("id") or pt.get("id_sp")
                        nama = str(pt.get("nama_pt") or pt.get("nama") or pt.get("nama_singkat") or "Unknown").strip()
                        
                        if id_pt and kode:
                            if kode not in kampus_terkumpul:
                                count_baru += 1
                            kampus_terkumpul[kode] = {"id_pt": id_pt, "kode_pt": kode, "nama_pt": nama, "status_tuntas": 0}
                            db_manager.save_pt(id_pt, kode, nama)
                            
                    print(f"✅ Ditemukan {len(daftar_raw):<3} (+{count_baru:<3} baru) | Total DB: {len(kampus_terkumpul):,}", flush=True)
                    time.sleep(0.3)
                
            daftar_pt = list(kampus_terkumpul.values())
            print(f"\n✅ Daftar target siap: {len(daftar_pt):,} Perguruan Tinggi se-Indonesia!")
            
            if not daftar_pt:
                print("\n🚨 PERINGATAN: Belum ada kampus teraktif. Periksa token CF_CLEARANCE Anda di config.py!")
                return
            
            if max_kampus is not None:
                daftar_pt = daftar_pt[:max_kampus]

            # 2. EKSTRAKSI DENGAN ULTRA-FAST ZERO-NETWORK INSTANT RESUME
            print(f"\n🎓 [TAHAP 2 & 3] Akuisi Prodi & Riwayat Student Body (ULTRA-FAST RESUME AKTIF)...")
            total_prodi_diproses = 0
            skipped_campus_count = 0
            
            for idx_pt, pt in enumerate(daftar_pt, 1):
                id_pt   = pt["id_pt"]
                kode_pt = pt["kode_pt"]
                nama_pt = str(pt["nama_pt"]).strip()
                
                if pt.get("status_tuntas") == 1 or db_manager.is_pt_tuntas(id_pt):
                    skipped_campus_count += 1
                    print(f"   [{idx_pt:,}/{len(daftar_pt):,}] ⏭️ [Tuntas di DB]: {nama_pt[:45]:<45} (Lompat 0 ms)", flush=True)
                    continue
                
                if skipped_campus_count > 0:
                    print(f"\n⚡ Berhasil melintasi {skipped_campus_count:,} kampus yang sudah tuntas secepat kilat!")
                    skipped_campus_count = 0

                print(f"\n   [{idx_pt:,}/{len(daftar_pt):,}] 🏛️ {nama_pt} (Kode: {kode_pt})")
                
                # Coba unduh prodi dengan parameter 20241
                data_prodi = pddikti.get_prodi_pt(id_pt, "20241")
                list_prodi = []
                if data_prodi and isinstance(data_prodi, dict) and "data" in data_prodi:
                    list_prodi = data_prodi["data"]
                elif isinstance(data_prodi, list):
                    list_prodi = data_prodi
                
                # Jika 20241 kosong/none (sering pada politeknik atau kampus keagamaan tertentu), coba tanpa parameter semester
                if not list_prodi:
                    data_prodi = pddikti.get_prodi_pt(id_pt, "")
                    if data_prodi and isinstance(data_prodi, dict) and "data" in data_prodi:
                        list_prodi = data_prodi["data"]
                    elif isinstance(data_prodi, list):
                        list_prodi = data_prodi

                if max_prodi_per_kampus is not None:
                    list_prodi = list_prodi[:max_prodi_per_kampus]

                # PERBAIKAN BUG KRITIS: Jika list_prodi tetap kosong akibat rate limit Cloudflare atau jaringan putus,
                # JANGAN MENANDAI SEBAGAI TUNTAS! (Biarkan status_tuntas = 0 agar dicoba kembali di run berikutnya)
                if not list_prodi:
                    print(f"       ⚠️ (Daftar prodi kosong/gagal dari server, dilewati SEMENTARA tanpa stempel tuntas agar bisa dicoba ulang nanti)")
                    continue

                skipped_prodi = 0
                fetched_prodi = 0

                for pr in list_prodi:
                    id_prodi   = pr.get("id_sms") or pr.get("id_prodi") or pr.get("id")
                    kode_prodi = str(pr.get("kode_prodi", "-")).strip()
                    nama_prodi = str(pr.get("nama_prodi", "Unknown")).strip()
                    jenjang    = str(pr.get("jenjang_prodi") or pr.get("jenjang", "")).strip()
                    akreditasi = str(pr.get("akreditasi", "-")).strip()
                    
                    if id_prodi:
                        db_manager.save_prodi(id_prodi, id_pt, kode_prodi, nama_prodi, jenjang, akreditasi)
                        total_prodi_diproses += 1

                        if db_manager.is_prodi_harvested(id_prodi):
                            skipped_prodi += 1
                            continue
                        
                        fetched_prodi += 1
                        if fetched_prodi == 1:
                            print(f"       📥 Mengunduh riwayat prodi baru", end="", flush=True)

                        riwayat = pddikti.get_num_students_lecturers_prodi(id_prodi)
                        if riwayat and isinstance(riwayat, dict) and "data" in riwayat:
                            for row in riwayat["data"]:
                                sem = str(row.get("semester") or row.get("id_semester") or "-").strip()
                                if start_semester_filter in sem or str(sem) >= start_semester_filter or "202" in sem:
                                    sb = row.get("jumlah_mahasiswa") or row.get("mahasiswa") or 0
                                    jd = row.get("jumlah_dosen") or row.get("dosen") or 0
                                    db_manager.save_riwayat_student_body(id_prodi, sem, sb, jd)
                        
                        print(".", end="", flush=True)
                        time.sleep(0.25)
                        
                if skipped_prodi > 0:
                    print(f"       ⏭️ [Smart Resume: {skipped_prodi} prodi dilewati karena ada di DB]", end="")
                if fetched_prodi > 0:
                    print(" Selesai!", end="")
                print()
                
                # STEMPEL KEAMANAN MULTAK: Karena prodi berhasil diunduh dan diputar sampai akhir, kunci di DB
                db_manager.mark_pt_as_tuntas(id_pt)
                print(f"       🔐 Stempel Tuntas 100% dikunci di DB untuk kampus ini.")

            print("\n🇮🇩🎉 PANEN MASSAL SE-INDONESIA SELESAI TANPA DUPLIKASI!")
            print_db_status()

    except Exception as e:
        logger.error(f"Terjadi kesalahan saat harvesting nasional: {e}", exc_info=True)
        print(f"\n❌ Terjadi pemutusan/kesalahan saat harvesting: {e}")
        print("\n🛡️ JANGAN KHAWATIR! Fitur ULTRA-FAST RESUME telah mengamankan progres Nusantara Anda.")
        print_db_status()

def harvest_yogyakarta(max_kampus=None, max_prodi_per_kampus=None, start_semester_filter="2019/2020"):
    db_manager.init_db()
    print("⏳ Menyiapkan klien PDDIKTI (Mode Ultra-Fast Resume DIY Aktif)...")
    try:
        client = api(cf_clearance=CF_CLEARANCE, user_agent=USER_AGENT)
        with client as pddikti:
            wilayah_diy = ["Yogyakarta", "Sleman", "Bantul", "Kulon Progo", "Gunungkidul", "D.I. Yogyakarta"]
            kampus_terkumpul = {}
            saved_pts = db_manager.get_saved_pts()
            for spt in saved_pts:
                kampus_terkumpul[spt["kode_pt"]] = spt

            print(f"\n📍 [TAHAP 1] Menyapu & Memvalidasi Daftar Perguruan Tinggi se-D.I. Yogyakarta...")
            for kw in wilayah_diy:
                print(f"   🔎 Pencarian area: '{kw}'...", end=" ", flush=True)
                hasil = pddikti.search_pt(kw)
                if not hasil:
                    print("⚠️ (0 hasil / Timeout, meneruskan...)", flush=True)
                    continue
                if isinstance(hasil, dict) and hasil.get("error"):
                    print(f"❌ Error Server: {hasil.get('error')}", flush=True)
                    continue
                daftar_raw = []
                if isinstance(hasil, dict) and "data" in hasil:
                    daftar_raw = hasil["data"]
                elif isinstance(hasil, list):
                    daftar_raw = hasil
                if not daftar_raw:
                    print("⚠️ (0 kampus terdeteksi)", flush=True)
                    continue
                count_baru = 0
                for pt in daftar_raw:
                    kode = str(pt.get("kode_pt") or pt.get("kode") or "").strip()
                    id_pt = pt.get("id_pt") or pt.get("id") or pt.get("id_sp")
                    nama = str(pt.get("nama_pt") or pt.get("nama") or pt.get("nama_singkat") or "Unknown").strip()
                    if id_pt and kode:
                        if kode not in kampus_terkumpul:
                            count_baru += 1
                        kampus_terkumpul[kode] = {"id_pt": id_pt, "kode_pt": kode, "nama_pt": nama, "status_tuntas": 0}
                        db_manager.save_pt(id_pt, kode, nama)
                print(f"✅ Terdaftar {len(daftar_raw)} (+{count_baru} kampus baru di DB)", flush=True)
                time.sleep(0.3)
                
            daftar_pt = list(kampus_terkumpul.values())
            print(f"\n✅ TAHAP 1 SELESAI: Ada {len(daftar_pt)} Perguruan Tinggi di dalam database SQLite!")
            if not daftar_pt:
                return
            if max_kampus is not None:
                daftar_pt = daftar_pt[:max_kampus]

            print("\n🎓 [TAHAP 2 & 3] Mengakuisisi Program Studi & Riwayat Student Body DIY...")
            skipped_campus_count = 0
            
            for idx_pt, pt in enumerate(daftar_pt, 1):
                id_pt   = pt["id_pt"]
                kode_pt = pt["kode_pt"]
                nama_pt = str(pt["nama_pt"]).strip()
                
                if pt.get("status_tuntas") == 1 or db_manager.is_pt_tuntas(id_pt):
                    skipped_campus_count += 1
                    print(f"   [{idx_pt:,}/{len(daftar_pt):,}] ⏭️ [Tuntas di DB]: {nama_pt[:45]:<45} (Lompat 0 ms)", flush=True)
                    continue
                
                if skipped_campus_count > 0:
                    print(f"\n⚡ Berhasil melintasi {skipped_campus_count:,} kampus yang sudah tuntas secepat kilat!")
                    skipped_campus_count = 0

                print(f"\n   [{idx_pt}/{len(daftar_pt)}] 🏛️ {nama_pt} (Kode: {kode_pt})")
                data_prodi = pddikti.get_prodi_pt(id_pt, "20241")
                list_prodi = []
                if data_prodi and isinstance(data_prodi, dict) and "data" in data_prodi:
                    list_prodi = data_prodi["data"]
                elif isinstance(data_prodi, list):
                    list_prodi = data_prodi
                
                if not list_prodi:
                    data_prodi = pddikti.get_prodi_pt(id_pt, "")
                    if data_prodi and isinstance(data_prodi, dict) and "data" in data_prodi:
                        list_prodi = data_prodi["data"]
                    elif isinstance(data_prodi, list):
                        list_prodi = data_prodi

                if max_prodi_per_kampus is not None:
                    list_prodi = list_prodi[:max_prodi_per_kampus]

                # PERBAIKAN BUG KRITIS: Jangan beri stempel tuntas jika prodi kosong/gagal loading
                if not list_prodi:
                    print(f"       ⚠️ (Daftar prodi kosong/gagal dari server, dilewati SEMENTARA tanpa stempel tuntas)")
                    continue

                skipped_prodi = 0
                fetched_prodi = 0
                for pr in list_prodi:
                    id_prodi   = pr.get("id_sms") or pr.get("id_prodi") or pr.get("id")
                    kode_prodi = str(pr.get("kode_prodi", "-")).strip()
                    nama_prodi = str(pr.get("nama_prodi", "Unknown")).strip()
                    jenjang    = str(pr.get("jenjang_prodi") or pr.get("jenjang", "")).strip()
                    akreditasi = str(pr.get("akreditasi", "-")).strip()
                    if id_prodi:
                        db_manager.save_prodi(id_prodi, id_pt, kode_prodi, nama_prodi, jenjang, akreditasi)
                        if db_manager.is_prodi_harvested(id_prodi):
                            skipped_prodi += 1
                            continue
                        fetched_prodi += 1
                        if fetched_prodi == 1:
                            print(f"       📥 Mengunduh riwayat baru untuk prodi", end="", flush=True)
                        riwayat = pddikti.get_num_students_lecturers_prodi(id_prodi)
                        if riwayat and isinstance(riwayat, dict) and "data" in riwayat:
                            for row in riwayat["data"]:
                                sem = str(row.get("semester") or row.get("id_semester") or "-").strip()
                                if start_semester_filter in sem or str(sem) >= start_semester_filter or "202" in sem:
                                    sb = row.get("jumlah_mahasiswa") or row.get("mahasiswa") or 0
                                    jd = row.get("jumlah_dosen") or row.get("dosen") or 0
                                    db_manager.save_riwayat_student_body(id_prodi, sem, sb, jd)
                        print(".", end="", flush=True)
                        time.sleep(0.25)
                if skipped_prodi > 0:
                    print(f"       ⏭️ [Smart Resume: {skipped_prodi} prodi dilompati karena ada di DB]", end="")
                if fetched_prodi > 0:
                    print(" Selesai!", end="")
                print()
                db_manager.mark_pt_as_tuntas(id_pt)

            print("\n🎉 PANEN DATA DIY SELESAI TOTAL TANPA DUPLIKASI!")
            print_db_status()

    except Exception as e:
        logger.error(f"Terjadi kesalahan saat harvesting DIY: {e}", exc_info=True)
        print(f"\n❌ Terjadi pemutusan/kesalahan saat harvesting: {e}")
        print_db_status()

def cek_total_pt_indonesia():
    """Mengambil informasi total keseluruhan perguruan tinggi di Indonesia langsung dari server PDDIKTI."""
    print("\n⏳ Menghubungi server PDDIKTI untuk mengambil total populasi Perguruan Tinggi...")
    try:
        client = api(cf_clearance=CF_CLEARANCE, user_agent=USER_AGENT)
        with client as pddikti:
            hasil = pddikti.get_pt_locations()
            if hasil and isinstance(hasil, dict) and "data" in hasil:
                total = len(hasil["data"])
                print(f"🎉 SUKSES! Menurut data real-time pemetaan (GIS) PDDIKTI saat ini:")
                print(f"   => Terdapat {total:,} Perguruan Tinggi yang terdaftar aktif di seluruh Indonesia!")
            else:
                print("⚠️ Gagal mengambil total data (Server mengembalikan hasil kosong/None).")
                print("   [TIPS] Kemungkinan token CF_CLEARANCE Anda sudah kedaluwarsa. Silakan perbarui di config.py!")
    except Exception as e:
        logger.error(f"Error saat mengecek total PT: {e}", exc_info=True)
        print(f"❌ Terjadi kesalahan saat menghubungi API: {e}")

cf_lock = threading.Lock()

def process_prodi(pr, target_idx, total_target):
    import config
    importlib.reload(config)
    
    id_prodi = pr['id_prodi']
    nama_prodi = pr['nama_prodi']
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            importlib.reload(config)
            old_cf = config.CF_CLEARANCE
            client = api(cf_clearance=config.CF_CLEARANCE, user_agent=config.USER_AGENT)
            with client as pddikti:
                detail_resp = pddikti.get_detail_prodi(id_prodi)
                
                if not detail_resp or not isinstance(detail_resp, dict) or "data" not in detail_resp:
                    raise Exception("Kemungkinan Terblokir Cloudflare (Respon Invalid)")
                
                d = detail_resp["data"]
                
                detail_data = {
                    "status": d.get("status", "-"),
                    "kel_bidang": d.get("kel_bidang", "-"),
                    "tgl_berdiri": d.get("tgl_berdiri", "-"),
                    "sk_selenggara": d.get("sk_selenggara", "-"),
                    "tgl_sk_selenggara": d.get("tgl_sk_selenggara", "-"),
                    "alamat_prodi": d.get("alamat", "-"),
                    "website_prodi": d.get("website", "-"),
                    "email_prodi": d.get("email", "-"),
                    "no_tel_prodi": d.get("no_tel", "-"),
                    "lintang_prodi": d.get("lintang", "-"),
                    "bujur_prodi": d.get("bujur", "-"),
                    "akreditasi_prodi": d.get("akreditasi", "-"),
                    "tgl_tutup_estimasi": "-"
                }
                
                status_prodi = str(detail_data["status"]).strip().title()
                if status_prodi in ["Tutup", "Alih Bentuk", "Pembinaan", "Hapus"]:
                    estimasi = db_manager.get_last_reported_year(id_prodi)
                    detail_data["tgl_tutup_estimasi"] = estimasi
                
                db_manager.update_prodi_detail(id_prodi, detail_data)
                print(f"[{target_idx:,}/{total_target:,}] 🎓 Selesai: {nama_prodi[:40]}")
                return
                
        except Exception as e:
            print(f"⚠️ [{target_idx}] Error untuk {nama_prodi[:30]}: {str(e)[:30]}. Meminta Bypass...")
            with cf_lock:
                importlib.reload(config)
                current_cf = config.CF_CLEARANCE
                if current_cf == old_cf:
                    print("🛑 Memulai Auto-Bypass DrissionPage...")
                    new_cf = cf_bypass.get_fresh_clearance()
                    if new_cf:
                        print("✅ Bypass Sukses. Melanjutkan seluruh antrean...")
                        time.sleep(2)
                    else:
                        print("❌ Gagal Bypass. Menunggu 10 detik lalu coba lagi...")
                        time.sleep(10)
                else:
                    # Token sudah diupdate oleh thread lain yang duluan masuk lock
                    pass
            time.sleep(1) # Beri jeda sebelum retry
            
    # Gagal permanen setelah max_retries
    db_manager.update_prodi_detail(id_prodi, {"status": "-"})
    print(f"❌ [{target_idx}] Gagal Ekstraksi secara permanen: {nama_prodi}")

def enrich_all_prodis(force_update=False):
    """Menyisir seluruh prodi di DB dengan Multi-Threading dan Auto-Bypass CF."""
    print(f"\n🔍 Memulai Ekstraksi Multi-Threading (Max 5 Workers)... (Smart Resume: {'OFF' if force_update else 'ON'})")
    
    target_prodis = db_manager.get_prodis_for_enrichment(force_update=force_update)
    total_target = len(target_prodis)
    
    if total_target == 0:
        print("🎉 WOW! Seluruh profil Program Studi di database sudah terisi lengkap 100%. Tidak ada yang perlu diunduh.")
        return
        
    print(f"📊 Menemukan {total_target:,} Program Studi yang belum memiliki detail lengkap.")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for idx, pr in enumerate(target_prodis, 1):
            futures.append(executor.submit(process_prodi, pr, idx, total_target))
            
        for future in as_completed(futures):
            future.result()

def print_db_status():
    pt_c, pr_c, r_c, en_c, tu_c = db_manager.get_stats()
    print("\n================================================================================")
    print("📊 STATUS CURRENT DATABASE SQLITE LOKAL ('pddikti.db'):")
    print("================================================================================")
    print(f"   • Total Perguruan Tinggi (Kampus) : {pt_c:,} unit ({tu_c:,} tuntas prodi, {en_c:,} lengkap detail)")
    print(f"   • Total Program Studi (Prodi)     : {pr_c:,} prodi")
    print(f"   • Total Record Riwayat Semester   : {r_c:,} baris student body")
    print("================================================================================")

if __name__ == "__main__":
    harvest_yogyakarta()
