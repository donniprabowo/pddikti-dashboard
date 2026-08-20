import sys
import logging
import db_manager
from harvester import harvest_yogyakarta, harvest_indonesia, enrich_all_pts, print_db_status, cek_total_pt_indonesia, enrich_all_prodis

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    while True:
        print("\n================================================================================")
        print("🚀 SISTEM INTEGRASI DATABASE PDDIKTI - NUSANTARA & D.I. YOGYAKARTA")
        print("================================================================================")
        print("Pilihan Menu Utama:")
        print("  1) ⚡ Uji Coba Cepat (Harvest 3 Kampus Teratas & 5 Prodi per Kampus)")
        print("  2) 📍 Panen Massal Tingkat PROVINSI: Khusus D.I. YOGYAKARTA (~193 Kampus)")
        print("  3) 🇮🇩 Panen Massal Tingkat NASIONAL: SELURUH INDONESIA! (38 Provinsi / ~4,500+ Kampus)")
        print("      🚀 Dilengkapi ULTRA-FAST INSTANT RESUME (Stempel Tuntas 100% Akurat):")
        print("         Melompati ribuan kampus yang sudah tuntas SECEPAT KILAT tanpa request internet!")
        print("  4) 🏛️ Lengkapi Profil Detail Seluruh Kampus di DB (Alamat, Website, Akreditasi, Koordinat Peta GIS)")
        print("  5) 🌐 Cek Total Perguruan Tinggi se-Indonesia (Live dari Server PDDIKTI)")
        print("  6) 📊 Lihat Statistik & Status Database SQLite Lokal ('pddikti.db')")
        print("  7) 🎓 Lengkapi Profil Detail Seluruh Prodi (Status, Tgl Berdiri, Auto-Deteksi Tahun Tutup)")
        print("  8) ❌ Keluar / Exit")
        print("================================================================================")
        
        try:
            pilihan = input("👉 Masukkan nomor pilihan Anda [1-8]: ").strip()
            
            if pilihan == "1":
                print("\n▶️ MENJALANKAN MENU 1: Uji Coba Cepat (3 Kampus)...")
                harvest_yogyakarta(max_kampus=3, max_prodi_per_kampus=5, start_semester_filter="2019/2020")
            elif pilihan == "2":
                print("\n▶️ MENJALANKAN MENU 2: Panen Massal Khusus D.I. Yogyakarta...")
                print("🚀 Fitur ULTRA-FAST RESUME AKTIF (Anti-Duplikasi & Auto-Lanjut Kilat).")
                konfirmasi = input("\n   Apakah Anda yakin ingin memulai panen DIY sekarang? (y/n) [Default: y]: ").strip().lower()
                if konfirmasi in ["", "y", "yes"]:
                    harvest_yogyakarta(max_kampus=None, max_prodi_per_kampus=None, start_semester_filter="2019/2020")
                else:
                    print("   Dibatalkan.")
            elif pilihan == "3":
                print("\n▶️ MENJALANKAN MENU 3: Panen Massal Nusantara (SELURUH INDONESIA)...")
                print("🚀 Fitur ULTRA-FAST INSTANT RESUME AKTIF:")
                print("   Sistem dibekali stempel penuntasan mutlak 100% akurat. Saat dijalankan ulang usai")
                print("   terputus, kampus yang sudah tuntas dipindai akan dilintasi SECEPAT KILAT (0 ms)")
                print("   langsung dari memori tanpa menunggu koneksi internet!")
                konfirmasi = input("\n   🇮🇩 Siap memulai penelusuran se-Indonesia sekarang? (y/n) [Default: y]: ").strip().lower()
                if konfirmasi in ["", "y", "yes"]:
                    harvest_indonesia(max_kampus=None, max_prodi_per_kampus=None, start_semester_filter="2019/2020")
                else:
                    print("   Dibatalkan.")
            elif pilihan == "4":
                print("\n▶️ MENJALANKAN MENU 4: Melengkapi Profil Detail Kampus...")
                print("   Proses ini akan mengunduh koordinat lintang/bujur, akreditasi resmi, website, dll.")
                enrich_all_pts(force_update=False)
            elif pilihan == "5":
                print("\n▶️ MENJALANKAN MENU 5: Cek Total Populasi Kampus Nasional...")
                cek_total_pt_indonesia()
            elif pilihan == "6":
                print_db_status()
            elif pilihan == "7":
                print("\n▶️ MENJALANKAN MENU 7: Melengkapi Profil Detail Program Studi...")
                print("   Proses ini akan mengunduh tgl_berdiri, status, akreditasi, dan auto-deteksi tahun prodi tutup.")
                enrich_all_prodis(force_update=False)
            elif pilihan == "8" or pilihan.lower() in ["exit", "quit", "q"]:
                print("🙏 Terima kasih! Database Anda tersimpan aman di 'pddikti.db'. Sampai jumpa!")
                break
            else:
                print("❌ Pilihan tidak valid, silakan ketik angka 1 hingga 8.")
                
        except KeyboardInterrupt:
            print("\n\n⏹️ Dihentikan oleh user (Ctrl+C). Keluar...")
            break
        except Exception as e:
            print(f"\n❌ Terjadi kesalahan: {e}")

if __name__ == "__main__":
    main()