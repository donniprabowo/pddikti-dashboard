import sqlite3
import logging

logger = logging.getLogger(__name__)

DB_PATH = "pddikti.db"

DETAIL_PT_COLUMNS = [
    ("nm_singkat", "TEXT"),
    ("jalan", "TEXT"),
    ("rt", "TEXT"),
    ("rw", "TEXT"),
    ("dusun", "TEXT"),
    ("kelurahan", "TEXT"),
    ("kode_pos", "TEXT"),
    ("lintang_pt", "TEXT"),
    ("bujur_pt", "TEXT"),
    ("telepon", "TEXT"),
    ("faximile", "TEXT"),
    ("email", "TEXT"),
    ("website", "TEXT"),
    ("alamat", "TEXT"),
    ("akreditasi_pt", "TEXT")
]

DETAIL_PRODI_COLUMNS = [
    ("status", "TEXT"),
    ("kel_bidang", "TEXT"),
    ("tgl_berdiri", "TEXT"),
    ("sk_selenggara", "TEXT"),
    ("tgl_sk_selenggara", "TEXT"),
    ("alamat_prodi", "TEXT"),
    ("website_prodi", "TEXT"),
    ("email_prodi", "TEXT"),
    ("no_tel_prodi", "TEXT"),
    ("lintang_prodi", "TEXT"),
    ("bujur_prodi", "TEXT"),
    ("akreditasi_prodi", "TEXT"),
    ("tgl_tutup_estimasi", "TEXT")
]

def get_connection():
    """Membuka koneksi ke database SQLite lokal."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inisialisasi, Migrasi, & Pembersihan (Healing) otomatis tabel di dalam database SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Tabel Perguruan Tinggi (Dasar)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS perguruan_tinggi (
        id_pt TEXT PRIMARY KEY,
        kode_pt TEXT UNIQUE,
        nama_pt TEXT,
        status_tuntas INTEGER DEFAULT 0
    );
    """)

    # MIGRASI OTOMATIS: Tambahkan kolom detail & status_tuntas jika belum ada di tabel existing
    cursor.execute("PRAGMA table_info(perguruan_tinggi);")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    
    if "status_tuntas" not in existing_cols:
        logger.info("Adding column 'status_tuntas' (INTEGER DEFAULT 0) for Ultra-Fast Instant Resume...")
        cursor.execute("ALTER TABLE perguruan_tinggi ADD COLUMN status_tuntas INTEGER DEFAULT 0;")
        
    for col_name, col_type in DETAIL_PT_COLUMNS:
        if col_name not in existing_cols:
            logger.info(f"Adding new column '{col_name}' ({col_type}) to table 'perguruan_tinggi'...")
            cursor.execute(f"ALTER TABLE perguruan_tinggi ADD COLUMN {col_name} {col_type};")

    # 2. Tabel Program Studi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS program_studi (
        id_prodi TEXT PRIMARY KEY,
        id_pt TEXT,
        kode_prodi TEXT,
        nama_prodi TEXT,
        jenjang TEXT,
        akreditasi TEXT,
        FOREIGN KEY (id_pt) REFERENCES perguruan_tinggi (id_pt)
    );
    """)

    # 3. Tabel Riwayat Student Body Per Semester
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS riwayat_student_body (
        id_prodi TEXT,
        semester TEXT,
        student_body INTEGER,
        jumlah_dosen INTEGER,
        PRIMARY KEY (id_prodi, semester),
        FOREIGN KEY (id_prodi) REFERENCES program_studi (id_prodi)
    );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prodi_pt ON program_studi (id_pt);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_riwayat_prodi ON riwayat_student_body (id_prodi);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_riwayat_semester ON riwayat_student_body (semester);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pt_tuntas ON perguruan_tinggi (status_tuntas);")

    # OTO-RECOVERY / AUTO-HEALING:
    # Smart Auto-Healing untuk kampus yang tersangkut karena API sebelumnya blank:
    cursor.execute("UPDATE perguruan_tinggi SET status_tuntas = 0 WHERE status_tuntas = 1 AND id_pt NOT IN (SELECT DISTINCT id_pt FROM program_studi);")
    healed_count = cursor.rowcount
    if healed_count > 0:
        print(f"\n🛠️ AUTO-HEALING DB: Berhasil memulihkan {healed_count} kampus kosong yang sempat lompat agar bisa diunduh ulang dengan benar!")
        
    # Add new columns to program_studi if they don't exist
    for col_name, col_type in DETAIL_PRODI_COLUMNS:
        try:
            cursor.execute(f"ALTER TABLE program_studi ADD COLUMN {col_name} {col_type};")
        except sqlite3.OperationalError:
            pass # Column exists

    conn.commit()
    conn.close()

def save_pt(id_pt, kode_pt, nama_pt):
    """Menyimpan atau memperbarui data Perguruan Tinggi dengan proteksi ganda."""
    conn = get_connection()
    cursor = conn.cursor()
    
    id_clean = str(id_pt).strip()
    kode_clean = str(kode_pt).strip()
    nama_clean = str(nama_pt).strip()

    cursor.execute("SELECT status_tuntas FROM perguruan_tinggi WHERE kode_pt = ? OR id_pt = ?", (kode_clean, id_clean))
    row = cursor.fetchone()
    if row:
        current_tuntas = row["status_tuntas"] or 0
        cursor.execute("""
        UPDATE perguruan_tinggi 
        SET id_pt = ?, kode_pt = ?, nama_pt = ?, status_tuntas = ?
        WHERE kode_pt = ? OR id_pt = ?;
        """, (id_clean, kode_clean, nama_clean, current_tuntas, kode_clean, id_clean))
    else:
        cursor.execute("""
        INSERT INTO perguruan_tinggi (id_pt, kode_pt, nama_pt, status_tuntas)
        VALUES (?, ?, ?, 0);
        """, (id_clean, kode_clean, nama_clean))

    conn.commit()
    conn.close()

def mark_pt_as_tuntas(id_pt):
    """Mengubah status_tuntas = 1 hanya untuk kampus yang memiliki data prodi valid & tuntas diunduh."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE perguruan_tinggi SET status_tuntas = 1 WHERE id_pt = ?;", (str(id_pt).strip(),))
    conn.commit()
    conn.close()

