import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Konfigurasi Halaman (Premium Aesthetics)
st.set_page_config(
    page_title="PDDIKTI Analytics Engine",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# SISTEM AUTENTIKASI
# ---------------------------------------------------------
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>🔒 Dasbor Analitik PDDIKTI</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Akses terbatas. Silakan masuk menggunakan kredensial Anda.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login", use_container_width=True)
            
            if submit_button:
                if username == "admin@amikom.ac.id" and password == "amikom":
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.error("❌ Email atau Password salah!")
                    
    st.stop() # Hentikan eksekusi seluruh script ke bawah jika belum login

# Tema diserahkan sepenuhnya ke bawaan Streamlit (via config.toml)

# ---------------------------------------------------------
# DATA LOADING & PREPARATION (CACHED)
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    conn = sqlite3.connect('pddikti.db')
    
    # Load raw tables
    df_pt = pd.read_sql("SELECT * FROM perguruan_tinggi", conn)
    df_prodi = pd.read_sql("SELECT * FROM program_studi", conn)
    df_riwayat = pd.read_sql("SELECT * FROM riwayat_student_body", conn)
    conn.close()
    
    if df_riwayat.empty:
        return df_pt, df_prodi, pd.DataFrame(), pd.DataFrame()
        
    # Standarisasi Tahun Akademik
    # semester format is usually "2023/2024 Ganjil", extract first 4 chars
    df_riwayat['tahun'] = df_riwayat['semester'].str[:4].astype(int, errors='ignore')
    # Filter out rows where tahun extraction failed
    df_riwayat = df_riwayat[pd.to_numeric(df_riwayat['tahun'], errors='coerce').notnull()]
    df_riwayat['tahun'] = df_riwayat['tahun'].astype(int)
    
    # Hapus seluruh riwayat di atas tahun 2025 secara global agar tidak masuk ke grafik
    df_riwayat = df_riwayat[df_riwayat['tahun'] <= 2025]
    
    # Kita ambil puncak (max) student body per tahun jika ada semester Ganjil dan Genap
    df_yearly = df_riwayat.groupby(['id_prodi', 'tahun'])['student_body'].max().reset_index()
    
    # Merge dengan prodi dan kampus
    df_merged = df_yearly.merge(df_prodi, on='id_prodi').merge(df_pt, on='id_pt')
    
    # === FILTER ANTI-DUPLIKAT GLOBAL ===
    # Membersihkan duplikasi data mahasiswa kembar dari kampus yang sama
    df_merged = df_merged.drop_duplicates(subset=['id_pt', 'nama_prodi', 'jenjang', 'tahun', 'student_body']).copy()
    
    # Pivot Tabel: Kolom adalah Tahun, Baris adalah Prodi
    df_pivot = df_merged.pivot_table(
        index=['id_pt', 'kode_pt', 'nama_pt', 'id_prodi', 'kode_prodi', 'nama_prodi', 'jenjang', 'akreditasi', 'pembina'],
        columns='tahun',
        values='student_body'
    ).reset_index()
    
    return df_pt, df_prodi, df_merged, df_pivot

with st.spinner("⏳ Menginisialisasi Mesin Analitik Data PDDIKTI..."):
    df_pt, df_prodi, df_merged, df_pivot = load_data()

def load_maba_data():
    conn_maba = sqlite3.connect('mahasiswa_baru.db')
    df_enroll = pd.read_sql_query("SELECT * FROM v_enrollment_full", conn_maba)
    df_yoy = pd.read_sql_query("SELECT * FROM v_yoy_growth", conn_maba)
    conn_maba.close()
    return df_enroll, df_yoy

with st.spinner("⏳ Menginisialisasi Data Mahasiswa Baru..."):
    df_maba, df_maba_yoy = load_maba_data()

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def calculate_delta(df, tahun_sekarang, range_tahun):
    tahun_lalu = tahun_sekarang - range_tahun
    
    if tahun_sekarang not in df.columns or tahun_lalu not in df.columns:
        df['Delta (Angka)'] = 0
        df['Delta (%)'] = 0.0
        return df
        
    # Kalkulasi vektorisasi super cepat
    df['Delta (Angka)'] = df[tahun_sekarang].fillna(0) - df[tahun_lalu].fillna(0)
    
    # Menghindari division by zero
    mask_nol = df[tahun_lalu].fillna(0) == 0
    df['Delta (%)'] = np.where(
        mask_nol, 
        np.where(df[tahun_sekarang].fillna(0) > 0, 100.0, 0.0), # Jika sebelumnya 0 dan sekarang ada, anggap 100% (baru)
        (df['Delta (Angka)'] / df[tahun_lalu]) * 100
    )
    return df

# ---------------------------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------------------------
st.sidebar.title("🎓 PDDIKTI Analytics")

modul = st.sidebar.selectbox("Pilih Modul Dasbor:", ["Modul Utama (PDDIKTI)", "Modul Mahasiswa Baru"])

if modul == "Modul Utama (PDDIKTI)":
    menu = st.sidebar.radio(
        "Navigasi Utama:",
        [
            "📊 Dashboard Nasional", 
            "🔍 Analisis Prodi (Head-to-Head)", 
            "🏛️ Daftar Perguruan Tinggi", 
            "🎓 Daftar Program Studi",
            "📊 Top 10 Pertumbuhan (Rising Stars)",
            "📈 Tren Pertumbuhan Prodi",
            "🏢 Analisis Prodi Per Pembina",
            "🏫 Profil Perguruan Tinggi",
            "🏢 Analisis Kampus Per Pembina"
        ]
    )
else:
    menu = st.sidebar.radio(
        "Navigasi Mahasiswa Baru:",
        [
            "🎓 Analisis Mahasiswa Baru"
        ]
    )

if df_merged.empty and modul == "Modul Utama (PDDIKTI)":
    st.error("⚠️ Database utama masih kosong atau belum ada riwayat semester yang berhasil diekstrak.")
    st.stop()

# Deteksi Tahun Maksimal yang tersedia di data (Dibatasi maksimal 2025)
available_years = sorted([c for c in df_pivot.columns if isinstance(c, int) and c <= 2025])
max_year = available_years[-1] if available_years else 2025

# ---------------------------------------------------------
# MENU 1: DASHBOARD NASIONAL
# ---------------------------------------------------------
if menu == "📊 Dashboard Nasional":
    st.title("📊 Dashboard Eksekutif PDDIKTI")
    st.markdown("Pusat pantauan statistik pendidikan tinggi secara nasional.")
    
    # Kalkulasi Metrik
    total_pt = len(df_pt)
    total_prodi_unik = df_prodi['nama_prodi'].nunique()
    total_mahasiswa_aktif = df_merged[df_merged['tahun'] == max_year]['student_body'].sum()
    
    # Layout KPI
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="Total Perguruan Tinggi", value=f"{total_pt:,}")
    with col2:
        st.metric(label=f"Total Mahasiswa ({max_year})", value=f"{int(total_mahasiswa_aktif):,}")
    with col3:
        st.metric(label="Variasi Program Studi", value=f"{total_prodi_unik:,}")
        
    st.write("---")
    
    col_chart, col_table = st.columns([2, 1])
    
    with col_chart:
        st.subheader("📈 Tren Mahasiswa Nasional")
        tren_nasional = df_merged.groupby('tahun')['student_body'].sum().reset_index()
        fig = px.line(tren_nasional, x='tahun', y='student_body', markers=True, 
                      line_shape='spline', title="Total Student Body per Tahun",
                      labels={'tahun': 'Tahun Akademik', 'student_body': 'Total Mahasiswa'})
        fig.update_traces(line_color='#2563eb', line_width=3, marker_size=8)
        st.plotly_chart(fig, use_container_width=True)
        
    with col_table:
        st.subheader("📋 Sebaran Prodi Terbanyak")
        st.markdown("Prodi apa yang paling banyak dibuka oleh kampus?")
        sebaran_prodi = df_prodi.groupby('nama_prodi').size().reset_index(name='Jumlah Kampus')
        sebaran_prodi = sebaran_prodi.sort_values(by='Jumlah Kampus', ascending=False).head(10)
        st.dataframe(sebaran_prodi, hide_index=True)

    st.write("---")
    st.subheader("🏢 Rekapitulasi Nasional Berdasarkan Wilayah Pembina")
    st.markdown("Tabel perbandingan total mahasiswa secara nasional di masing-masing instansi pembina (Kementerian / LLDikti) dari tahun ke tahun.")
    
    # Agregasi data per pembina per tahun
    df_nasional_pembina = df_merged.groupby(['pembina', 'tahun'])['student_body'].sum().reset_index()
    df_nas_pivot = df_nasional_pembina.pivot_table(index='pembina', columns='tahun', values='student_body', fill_value=0).reset_index()
    
    # Hitung tahun awal dan akhir yang ada
    start_y = df_nasional_pembina['tahun'].min()
    end_y = max_year
    
    df_nas_pivot['Pertumbuhan (Angka)'] = df_nas_pivot[end_y] - df_nas_pivot[start_y]
    df_nas_pivot['Pertumbuhan (%)'] = np.where(df_nas_pivot[start_y] > 0, 
                                            (df_nas_pivot['Pertumbuhan (Angka)'] / df_nas_pivot[start_y]) * 100, 
                                            0.0)
    
    # Siapkan kolom
    cols_nas = ['pembina'] + [y for y in range(start_y, end_y+1) if y in df_nas_pivot.columns] + ['Pertumbuhan (Angka)', 'Pertumbuhan (%)']
    df_nas_final = df_nas_pivot[cols_nas].copy()
    
    df_nas_final.rename(columns={'pembina': 'Instansi Pembina'}, inplace=True)
    df_nas_final = df_nas_final.sort_values(by=end_y, ascending=False).reset_index(drop=True)
    df_nas_final.insert(0, 'No.', df_nas_final.index + 1)
    
    # Formatting
    format_nas = {'Pertumbuhan (Angka)': '{:+,.0f}', 'Pertumbuhan (%)': '{:+.1f}%'}
    for y in range(start_y, end_y+1):
        if y in df_nas_final.columns:
            format_nas[y] = "{:,.0f}"
            
    st.dataframe(
        df_nas_final.style.format(format_nas).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Pertumbuhan (Angka)', 'Pertumbuhan (%)']),
        hide_index=True,
        use_container_width=True,
        height=600
    )

# ---------------------------------------------------------
# MENU 2: ANALISIS PRODI (MANDATORI)
# ---------------------------------------------------------
elif menu == "🔍 Analisis Prodi (Head-to-Head)":
    st.title("🔍 Analisis Kompetisi Program Studi")
    st.markdown("Bandingkan performa sebuah prodi secara *head-to-head* dengan kampus kompetitor di seluruh Indonesia.")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Filter Analisis")
    
    list_prodi = sorted(df_prodi['nama_prodi'].unique().tolist())
    selected_prodi = st.sidebar.selectbox("1. Pilih Nama Prodi", list_prodi)
    
    # Dapatkan daftar jenjang yang tersedia untuk prodi ini
    df_temp_jenjang = df_pivot[df_pivot['nama_prodi'] == selected_prodi]
    list_jenjang = sorted(df_temp_jenjang['jenjang'].unique().tolist())
    selected_jenjang = st.sidebar.selectbox("2. Pilih Jenjang", list_jenjang)
    
    # Dapatkan daftar pembina yang tersedia
    df_temp_pembina = df_pivot[(df_pivot['nama_prodi'] == selected_prodi) & (df_pivot['jenjang'] == selected_jenjang)]
    list_pembina = ["Semua"] + sorted([str(p) for p in df_temp_pembina['pembina'].unique() if p])
    selected_pembina = st.sidebar.selectbox("3. Pilih Pembina", list_pembina)
    
    # Filter kampus yang PUNYA prodi, jenjang, dan pembina tersebut
    if selected_pembina == "Semua":
        df_filtered_prodi = df_pivot[(df_pivot['nama_prodi'] == selected_prodi) & (df_pivot['jenjang'] == selected_jenjang)]
    else:
        df_filtered_prodi = df_pivot[(df_pivot['nama_prodi'] == selected_prodi) & (df_pivot['jenjang'] == selected_jenjang) & (df_pivot['pembina'] == selected_pembina)]
        
    list_kampus = sorted(df_filtered_prodi['nama_pt'].unique().tolist())
    
    if not list_kampus:
        st.warning(f"Belum ada data kampus untuk prodi {selected_prodi} ({selected_jenjang}) dengan filter pembina tersebut.")
        st.stop()
        
    selected_kampus = st.sidebar.selectbox("4. Pilih Kampus Utama (Target)", list_kampus)
    rentang_tahun = st.sidebar.slider("5. Bandingkan Pertumbuhan (X Tahun Terakhir)", min_value=1, max_value=5, value=3)
    
    # 1. Detail Kampus Target
    st.subheader(f"🏛️ Profil: {selected_prodi} ({selected_jenjang}) di {selected_kampus}")
    target_data = df_filtered_prodi[df_filtered_prodi['nama_pt'] == selected_kampus]
    
    if target_data.empty:
        st.error("Data tidak ditemukan.")
    else:
        # Tampilkan metrik pertumbuhan target
        target_calculated = calculate_delta(target_data.copy(), max_year, rentang_tahun)
        val_sekarang = target_calculated[max_year].values[0] if max_year in target_calculated.columns else 0
        val_lalu = target_calculated[max_year - rentang_tahun].values[0] if (max_year - rentang_tahun) in target_calculated.columns else 0
        delta_angka = target_calculated['Delta (Angka)'].values[0]
        delta_persen = target_calculated['Delta (%)'].values[0]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(label=f"Mahasiswa ({max_year})", value=f"{val_sekarang:,.0f}")
        c2.metric(label=f"Mahasiswa ({max_year - rentang_tahun})", value=f"{val_lalu:,.0f}")
        c3.metric(label=f"Pertumbuhan ({rentang_tahun} Thn)", value=f"{delta_angka:,.0f} Mhs", delta=f"{delta_persen:.1f}%")
        
        # Plot garis untuk target
        df_target_history = df_merged[(df_merged['nama_prodi'] == selected_prodi) & (df_merged['jenjang'] == selected_jenjang) & (df_merged['nama_pt'] == selected_kampus)]
        fig_t = px.line(df_target_history, x='tahun', y='student_body', line_group='id_prodi', markers=True, 
                        line_shape='spline', title=f"Lintasan {selected_prodi} ({selected_jenjang}) - {selected_kampus}")
        fig_t.update_traces(line_width=3, marker_size=8)
        st.plotly_chart(fig_t, use_container_width=True)
        
    st.write("---")
    
    # 1.5. Agregat Nasional / Pembina
    title_agg = f"🌐 Agregat Pertumbuhan: {selected_prodi} ({selected_jenjang})"
    title_agg += f" - {selected_pembina}" if selected_pembina != "Semua" else " - Nasional"
    st.subheader(title_agg)
    st.markdown("Total keseluruhan *student body* untuk prodi dan jenjang ini berdasarkan filter yang Anda pilih.")
    
    # Hitung agregat tahunan dari seluruh kampus yang lolos filter
    years_avail = [col for col in df_filtered_prodi.columns if isinstance(col, int)]
    years_avail = sorted(years_avail)
    
    if years_avail:
        agg_data = {y: [df_filtered_prodi[y].sum()] for y in years_avail}
        df_agg = pd.DataFrame(agg_data)
        
        agg_cols = []
        format_agg = {}
        for y in years_avail:
            agg_cols.append(y)
            format_agg[y] = "{:,.0f}"
            
        tahun_sekarang = max_year
        tahun_lalu = max_year - rentang_tahun
        
        if tahun_sekarang in df_agg.columns and tahun_lalu in df_agg.columns:
            df_agg['Delta (Angka)'] = df_agg[tahun_sekarang] - df_agg[tahun_lalu]
            val_lalu_agg = df_agg[tahun_lalu].values[0]
            df_agg['Delta (%)'] = (df_agg['Delta (Angka)'] / val_lalu_agg * 100) if val_lalu_agg != 0 else 0
            
            agg_cols.extend(['Delta (Angka)', 'Delta (%)'])
            format_agg['Delta (Angka)'] = "{:+,.0f}"
            format_agg['Delta (%)'] = "{:+.1f}%"
            
        df_agg = df_agg[agg_cols]
        
        # Konversi nama kolom ke format yang lebih rapi (Mhs 2019, Mhs 2020, dst)
        rename_dict = {y: f"Mhs {y}" for y in years_avail}
        df_agg.rename(columns=rename_dict, inplace=True)
        
        # Update format_agg keys
        format_agg = {rename_dict.get(k, k): v for k, v in format_agg.items()}
        
        subset_colors = ['Delta (Angka)', 'Delta (%)'] if 'Delta (Angka)' in df_agg.columns else []
        
        st.dataframe(
            df_agg.style.format(format_agg).map(
                lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), 
                subset=subset_colors
            ),
            hide_index=True,
            use_container_width=True
        )
    
    st.write("---")
    
    # 2. Perbandingan Nasional
    st.subheader("📊 Perbandingan Nasional")
    st.markdown(f"Bagaimana posisi **{selected_kampus}** dibandingkan **{len(list_kampus)-1} kampus lain** yang juga memiliki prodi **{selected_prodi} ({selected_jenjang})**?")
    
    # Kalkulasi seluruh kampus
    df_kompetisi = calculate_delta(df_filtered_prodi.copy(), max_year, rentang_tahun)
    
    # Sortir dan format
    df_kompetisi = df_kompetisi[['nama_pt', 'jenjang', 'akreditasi', (max_year - rentang_tahun), max_year, 'Delta (Angka)', 'Delta (%)']]
    df_kompetisi.rename(columns={(max_year - rentang_tahun): f"Mhs {max_year - rentang_tahun}", max_year: f"Mhs {max_year}"}, inplace=True)
    
    # Buat 2 Dataframe tersortir dengan nomor urut
    df_tertinggi = df_kompetisi.sort_values(by='Delta (Angka)', ascending=False).reset_index(drop=True)
    df_tertinggi.insert(0, 'No.', df_tertinggi.index + 1)
    
    df_terendah = df_kompetisi.sort_values(by='Delta (Angka)', ascending=True).reset_index(drop=True)
    df_terendah.insert(0, 'No.', df_terendah.index + 1)
    
    col_kiri, col_kanan = st.columns(2)
    
    with col_kiri:
        st.markdown("**📈 Pertumbuhan Terbanyak**")
        st.dataframe(
            df_tertinggi.style.format({
                f"Mhs {max_year - rentang_tahun}": "{:,.0f}",
                f"Mhs {max_year}": "{:,.0f}",
                'Delta (Angka)': "{:+,.0f}",
                'Delta (%)': "{:+.1f}%"
            }).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Delta (Angka)', 'Delta (%)']),
            hide_index=True,
            height=400,
            use_container_width=True
        )
        
    with col_kanan:
        st.markdown("**📉 Penurunan Terbanyak**")
        st.dataframe(
            df_terendah.style.format({
                f"Mhs {max_year - rentang_tahun}": "{:,.0f}",
                f"Mhs {max_year}": "{:,.0f}",
                'Delta (Angka)': "{:+,.0f}",
                'Delta (%)': "{:+.1f}%"
            }).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Delta (Angka)', 'Delta (%)']),
            hide_index=True,
            height=400,
            use_container_width=True
        )
    
    # Sorotan (Auto-Highlight)
    if len(df_kompetisi) > 1:
        top_growth = df_kompetisi.nlargest(1, 'Delta (Angka)')
        top_decline = df_kompetisi.nsmallest(1, 'Delta (Angka)')
        
        st.info(f"🏆 **Top Growth:** {top_growth['nama_pt'].values[0]} melesat tajam dengan tambahan **{top_growth['Delta (Angka)'].values[0]:,.0f} mahasiswa** ({top_growth['Delta (%)'].values[0]:+.1f}%).")
        if top_decline['Delta (Angka)'].values[0] < 0:
            st.error(f"⚠️ **Top Decline:** {top_decline['nama_pt'].values[0]} kehilangan **{abs(top_decline['Delta (Angka)'].values[0]):,.0f} mahasiswa** ({top_decline['Delta (%)'].values[0]:+.1f}%).")