def is_pt_tuntas(id_pt):
    """Mengecek apakah kampus sudah distempel tuntas di DB."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status_tuntas FROM perguruan_tinggi WHERE id_pt = ? LIMIT 1;", (str(id_pt).strip(),))
    row = cursor.fetchone()
    conn.close()
    return row and row["status_tuntas"] == 1

def update_pt_detail(id_pt, detail_data):
    """Memperbarui row perguruan_tinggi dengan atribut detail dari get_detail_pt."""
    if not detail_data or not isinstance(detail_data, dict):
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    
    vals = []
    for col_name, _ in DETAIL_PT_COLUMNS:
        val = detail_data.get(col_name, "")
        val = str(val).strip() if val is not None else ""
        if val == "":
            val = "-"
        vals.append(val)
    
    vals.append(str(id_pt).strip())
    set_clause = ", ".join([f"{col} = ?" for col, _ in DETAIL_PT_COLUMNS])
    query = f"UPDATE perguruan_tinggi SET {set_clause} WHERE id_pt = ?;"
    
    cursor.execute(query, vals)
    conn.commit()
    conn.close()

def get_pts_for_enrichment(force_update=False):
    """Mengambil daftar kampus yang perlu dilengkapi profil detailnya."""
    conn = get_connection()
    cursor = conn.cursor()
    if force_update:
        cursor.execute("SELECT id_pt, kode_pt, nama_pt, alamat FROM perguruan_tinggi;")
    else:
        cursor.execute("SELECT id_pt, kode_pt, nama_pt, alamat FROM perguruan_tinggi WHERE alamat IS NULL OR alamat = '' OR alamat = '-' OR akreditasi_pt IS NULL OR akreditasi_pt = '' OR akreditasi_pt = '-';")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_prodis_for_enrichment(force_update=False):
    """Mengambil daftar prodi yang perlu dilengkapi profil detailnya."""
    conn = get_connection()
    cursor = conn.cursor()
    if force_update:
        cursor.execute("SELECT id_prodi, nama_prodi FROM program_studi;")
    else:
        cursor.execute("SELECT id_prodi, nama_prodi FROM program_studi WHERE status IS NULL OR status = '' OR status = '-';")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_last_reported_year(id_prodi):
    """Mencari tahun terakhir prodi melaporkan student body (mengabaikan laporan bernilai 0)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT semester FROM riwayat_student_body WHERE id_prodi = ? AND student_body > 0", (id_prodi,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "0000"
        
    years = []
    for r in rows:
        sem = r['semester']
        if sem and len(sem) >= 4 and sem[:4].isdigit():
            years.append(int(sem[:4]))
            
    if years:
        return str(max(years))
    return "0000"