# ---------------------------------------------------------
# MENU 3: DAFTAR PERGURUAN TINGGI
# ---------------------------------------------------------
elif menu == "🏛️ Daftar Perguruan Tinggi":
    st.title("🏛️ Master Data: Perguruan Tinggi")
    st.markdown("Eksplorasi seluruh daftar institusi pendidikan tinggi di dalam database.")
    
    search_pt = st.text_input("Cari Nama atau Kode Kampus:", "")
    df_display = df_pt.copy()
    if search_pt:
        df_display = df_display[df_display['nama_pt'].str.contains(search_pt, case=False, na=False) | df_display['kode_pt'].str.contains(search_pt, case=False, na=False)]
    
    st.dataframe(df_display, hide_index=True)

# ---------------------------------------------------------
# MENU 4: DAFTAR PROGRAM STUDI
# ---------------------------------------------------------
elif menu == "🎓 Daftar Program Studi":
    st.title("🎓 Master Data: Program Studi")
    st.markdown("Eksplorasi seluruh program studi beserta afiliasi kampusnya.")
    
    # Merge untuk relasi lengkap
    df_ps = df_prodi.merge(df_pt[['id_pt', 'nama_pt', 'kode_pt']], on='id_pt', how='left')
    df_ps = df_ps[['kode_pt', 'nama_pt', 'kode_prodi', 'nama_prodi', 'jenjang', 'akreditasi']]
    
    search_ps = st.text_input("Cari Nama Prodi:", "")
    if search_ps:
        df_ps = df_ps[df_ps['nama_prodi'].str.contains(search_ps, case=False, na=False)]
        
    st.dataframe(df_ps, hide_index=True)

# ---------------------------------------------------------
# MENU 5: LEADERBOARD PERTUMBUHAN
# ---------------------------------------------------------
elif menu == "📊 Top 10 Pertumbuhan (Rising Stars)":
    st.title("🚀 Leaderboard Nasional (Top Growth)")
    st.markdown("Pemetaan program studi dengan tingkat pertumbuhan mahasiswa tertinggi.")
    
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        rentang_lb = st.slider("Rentang Pengukuran Pertumbuhan (Tahun)", min_value=1, max_value=5, value=3)
    with col_l2:
        metrik_lb = st.radio("Metrik Pengukuran Berdasarkan:", ["Angka Kenaikan Mutlak (Mhs)", "Persentase Lonjakan (%)"])
    
    sort_col = 'Delta (Angka)' if "Angka" in metrik_lb else 'Delta (%)'
    
    # Kalkulasi skala masif
    df_lb = calculate_delta(df_pivot.copy(), max_year, rentang_lb)
    
    # Filter prodi yang sudah establish (menghindari persentase tidak wajar karena mahasiswa awalnya 0/1)
    df_lb = df_lb[df_lb[max_year - rentang_lb] >= 10]
    
    # Ambil Top 100
    df_lb_top = df_lb.nlargest(100, sort_col)
    
    # Tampilan
    df_lb_display = df_lb_top[['nama_pt', 'nama_prodi', 'jenjang', (max_year - rentang_lb), max_year, 'Delta (Angka)', 'Delta (%)']].copy()
    df_lb_display.rename(columns={(max_year - rentang_lb): f"Mhs {max_year - rentang_lb}", max_year: f"Mhs {max_year}"}, inplace=True)
    
    st.dataframe(
        df_lb_display.style.format({
            f"Mhs {max_year - rentang_lb}": "{:,.0f}",
            f"Mhs {max_year}": "{:,.0f}",
            'Delta (Angka)': "{:+,.0f}",
            'Delta (%)': "{:+.1f}%"
        }).background_gradient(subset=[sort_col], cmap="Greens"),
        hide_index=True,
        height=600
    )

# ---------------------------------------------------------
# MENU 6: TREN PERTUMBUHAN PRODI
# ---------------------------------------------------------
elif menu == "📈 Tren Pertumbuhan Prodi":
    st.title("📈 Tren Pertumbuhan Program Studi")
    st.markdown("Lihat dinamika pembukaan program studi baru dan pertumbuhan mahasiswanya dari tahun ke tahun.")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Parameter Waktu")
    
    start_year = st.sidebar.selectbox("Tahun Awal", list(range(2000, 2025)), index=19) # Default 2019
    end_year = st.sidebar.selectbox("Tahun Akhir", list(range(2001, 2026)), index=24) # Default 2025
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Filter Khusus")
    filter_it = st.sidebar.checkbox("💻 Rumpun Informatika & Teknologi")
        
    if start_year >= end_year:
        st.error("Tahun Awal harus lebih kecil dari Tahun Akhir.")
        st.stop()
        
    # Proses ekstraksi data
    df_prodi_tren = df_prodi.copy()
    
    if filter_it:
        it_keywords = ['informatika', 'sistem informasi', 'teknologi informasi', 'komputer', 'rekayasa perangkat lunak', 'software', 'bisnis digital', 'digital bisnis', 'elektro', 'sains data', 'data', 'kecerdasan buatan', 'artificial intelligence', 'siber', 'cyber']
        pattern = '|'.join(it_keywords)
        df_prodi_tren = df_prodi_tren[df_prodi_tren['nama_prodi'].str.contains(pattern, case=False, na=False)]
        st.info("💻 Filter **Rumpun Informatika & Teknologi** diaktifkan.")
    
    # Ekstrak year_berdiri
    df_prodi_tren['year_berdiri'] = df_prodi_tren['tgl_berdiri'].astype(str).str[:4]
    df_prodi_tren['year_berdiri'] = pd.to_numeric(df_prodi_tren['year_berdiri'], errors='coerce').fillna(1900)
    
    # Ekstrak year_tutup (asumsikan kolom tgl_tutup_estimasi ada)
    if 'tgl_tutup_estimasi' in df_prodi_tren.columns:
        df_prodi_tren['year_tutup'] = pd.to_numeric(df_prodi_tren['tgl_tutup_estimasi'], errors='coerce')
        df_prodi_tren['year_tutup'] = df_prodi_tren['year_tutup'].replace(0, 9999).fillna(9999)
    else:
        # Jika belum ada (belum di-harvest), anggap semuanya aktif (9999)
        df_prodi_tren['year_tutup'] = 9999
    
    # Hitung jumlah kampus per prodi per tahun
    years_range = list(range(start_year, end_year + 1))
    
    st.info(f"⏳ Mengaktifkan **Filter Anti-Duplikat** & menghitung pertumbuhan untuk **{len(df_prodi_tren):,} program studi**...")
    
    # === FILTER ANTI-DUPLIKAT (DEDUPLIKATOR KEMENTERIAN) ===
    # 1. Bersihkan df_merged dari duplikasi data mahasiswa yang kembar identik di kampus dan jenjang yang sama
    df_merged_clean = df_merged.drop_duplicates(subset=['id_pt', 'nama_prodi', 'jenjang', 'tahun', 'student_body'])
    
    # 2. Bersihkan df_prodi_tren agar jumlah kampus tidak terhitung dua kali jika ada 2 prodi identik
    df_prodi_tren = df_prodi_tren.drop_duplicates(subset=['id_pt', 'nama_prodi', 'jenjang'])
    
    # Agregasi Total Mahasiswa Nasional per Prodi per Tahun
    df_mhs_grouped = df_merged_clean.groupby(['nama_prodi', 'jenjang', 'tahun'])['student_body'].sum().reset_index()
    df_mhs_grouped['prodi_jenjang'] = df_mhs_grouped['nama_prodi'] + " | " + df_mhs_grouped['jenjang']
    df_mhs_pivot = df_mhs_grouped.pivot(index='prodi_jenjang', columns='tahun', values='student_body').fillna(0)
    
    results = []
    
    # Grouping by nama_prodi dan jenjang
    for (nama, jenjang), group in df_prodi_tren.groupby(['nama_prodi', 'jenjang']):
        row = {'Nama Program Studi': nama, 'Jenjang': jenjang}
        key = f"{nama} | {jenjang}"
        
        # Kondisi: year_berdiri <= Y AND year_tutup > Y
        for y in years_range:
            # Hitung jumlah penyelenggara (kampus)
            active_count = ((group['year_berdiri'] <= y) & (group['year_tutup'] > y)).sum()
            row[f"Kampus {y}"] = active_count
            
            # Ambil total mahasiswa dari pivot
            if key in df_mhs_pivot.index and y in df_mhs_pivot.columns:
                mhs_count = df_mhs_pivot.at[key, y]
            else:
                mhs_count = 0
            row[f"Mhs {y}"] = mhs_count
            
        row['Delta Kampus'] = row[f"Kampus {end_year}"] - row[f"Kampus {start_year}"]
        row['Delta Mhs'] = row[f"Mhs {end_year}"] - row[f"Mhs {start_year}"]
        results.append(row)
        
    df_growth = pd.DataFrame(results)
    
    # Filter prodi yang terlalu sepi agar fokus ke data dominan (min 5 kampus di tahun akhir)
    df_growth = df_growth[df_growth[f"Kampus {end_year}"] >= 5]
    
    # Sortir berdasarkan Delta Mhs tertinggi
    df_growth = df_growth.sort_values('Delta Mhs', ascending=False).reset_index(drop=True)
    
    # --- UI BAGIAN ATAS: TOP 3 HIGHLIGHT ---
    st.subheader(f"📈 Top 3 Prodi dengan Pertumbuhan Mahasiswa Tertinggi ({start_year}-{end_year})")
    if len(df_growth) >= 3:
        c1, c2, c3 = st.columns(3)
        for i, col in enumerate([c1, c2, c3]):
            nama = df_growth.iloc[i]['Nama Program Studi']
            jenjang = df_growth.iloc[i]['Jenjang']
            delta_k = df_growth.iloc[i]['Delta Kampus']
            delta_m = df_growth.iloc[i]['Delta Mhs']
            
            akhir_k = df_growth.iloc[i][f"Kampus {end_year}"]
            akhir_m = df_growth.iloc[i][f"Mhs {end_year}"]
            
            with col:
                st.markdown(f"**#{i+1} {nama} ({jenjang})**")
                st.metric(label=f"Pertumbuhan Mahasiswa ({end_year})", value=f"{akhir_m:,.0f}", delta=f"{delta_m:,.0f} Mhs")
                st.metric(label=f"Penambahan Kampus ({end_year})", value=f"{akhir_k}", delta=f"{delta_k} Kampus")
                st.write("---")
                
    st.write("---")
    
    # --- TABEL UTAMA ---
    st.subheader("📊 Tabel Analitik Pertumbuhan Prodi (Kampus & Mahasiswa)")
    
    format_dict = {}
    for y in years_range:
        format_dict[f"Kampus {y}"] = "{:,.0f}"
        format_dict[f"Mhs {y}"] = "{:,.0f}"
        
    format_dict['Delta Kampus'] = "{:+,.0f}"
    format_dict['Delta Mhs'] = "{:+,.0f}"
    
    # Atur urutan kolom agar enak dilihat: Nama, Jenjang, lalu K19, M19, K20, M20... lalu Delta
    cols_order = ['Nama Program Studi', 'Jenjang']
    for y in years_range:
        cols_order.extend([f"Kampus {y}", f"Mhs {y}"])
    cols_order.extend(['Delta Kampus', 'Delta Mhs'])
    
    df_growth = df_growth[cols_order]
    
    # --- FITUR PENCARIAN ---
    search_prodi = st.text_input("🔍 Cari Program Studi (Ketik nama prodi lalu tekan Enter):", placeholder="Contoh: Manajemen, Hukum, Kedokteran...")
    if search_prodi:
        df_growth = df_growth[df_growth['Nama Program Studi'].str.contains(search_prodi, case=False, na=False)]
    
    st.dataframe(
        df_growth.style.format(format_dict).background_gradient(subset=['Delta Mhs', 'Delta Kampus'], cmap="Greens"),
        height=700,
        hide_index=True
    )
    
    st.write("---")
    st.subheader("🏢 Detail Penyelenggara Program Studi")
    
    # Sediakan opsi untuk memilih prodi dari list df_growth yang sedang difilter
    list_prodi = [""] + sorted(df_growth['Nama Program Studi'].unique().tolist())
    
    selected_prodi_detail = st.selectbox(
        "Pilih Program Studi untuk melihat daftar Perguruan Tinggi penyelenggara secara detail:",
        options=list_prodi,
        format_func=lambda x: "Pilih Program Studi di sini..." if x == "" else x
    )
    
    if selected_prodi_detail:
        # Filter prodi tren berdasarkan nama
        df_detail_kampus = df_prodi_tren[df_prodi_tren['nama_prodi'] == selected_prodi_detail].copy()
        
        # Merge dengan df_pt untuk mendapatkan nama kampus
        df_detail_kampus = df_detail_kampus.merge(df_pt[['id_pt', 'nama_pt']], on='id_pt', how='left')
        
        # Ambil data riwayat mahasiswa untuk prodi ini di rentang tahun terpilih menggunakan df_merged_clean
        df_mhs_detail = df_merged_clean[(df_merged_clean['nama_prodi'] == selected_prodi_detail) & (df_merged_clean['tahun'].isin(years_range))]
        
        # Pivot data mahasiswa per PRODI per tahun (Bukan per kampus, agar D3 dan S1 tidak tercampur!)
        if not df_mhs_detail.empty:
            df_mhs_pivot = df_mhs_detail.pivot_table(index='id_prodi', columns='tahun', values='student_body').fillna(0).reset_index()
            # Merge ke df_detail_kampus
            df_detail_kampus = df_detail_kampus.merge(df_mhs_pivot, on='id_prodi', how='left')
        
        # Persiapkan kolom untuk ditampilkan
        cols_tampil = ['nama_pt', 'jenjang', 'status', 'year_berdiri', 'year_tutup']
        format_dict_detail = {}
        
        # Masukkan kolom tahun ke tabel, jika tidak ada data diisi 0
        for y in years_range:
            if y not in df_detail_kampus.columns:
                df_detail_kampus[y] = 0
            df_detail_kampus[y] = df_detail_kampus[y].fillna(0)
            cols_tampil.append(y)
            format_dict_detail[y] = "{:,.0f}"
            
        # Hitung Delta Pertumbuhan Mahasiswa di Kampus Tersebut
        df_detail_kampus['Delta Mhs'] = df_detail_kampus[end_year] - df_detail_kampus[start_year]
        cols_tampil.append('Delta Mhs')
        format_dict_detail['Delta Mhs'] = "{:+,.0f}"
        
        df_tampil = df_detail_kampus[cols_tampil].rename(columns={
            'nama_pt': 'Perguruan Tinggi',
            'jenjang': 'Jenjang',
            'status': 'Status',
            'year_berdiri': 'Tahun Buka',
            'year_tutup': 'Estimasi Tutup'
        })
        
        # Format tampilan agar lebih rapi
        if 'Tahun Buka' in df_tampil.columns:
            df_tampil['Tahun Buka'] = df_tampil['Tahun Buka'].replace(1900, 'Tidak Diketahui')
            
        if 'Estimasi Tutup' in df_tampil.columns:
            df_tampil['Estimasi Tutup'] = df_tampil['Estimasi Tutup'].replace(9999, 'Masih Aktif')
            
        # Sort berdasarkan Delta Mhs terbanyak, lalu total mahasiswa terakhir
        df_tampil = df_tampil.sort_values(['Delta Mhs', end_year], ascending=[False, False]).reset_index(drop=True)
            
        # Eksekusi Filter Anti-Duplikat visual untuk berjaga-jaga jika ada sisa duplikasi
        df_tampil = df_tampil.drop_duplicates(subset=['Perguruan Tinggi', 'Jenjang'] + years_range).reset_index(drop=True)
            
        st.markdown(f"**Menampilkan riwayat pertumbuhan mahasiswa untuk prodi `{selected_prodi_detail}` di seluruh kampus:**")
        
        st.dataframe(
            df_tampil.style.format(format_dict_detail).background_gradient(subset=['Delta Mhs'], cmap="Blues"),
            height=600,
            use_container_width=True,
            hide_index=True
        )