def update_prodi_detail(id_prodi, detail_data):
    """Menyimpan detail ekstraks ke tabel program_studi."""
    conn = get_connection()
    cursor = conn.cursor()
    
    set_clause = ", ".join([f"{col} = ?" for col, _ in DETAIL_PRODI_COLUMNS])
    query = f"UPDATE program_studi SET {set_clause} WHERE id_prodi = ?;"
    
    vals = []
    for col_name, _ in DETAIL_PRODI_COLUMNS:
        val = detail_data.get(col_name, "")
        val = str(val).strip() if val is not None else ""
        if val == "":
            val = "-"
        vals.append(val)
    
    vals.append(str(id_prodi).strip())
    
    try:
        cursor.execute(query, tuple(vals))
        conn.commit()
    except Exception as e:
        logger.error(f"Gagal update detail prodi {id_prodi}: {e}", exc_info=True)
    finally:
        conn.close()

def save_prodi(id_prodi, id_pt, kode_prodi, nama_prodi, jenjang, akreditasi):
    """Menyimpan atau memperbarui data Program Studi secara aman."""
    conn = get_connection()
    cursor = conn.cursor()
    
    id_prodi_c = str(id_prodi).strip()
    id_pt_c = str(id_pt).strip()
    kode_prodi_c = str(kode_prodi).strip()
    nama_prodi_c = str(nama_prodi).strip()
    jenjang_c = str(jenjang).strip()
    akred_c = str(akreditasi).strip()

    cursor.execute("SELECT 1 FROM program_studi WHERE id_prodi = ?", (id_prodi_c,))
    if cursor.fetchone():
        cursor.execute("""
        UPDATE program_studi 
        SET id_pt = ?, kode_prodi = ?, nama_prodi = ?, jenjang = ?, akreditasi = ?
        WHERE id_prodi = ?;
        """, (id_pt_c, kode_prodi_c, nama_prodi_c, jenjang_c, akred_c, id_prodi_c))
    else:
        cursor.execute("""
        INSERT INTO program_studi (id_prodi, id_pt, kode_prodi, nama_prodi, jenjang, akreditasi)
        VALUES (?, ?, ?, ?, ?, ?);
        """, (id_prodi_c, id_pt_c, kode_prodi_c, nama_prodi_c, jenjang_c, akred_c))

    conn.commit()
    conn.close()

def save_riwayat_student_body(id_prodi, semester, student_body, jumlah_dosen):
    """Menyimpan atau memperbarui data riwayat Student Body tanpa duplikasi."""
    conn = get_connection()
    cursor = conn.cursor()
    
    id_prodi_c = str(id_prodi).strip()
    sem_c = str(semester).strip()
    
    try:
        sb = int(student_body) if student_body and str(student_body).isdigit() else 0
    except (ValueError, TypeError):
        sb = 0
    try:
        jd = int(jumlah_dosen) if jumlah_dosen and str(jumlah_dosen).isdigit() else 0
    except (ValueError, TypeError):
        jd = 0

    cursor.execute("SELECT 1 FROM riwayat_student_body WHERE id_prodi = ? AND semester = ?", (id_prodi_c, sem_c))
    if cursor.fetchone():
        cursor.execute("""
        UPDATE riwayat_student_body 
        SET student_body = ?, jumlah_dosen = ?
        WHERE id_prodi = ? AND semester = ?;
        """, (sb, jd, id_prodi_c, sem_c))
    else:
        cursor.execute("""
        INSERT INTO riwayat_student_body (id_prodi, semester, student_body, jumlah_dosen)
        VALUES (?, ?, ?, ?);
        """, (id_prodi_c, sem_c, sb, jd))

    conn.commit()
    conn.close()

def is_prodi_harvested(id_prodi):
    """SMART RESUME: Mengecek apakah prodi ini sudah pernah diambil riwayat student body-nya."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM riwayat_student_body WHERE id_prodi = ? LIMIT 1", (str(id_prodi).strip(),))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_saved_pts():
    """Mengambil daftar seluruh Perguruan Tinggi yang sudah ada di dalam database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_pt, kode_pt, nama_pt, status_tuntas FROM perguruan_tinggi")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    """Mengembalikan statistik jumlah record aktual di database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM perguruan_tinggi")
    pt_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM program_studi")
    prodi_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM riwayat_student_body")
    riwayat_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM perguruan_tinggi WHERE alamat IS NOT NULL AND alamat != ''")
    enriched_pt_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM perguruan_tinggi WHERE status_tuntas = 1")
    tuntas_pt_count = cursor.fetchone()[0]
    
    conn.close()
    return pt_count, prodi_count, riwayat_count, enriched_pt_count, tuntas_pt_count