# ---------------------------------------------------------
# MENU 7: ANALISIS PRODI PER PEMBINA
# ---------------------------------------------------------
elif menu == "🏢 Analisis Prodi Per Pembina":
    st.title("🏢 Analisis Prodi Per Pembina")
    st.markdown("Analisis agregat pertumbuhan dan penurunan seluruh program studi yang dikelompokkan berdasarkan instansi Pembina (misal: Kementerian Agama, Kemdikbud).")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Parameter Analisis")
    
    # Pilih Pembina
    raw_pembina = sorted([str(p) for p in df_pivot['pembina'].unique() if p and p != "-"])
    list_pembina = ["Semua (Nasional)"] + raw_pembina
    selected_pembina = st.sidebar.selectbox("1. Pilih Instansi Pembina", list_pembina)
    
    rentang_tahun = st.sidebar.slider("2. Bandingkan Pertumbuhan (X Tahun Terakhir)", min_value=1, max_value=5, value=3)
    
    pembina_label = "Tingkat Nasional" if selected_pembina == "Semua (Nasional)" else selected_pembina
    st.info(f"⏳ Menghitung agregat seluruh program studi di **{pembina_label}**...")
    
    # Filter df_merged by pembina
    if selected_pembina == "Semua (Nasional)":
        df_pembina = df_merged.copy()
    else:
        df_pembina = df_merged[df_merged['pembina'] == selected_pembina]
    
    if df_pembina.empty:
        st.warning("Data tidak ditemukan untuk pembina ini.")
    else:
        # Agregat total mahasiswa per prodi + jenjang per tahun
        df_prodi_agg = df_pembina.groupby(['nama_prodi', 'jenjang', 'tahun'])['student_body'].sum().reset_index()
        
        # Pivot agar tahun menjadi kolom
        df_prodi_pivot = df_prodi_agg.pivot_table(index=['nama_prodi', 'jenjang'], columns='tahun', values='student_body', fill_value=0).reset_index()
        
        tahun_sekarang = max_year
        tahun_lalu = max_year - rentang_tahun
        
        # Pastikan kolom tahun yang diminta ada
        if tahun_sekarang not in df_prodi_pivot.columns:
            df_prodi_pivot[tahun_sekarang] = 0
        if tahun_lalu not in df_prodi_pivot.columns:
            df_prodi_pivot[tahun_lalu] = 0
            
        # Hitung Delta
        df_prodi_pivot['Delta (Angka)'] = df_prodi_pivot[tahun_sekarang] - df_prodi_pivot[tahun_lalu]
        # Hindari pembagian dengan nol
        df_prodi_pivot['Delta (%)'] = np.where(df_prodi_pivot[tahun_lalu] > 0, 
                                               (df_prodi_pivot['Delta (Angka)'] / df_prodi_pivot[tahun_lalu]) * 100, 
                                               0.0)
                                               
        # Format dan ganti nama kolom
        df_prodi_pivot.rename(columns={tahun_lalu: f"Mhs {tahun_lalu}", tahun_sekarang: f"Mhs {tahun_sekarang}"}, inplace=True)
        cols_to_show = ['nama_prodi', 'jenjang', f"Mhs {tahun_lalu}", f"Mhs {tahun_sekarang}", 'Delta (Angka)', 'Delta (%)']
        
        df_final = df_prodi_pivot[cols_to_show].rename(columns={'nama_prodi': 'Program Studi', 'jenjang': 'Jenjang'})
        
        # --- TABEL RINGKASAN GRAND TOTAL ---
        grand_total_lalu = df_final[f"Mhs {tahun_lalu}"].sum()
        grand_total_sekarang = df_final[f"Mhs {tahun_sekarang}"].sum()
        grand_delta_angka = grand_total_sekarang - grand_total_lalu
        grand_delta_persen = (grand_delta_angka / grand_total_lalu * 100) if grand_total_lalu > 0 else 0
        
        st.subheader("🌐 Ringkasan Total Keseluruhan")
        st.markdown(f"Total *student body* gabungan dari **semua program studi** di wilayah **{pembina_label}**.")
        
        df_grand_total = pd.DataFrame([{
            'Wilayah Pembina': pembina_label,
            f'Total Mhs {tahun_lalu}': grand_total_lalu,
            f'Total Mhs {tahun_sekarang}': grand_total_sekarang,
            'Pertumbuhan (Angka)': grand_delta_angka,
            'Pertumbuhan (%)': grand_delta_persen
        }])
        
        format_grand = {
            f'Total Mhs {tahun_lalu}': "{:,.0f}",
            f'Total Mhs {tahun_sekarang}': "{:,.0f}",
            'Pertumbuhan (Angka)': "{:+,.0f}",
            'Pertumbuhan (%)': "{:+.1f}%"
        }
        
        st.dataframe(
            df_grand_total.style.format(format_grand).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Pertumbuhan (Angka)', 'Pertumbuhan (%)']),
            hide_index=True,
            use_container_width=True
        )
        
        st.write("---")
        
        # Pisah menjadi Growing dan Declining
        df_growing = df_final.sort_values(by='Delta (Angka)', ascending=False).reset_index(drop=True)
        df_growing.insert(0, 'No.', df_growing.index + 1)
        
        df_declining = df_final.sort_values(by='Delta (Angka)', ascending=True).reset_index(drop=True)
        df_declining.insert(0, 'No.', df_declining.index + 1)
        
        col_kiri, col_kanan = st.columns(2)
        
        format_dict = {
            f"Mhs {tahun_lalu}": "{:,.0f}",
            f"Mhs {tahun_sekarang}": "{:,.0f}",
            'Delta (Angka)': "{:+,.0f}",
            'Delta (%)': "{:+.1f}%"
        }
        
        # Tampilkan
        with col_kiri:
            st.markdown(f"**📈 Top Pertumbuhan (Growing)**")
            st.dataframe(
                df_growing.style.format(format_dict).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Delta (Angka)', 'Delta (%)']),
                hide_index=True,
                height=700,
                use_container_width=True
            )
            
        with col_kanan:
            st.markdown(f"**📉 Top Penurunan (Declining)**")
            st.dataframe(
                df_declining.style.format(format_dict).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Delta (Angka)', 'Delta (%)']),
                hide_index=True,
                height=700,
                use_container_width=True
            )

# ---------------------------------------------------------
# MENU 8: PROFIL PERGURUAN TINGGI
# ---------------------------------------------------------
elif menu == "🏫 Profil Perguruan Tinggi":
    st.title("🏫 Profil Perguruan Tinggi")
    st.markdown("Lihat rincian metrik dan daftar seluruh program studi yang diselenggarakan oleh sebuah kampus secara mendalam.")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Parameter Analisis")
    
    list_kampus = sorted([str(k) for k in df_pivot['nama_pt'].unique() if k])
    selected_kampus = st.sidebar.selectbox("1. Pilih Perguruan Tinggi", list_kampus)
    
    rentang_tahun = st.sidebar.slider("2. Bandingkan Pertumbuhan (X Tahun Terakhir)", min_value=1, max_value=5, value=3)
    
    st.info(f"⏳ Mengambil data lengkap untuk **{selected_kampus}**...")
    
    df_univ = df_pivot[df_pivot['nama_pt'] == selected_kampus].copy()
    
    if df_univ.empty:
        st.warning("Data tidak ditemukan untuk kampus ini.")
    else:
        tahun_sekarang = max_year
        tahun_lalu = max_year - rentang_tahun
        
        # Pastikan kolom tahun yang diminta ada
        if tahun_sekarang not in df_univ.columns:
            df_univ[tahun_sekarang] = 0
        if tahun_lalu not in df_univ.columns:
            df_univ[tahun_lalu] = 0
            
        df_univ['Delta (Angka)'] = df_univ[tahun_sekarang] - df_univ[tahun_lalu]
        df_univ['Delta (%)'] = np.where(df_univ[tahun_lalu] > 0, 
                                        (df_univ['Delta (Angka)'] / df_univ[tahun_lalu]) * 100, 
                                        0.0)
                                        
        cols_to_show = ['nama_prodi', 'jenjang', 'akreditasi', tahun_lalu, tahun_sekarang, 'Delta (Angka)', 'Delta (%)']
        df_final = df_univ[cols_to_show].rename(columns={
            'nama_prodi': 'Program Studi',
            'jenjang': 'Jenjang',
            'akreditasi': 'Akreditasi',
            tahun_lalu: f'Mhs {tahun_lalu}',
            tahun_sekarang: f'Mhs {tahun_sekarang}'
        })
        
        # --- Ringkasan Total Universitas ---
        total_lalu = df_final[f"Mhs {tahun_lalu}"].sum()
        total_sekarang = df_final[f"Mhs {tahun_sekarang}"].sum()
        delta_angka_univ = total_sekarang - total_lalu
        delta_persen_univ = (delta_angka_univ / total_lalu * 100) if total_lalu > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(label=f"Total Prodi", value=f"{len(df_final)}")
        c2.metric(label=f"Total Mhs ({tahun_lalu})", value=f"{total_lalu:,.0f}")
        c3.metric(label=f"Total Mhs ({tahun_sekarang})", value=f"{total_sekarang:,.0f}")
        c4.metric(label="Pertumbuhan Universitas", value=f"{delta_angka_univ:+,.0f} Mhs", delta=f"{delta_persen_univ:+.1f}%")
        
        # --- Plot Grafik Riwayat Pertumbuhan Universitas ---
        df_kampus_hist = df_merged[df_merged['nama_pt'] == selected_kampus]
        df_kampus_hist_agg = df_kampus_hist.groupby('tahun')['student_body'].sum().reset_index()
        
        if not df_kampus_hist_agg.empty:
            fig_univ = px.line(df_kampus_hist_agg, x='tahun', y='student_body', markers=True,
                               line_shape='spline', title=f"Lintasan Total Keseluruhan Mahasiswa - {selected_kampus}")
            fig_univ.update_traces(line_width=4, marker_size=10, line_color='#0284c7')
            st.plotly_chart(fig_univ, use_container_width=True)
            
        st.write("---")
        
        # Urutkan berdasarkan Mhs sekarang terbanyak
        df_final = df_final.sort_values(by=f'Mhs {tahun_sekarang}', ascending=False).reset_index(drop=True)
        df_final.insert(0, 'No.', df_final.index + 1)
        
        format_dict = {
            f"Mhs {tahun_lalu}": "{:,.0f}",
            f"Mhs {tahun_sekarang}": "{:,.0f}",
            'Delta (Angka)': "{:+,.0f}",
            'Delta (%)': "{:+.1f}%"
        }
        
        st.subheader(f"📚 Rincian Program Studi")
        st.dataframe(
            df_final.style.format(format_dict).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Delta (Angka)', 'Delta (%)']),
            hide_index=True,
            use_container_width=True,
            height=700
        )

# ---------------------------------------------------------
# MENU 9: ANALISIS KAMPUS PER PEMBINA
# ---------------------------------------------------------
elif menu == "🏢 Analisis Kampus Per Pembina":
    st.title("🏢 Analisis Kampus Per Pembina")
    st.markdown("Bandingkan performa *student body* (keseluruhan mahasiswa) antar perguruan tinggi di bawah naungan instansi pembina yang sama.")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Parameter Analisis")
    
    raw_pembina = sorted([str(p) for p in df_pivot['pembina'].unique() if p and p != "-"])
    list_pembina = ["Semua (Nasional)"] + raw_pembina
    selected_pembina = st.sidebar.selectbox("1. Pilih Instansi Pembina", list_pembina)
    
    rentang_tahun = st.sidebar.slider("2. Bandingkan Pertumbuhan (X Tahun Terakhir)", min_value=1, max_value=5, value=3)
    
    pembina_label = "Tingkat Nasional" if selected_pembina == "Semua (Nasional)" else selected_pembina
    st.info(f"⏳ Menghitung agregat seluruh kampus di **{pembina_label}**...")
    
    if selected_pembina == "Semua (Nasional)":
        df_pembina = df_merged.copy()
    else:
        df_pembina = df_merged[df_merged['pembina'] == selected_pembina]
    
    if df_pembina.empty:
        st.warning("Data tidak ditemukan untuk pembina ini.")
    else:
        # Agregat total mahasiswa per kampus per tahun
        df_kampus_agg = df_pembina.groupby(['nama_pt', 'tahun'])['student_body'].sum().reset_index()
        
        # --- Grafik Top 10 Kampus Terbesar di Tahun Terakhir ---
        tahun_terakhir = df_kampus_agg['tahun'].max()
        df_kampus_terakhir = df_kampus_agg[df_kampus_agg['tahun'] == tahun_terakhir]
        top_10_kampus = df_kampus_terakhir.nlargest(10, 'student_body')['nama_pt'].tolist()
        
        df_top_10_hist = df_kampus_agg[df_kampus_agg['nama_pt'].isin(top_10_kampus)]
        
        if not df_top_10_hist.empty:
            st.subheader(f"📈 Lintasan 10 Kampus Terbesar ({pembina_label})")
            st.markdown("Menampilkan dinamika pertumbuhan 10 perguruan tinggi dengan populasi mahasiswa terbesar saat ini.")
            fig_kampus = px.line(df_top_10_hist, x='tahun', y='student_body', color='nama_pt', markers=True,
                                 line_shape='spline')
            fig_kampus.update_traces(line_width=3, marker_size=8)
            # Taruh legenda di bawah agar tidak memakan ruang chart jika nama kampus panjang
            fig_kampus.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5))
            st.plotly_chart(fig_kampus, use_container_width=True)
            
        st.write("---")
        
        # --- Pivot untuk tabel perbandingan ---
        df_kampus_pivot = df_kampus_agg.pivot_table(index='nama_pt', columns='tahun', values='student_body', fill_value=0).reset_index()
        
        tahun_sekarang = max_year
        tahun_lalu = max_year - rentang_tahun
        
        if tahun_sekarang not in df_kampus_pivot.columns:
            df_kampus_pivot[tahun_sekarang] = 0
        if tahun_lalu not in df_kampus_pivot.columns:
            df_kampus_pivot[tahun_lalu] = 0
            
        df_kampus_pivot['Delta (Angka)'] = df_kampus_pivot[tahun_sekarang] - df_kampus_pivot[tahun_lalu]
        df_kampus_pivot['Delta (%)'] = np.where(df_kampus_pivot[tahun_lalu] > 0, 
                                                (df_kampus_pivot['Delta (Angka)'] / df_kampus_pivot[tahun_lalu]) * 100, 
                                                0.0)
                                                
        cols_to_show = ['nama_pt', tahun_lalu, tahun_sekarang, 'Delta (Angka)', 'Delta (%)']
        df_final = df_kampus_pivot[cols_to_show].rename(columns={
            'nama_pt': 'Perguruan Tinggi',
            tahun_lalu: f'Mhs {tahun_lalu}',
            tahun_sekarang: f'Mhs {tahun_sekarang}'
        })
        
        # Pisah menjadi Growing dan Declining
        df_growing = df_final.sort_values(by='Delta (Angka)', ascending=False).reset_index(drop=True)
        df_growing.insert(0, 'No.', df_growing.index + 1)
        
        df_declining = df_final.sort_values(by='Delta (Angka)', ascending=True).reset_index(drop=True)
        df_declining.insert(0, 'No.', df_declining.index + 1)
        
        col_kiri, col_kanan = st.columns(2)
        
        format_dict = {
            f'Mhs {tahun_lalu}': "{:,.0f}",
            f'Mhs {tahun_sekarang}': "{:,.0f}",
            'Delta (Angka)': "{:+,.0f}",
            'Delta (%)': "{:+.1f}%"
        }
        
        with col_kiri:
            st.markdown(f"**📈 Top Pertumbuhan Kampus (Growing)**")
            st.dataframe(
                df_growing.style.format(format_dict).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Delta (Angka)', 'Delta (%)']),
                hide_index=True,
                height=700,
                use_container_width=True
            )
            
        with col_kanan:
            st.markdown(f"**📉 Top Penurunan Kampus (Declining)**")
            st.dataframe(
                df_declining.style.format(format_dict).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Delta (Angka)', 'Delta (%)']),
                hide_index=True,
                height=700,
                use_container_width=True
            )

# ---------------------------------------------------------
# MENU 10: ANALISIS MAHASISWA BARU
# ---------------------------------------------------------
elif menu == "🎓 Analisis Mahasiswa Baru":
    st.title("🎓 Analisis Mahasiswa Baru (Maba)")
    st.markdown("Pantau dinamika pendaftaran mahasiswa baru secara nasional maupun per provinsi, dan pelajari pergeseran dominasi antara Perguruan Tinggi Negeri (PTN) vs Swasta (PTS).")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Filter Geografis")
    
    # Filter Provinsi
    list_provinsi = ["Semua (Nasional)"] + sorted([str(p) for p in df_maba['province_name'].unique() if p != 'TOTAL NASIONAL'])
    selected_provinsi = st.sidebar.selectbox("Pilih Provinsi", list_provinsi)
    
    min_year_maba = int(df_maba['start_year'].min())
    max_year_maba = int(df_maba['start_year'].max())
    tahun_awal, tahun_akhir = st.sidebar.slider("Rentang Tahun Perbandingan", min_value=min_year_maba, max_value=max_year_maba, value=(max_year_maba-1, max_year_maba))
    
    # Menyiapkan data
    if selected_provinsi == "Semua (Nasional)":
        df_chart = df_maba[df_maba['is_national_total'] == 1].copy()
        judul_wilayah = "Tingkat Nasional"
    else:
        df_chart = df_maba[df_maba['province_name'] == selected_provinsi].copy()
        judul_wilayah = f"Provinsi {selected_provinsi}"
        
    st.write("---")
    
    # 1. Tren Pendaftaran Maba Nasional
    st.subheader(f"📈 Tren Penerimaan Mahasiswa Baru ({judul_wilayah})")
    
    if not df_chart.empty:
        # Plotly Line Chart
        fig_tren = px.line(df_chart, x='year_label', y=['jumlah', 'negeri', 'swasta'], markers=True, 
                           line_shape='linear', title=f"Dinamika Maba PTN vs PTS", height=700)
        fig_tren.update_traces(line_width=4, marker_size=10)
        
        # Rapikan legend
        newnames = {'jumlah': 'Total (Negeri + Swasta)', 'negeri': 'PTN (Negeri)', 'swasta': 'PTS (Swasta)'}
        fig_tren.for_each_trace(lambda t: t.update(name = newnames.get(t.name, t.name),
                                                   legendgroup = newnames.get(t.name, t.name),
                                                   hovertemplate = t.hovertemplate.replace(t.name, newnames.get(t.name, t.name))
                                                  ))
                                                  
        fig_tren.update_layout(xaxis_title="Tahun Ajaran", yaxis_title="Jumlah Mahasiswa Baru", legend_title_text="Kategori")
        st.plotly_chart(fig_tren, use_container_width=True)
        
        # 2. Komposisi PTN vs PTS
        st.write("---")
        st.subheader(f"⚖️ Komposisi Pendaftar: Negeri vs Swasta ({judul_wilayah})")
        
        # Melt df_chart for Stacked Bar Chart
        df_komposisi = df_chart[['year_label', 'negeri', 'swasta']].melt(id_vars='year_label', var_name='Tipe PT', value_name='Jumlah Maba')
        df_komposisi['Tipe PT'] = df_komposisi['Tipe PT'].str.title()
        
        fig_bar = px.bar(df_komposisi, x='year_label', y='Jumlah Maba', color='Tipe PT',
                         title="Distribusi Maba PTN vs PTS", text_auto='.2s',
                         color_discrete_map={'Negeri': '#3b82f6', 'Swasta': '#f59e0b'})
        fig_bar.update_layout(xaxis_title="Tahun Ajaran", yaxis_title="Jumlah Mahasiswa Baru", barmode='stack')
        st.plotly_chart(fig_bar, use_container_width=True)
        
        # Tabel Detail Pertumbuhan PTN vs PTS
        st.write("---")
        st.markdown(f"### 📊 Detail Pertumbuhan Maba (PTN vs PTS)")
        df_tabel_komposisi = df_chart[['year_label', 'negeri', 'swasta']].copy()
        
        # Kalkulasi
        df_tabel_komposisi['Delta PTN'] = df_tabel_komposisi['negeri'].diff()
        df_tabel_komposisi['Pertumbuhan PTN (%)'] = df_tabel_komposisi['negeri'].pct_change() * 100
        df_tabel_komposisi['Delta PTS'] = df_tabel_komposisi['swasta'].diff()
        df_tabel_komposisi['Pertumbuhan PTS (%)'] = df_tabel_komposisi['swasta'].pct_change() * 100
        
        df_tabel_komposisi = df_tabel_komposisi.fillna(0)
        
        col_ptn, col_pts = st.columns(2)
        format_dict_komp = {
            'Jumlah': "{:,.0f}",
            'Pertumbuhan (Angka)': "{:+,.0f}",
            'Pertumbuhan (%)': "{:+.2f}%"
        }
        
        with col_ptn:
            st.markdown("**🎓 Perguruan Tinggi Negeri (PTN)**")
            df_ptn = df_tabel_komposisi[['year_label', 'negeri', 'Delta PTN', 'Pertumbuhan PTN (%)']].rename(columns={
                'year_label': 'Tahun Ajaran',
                'negeri': 'Jumlah',
                'Delta PTN': 'Pertumbuhan (Angka)',
                'Pertumbuhan PTN (%)': 'Pertumbuhan (%)'
            })
            st.dataframe(
                df_ptn.style.format(format_dict_komp).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Pertumbuhan (Angka)', 'Pertumbuhan (%)']),
                hide_index=True,
                use_container_width=True
            )
            
        with col_pts:
            st.markdown("**🏫 Perguruan Tinggi Swasta (PTS)**")
            df_pts = df_tabel_komposisi[['year_label', 'swasta', 'Delta PTS', 'Pertumbuhan PTS (%)']].rename(columns={
                'year_label': 'Tahun Ajaran',
                'swasta': 'Jumlah',
                'Delta PTS': 'Pertumbuhan (Angka)',
                'Pertumbuhan PTS (%)': 'Pertumbuhan (%)'
            })
            st.dataframe(
                df_pts.style.format(format_dict_komp).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Pertumbuhan (Angka)', 'Pertumbuhan (%)']),
                hide_index=True,
                use_container_width=True
            )
            
    else:
        st.warning("Data tidak tersedia untuk wilayah ini.")
        
    st.write("---")
    
    # 3. Analisis Kinerja Pertumbuhan (Provinsi Level)
    if selected_provinsi == "Semua (Nasional)":
        st.subheader("🗺️ Peta Kinerja Seluruh Provinsi")
        st.markdown("Menganalisis pertumbuhan absolut dan persentase penerimaan mahasiswa baru di seluruh provinsi Indonesia berdasarkan rentang tahun pilihan Anda.")
        
        # Aggregate and Pivot df_maba
        df_prov_agg = df_maba[df_maba['is_national_total'] == 0].groupby(['province_name', 'start_year'])['jumlah'].sum().reset_index()
        df_prov_pivot = df_prov_agg.pivot_table(index='province_name', columns='start_year', values='jumlah', fill_value=0).reset_index()
        
        if tahun_akhir not in df_prov_pivot.columns: df_prov_pivot[tahun_akhir] = 0
        if tahun_awal not in df_prov_pivot.columns: df_prov_pivot[tahun_awal] = 0
            
        df_prov_pivot['Pertumbuhan (Angka)'] = df_prov_pivot[tahun_akhir] - df_prov_pivot[tahun_awal]
        df_prov_pivot['Pertumbuhan (%)'] = np.where(df_prov_pivot[tahun_awal] > 0, 
                                                (df_prov_pivot['Pertumbuhan (Angka)'] / df_prov_pivot[tahun_awal]) * 100, 
                                                0.0)
                                                
        cols_to_show = ['province_name', tahun_awal, tahun_akhir, 'Pertumbuhan (Angka)', 'Pertumbuhan (%)']
        df_final_maba = df_prov_pivot[cols_to_show].rename(columns={
            'province_name': 'Provinsi',
            tahun_awal: f'Maba {tahun_awal}',
            tahun_akhir: f'Maba {tahun_akhir}'
        })
        
        # Pisahkan Growing dan Declining (Semua Provinsi)
        df_maba_growing = df_final_maba.sort_values(by='Pertumbuhan (Angka)', ascending=False).reset_index(drop=True)
        df_maba_growing.insert(0, 'Peringkat', df_maba_growing.index + 1)
        
        df_maba_declining = df_final_maba.sort_values(by='Pertumbuhan (Angka)', ascending=True).reset_index(drop=True)
        df_maba_declining.insert(0, 'Peringkat', df_maba_declining.index + 1)
        
        col_kiri, col_kanan = st.columns(2)
        
        format_dict_maba = {
            f'Maba {tahun_awal}': "{:,.0f}",
            f'Maba {tahun_akhir}': "{:,.0f}",
            'Pertumbuhan (Angka)': "{:+,.0f}",
            'Pertumbuhan (%)': "{:+.2f}%"
        }
        
        with col_kiri:
            st.markdown(f"**🔥 Provinsi dengan Pertumbuhan Maba Teratas**")
            st.dataframe(
                df_maba_growing.style.format(format_dict_maba).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Pertumbuhan (Angka)', 'Pertumbuhan (%)']),
                hide_index=True,
                use_container_width=True,
                height=700
            )
            
        with col_kanan:
            st.markdown(f"**❄️ Provinsi dengan Penurunan Maba Terparah**")
            st.dataframe(
                df_maba_declining.style.format(format_dict_maba).map(lambda x: 'color: #059669; font-weight: bold;' if x > 0 else ('color: #dc2626; font-weight: bold;' if x < 0 else ''), subset=['Pertumbuhan (Angka)', 'Pertumbuhan (%)']),
                hide_index=True,
                use_container_width=True,
                height=700
            )
