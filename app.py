import streamlit as st
import sqlite3
import re
import pandas as pd

# Configurazione della pagina
st.set_page_config(page_title="Torneo di Biliardino Live", page_icon="⚽", layout="centered")

# --- DATABASE SETUP ---
DB_NAME = "biliardino.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS coppie (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        girone TEXT,
        punti INTEGER DEFAULT 0,
        partite_giocate INTEGER DEFAULT 0,
        gol_fatti INTEGER DEFAULT 0,
        gol_subiti INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS partite (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fase TEXT DEFAULT 'girone',
        girone TEXT,
        coppia1_id INTEGER,
        coppia2_id INTEGER,
        gol1 INTEGER,
        gol2 INTEGER,
        stato TEXT DEFAULT 'da_giocare',
        biliardino INTEGER
    )''')
    conn.commit()
    conn.close()

init_db()

def get_config():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM config").fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def set_config(key, value):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# --- HEADER PRINCIPALE ---
st.title("⚽ Torneo di Biliardino Live")
st.markdown("Gestione gironi, biliardini, live in tempo reale e fase a eliminazione diretta.")

menu = st.sidebar.radio("Scegli Sezione:", ["🏠 Home", "⚙️ Area Admin (PIN 0000)", "👥 Area Giocatore (Live)"])

# ==========================================
# 1. HOME
# ==========================================
if menu == "🏠 Home":
    st.subheader("Benvenuti al portale del torneo!")
    st.write("Da qui puoi accedere come amministratore per configurare il torneo e inserire le coppie, oppure entrare come giocatore per seguire la live e inserire i risultati.")
    
    config = get_config()
    stato = config.get('stato_torneo', 'Non iniziato')
    st.info(f"Stato attuale del torneo: **{stato.upper()}**")

# ==========================================
# 2. AREA ADMIN
# ==========================================
elif menu == "⚙️ Area Admin (PIN 0000)":
    st.subheader("🔐 Pannello di Controllo Admin")
    
    pin_inserito = st.text_input("Inserisci PIN Admin (0000):", type="password")
    
    if pin_inserito == "0000":
        st.success("Accesso effettuato con successo!")
        
        config = get_config()
        
        st.markdown("---")
        st.subheader("1. Configurazione Iniziale e Coppie")
        
        with st.form("form_setup"):
            num_biliardini = st.number_input("Numero di Biliardini (Campi da gioco):", min_value=1, max_value=10, value=int(config.get('num_biliardini', 2)))
            num_gironi = st.number_input("Numero di Gironi:", min_value=1, max_value=6, value=int(config.get('num_gironi', 3)))
            passano_tot = st.number_input("Numero totale coppie che passano alla fase finale:", min_value=2, max_value=32, value=int(config.get('passano_tot', 8)))
            
            coppie_testo_default = "1. Andrea e Paolo\n2. Antonio e Franco\n3. Luca e Marco\n4. Giovanni e Stefano\n5. Davide e Matteo"
            coppie_text = st.text_area("Incolla qui la lista delle coppie (es. da WhatsApp):", value=config.get('ultimo_testo', coppie_testo_default), height=150)
            
            submit_setup = st.form_submit_button("Salva e Avvia Torneo")
            
            if submit_setup:
                set_config('num_biliardini', num_biliardini)
                set_config('num_gironi', num_gironi)
                set_config('passano_tot', passano_tot)
                set_config('stato_torneo', 'gironi')
                set_config('ultimo_testo', coppie_text)
                
                conn = get_connection()
                conn.execute("DELETE FROM coppie")
                conn.execute("DELETE FROM partite")
                conn.commit()
                
                righe = coppie_text.split('\n')
                coppie_nomi = []
                for riga in righe:
                    riga_pulita = re.sub(r'^\d+[\.\)]\s*', '', riga).strip()
                    if riga_pulita and "torneo" not in riga_pulita.lower():
                        coppie_nomi.append(riga_pulita)
                
                nomi_gironi = [chr(65 + i) for i in range(num_gironi)]
                for idx, nome_coppia in enumerate(coppie_nomi):
                    girone_assegnato = nomi_gironi[idx % num_gironi]
                    conn.execute("INSERT INTO coppie (nome, girone) VALUES (?, ?)", (nome_coppia, girone_assegnato))
                conn.commit()
                
                for g in nomi_gironi:
                    squadre = conn.execute("SELECT id FROM coppie WHERE girone = ?", (g,)).fetchall()
                    s_ids = [s['id'] for s in squadre]
                    if len(s_ids) % 2 == 1:
                        s_ids.append(None)
                    n = len(s_ids)
                    
                    for turno in range(n - 1):
                        for i in range(n // 2):
                            s1 = s_ids[i]
                            s2 = s_ids[n - 1 - i]
                            if s1 is not None and s2 is not None:
                                conn.execute("INSERT INTO partite (fase, girone, coppia1_id, coppia2_id, stato) VALUES ('girone', ?, ?, ?, 'da_giocare')", (g, s1, s2))
                        s_ids.insert(1, s_ids.pop())
                conn.commit()
                
                def assegna_iniziali():
                    libere = conn.execute("SELECT id FROM partite WHERE stato = 'da_giocare' LIMIT ?", (num_biliardini,)).fetchall()
                    for idx, p in enumerate(libere):
                        conn.execute("UPDATE partite SET stato = 'in_corso', biliardino = ? WHERE id = ?", (idx + 1, p['id']))
                    conn.commit()
                assegna_iniziali()
                conn.close()
                
                st.success("Torneo avviato con successo e gironi generati!")
                st.rerun()

        st.markdown("---")
        st.subheader("📋 Stato Attuale delle Partite e dei Biliardini")
        conn = get_connection()
        partite = conn.execute("""
            SELECT p.*, c1.nome as squadra1, c2.nome as squadra2 
            FROM partite p
            LEFT JOIN coppie c1 ON p.coppia1_id = c1.id
            LEFT JOIN coppie c2 ON p.coppia2_id = c2.id
        """).fetchall()
        conn.close()
        
        if partite:
            df_part = pd.DataFrame([dict(p) for p in partite])
            st.dataframe(df_part[['id', 'stato', 'biliardino', 'squadra1', 'squadra2', 'gol1', 'gol2']], use_container_width=True)
        else:
            st.write("Nessuna partita generata. Configura le coppie sopra per iniziare.")

    elif pin_inserito != "":
        st.error("PIN errato! Il PIN corretto è 0000.")

# ==========================================
# 3. AREA GIOCATORE (LIVE)
# ==========================================
elif menu == "👥 Area Giocatore (Live)":
    st.subheader("📱 Live del Torneo - Scegli la tua Coppia")
    
    conn = get_connection()
    coppie = conn.execute("SELECT * FROM coppie ORDER BY nome").fetchall()
    conn.close()
    
    if not coppie:
        st.warning("Il torneo non è ancora stato avviato dall'amministratore.")
    else:
        scelta_coppia = st.selectbox("Seleziona la tua coppia:", options=coppie, format_func=lambda x: f"{x['nome']} (Girone {x['girone']})")
        
        if scelta_coppia:
            coppia_id = scelta_coppia['id']
            
            conn = get_connection()
            c_data = conn.execute("SELECT * FROM coppie WHERE id = ?", (coppia_id,)).fetchone()
            girone = c_data['girone']
            
            classifica = conn.execute("""
                SELECT * FROM coppie WHERE girone = ? 
                ORDER BY punti DESC, (gol_fatti - gol_subiti) DESC, gol_fatti DESC
            """, (girone,)).fetchall()
            
            pos = 1
            for idx, c in enumerate(classifica):
                if c['id'] == coppia_id:
                    pos = idx + 1
                    break
            
            match_corrente = conn.execute("""
                SELECT p.*, c1.nome as squadra1, c2.nome as squadra2 
                FROM partite p
                LEFT JOIN coppie c1 ON p.coppia1_id = c1.id
                LEFT JOIN coppie c2 ON p.coppia2_id = c2.id
                WHERE (p.coppia1_id = ? OR p.coppia2_id = ?) AND p.stato = 'in_corso'
            """, (coppia_id, coppia_id)).fetchone()
            
            partite_attesa = conn.execute("""
                SELECT p.*, c1.nome as squadra1, c2.nome as squadra2 
                FROM partite p
                LEFT JOIN coppie c1 ON p.coppia1_id = c1.id
                LEFT JOIN coppie c2 ON p.coppia2_id = c2.id
                WHERE (p.coppia1_id = ? OR p.coppia2_id = ?) AND p.stato = 'da_giocare'
            """, (coppia_id, coppia_id)).fetchall()
            conn.close()
            
            st.markdown(f"### Coppia: {c_data['nome']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Girone", girone)
            col2.metric("Posizione", f"{pos}°")
            col3.metric("Punti", c_data['punti'])
            col4.metric("Giocate", c_data['partite_giocate'])
            
            st.markdown("---")
            
            if match_corrente:
                st.markdown(f"### 🔥 PARTITA IN CORSO AL BILIARDINO {match_corrente['biliardino']}!")
                avv = match_corrente['squadra2'] if match_corrente['coppia1_id'] == coppia_id else match_corrente['squadra1']
                st.write(f"Stai giocando contro: **{avv}**")
                
                with st.form("form_risultato"):
                    st.write("Inserisci il risultato finale della partita:")
                    g1_in = st.number_input(f"Gol {match_corrente['squadra1']}", min_value=0, max_value=20, value=0)
                    g2_in = st.number_input(f"Gol {match_corrente['squadra2']}", min_value=0, max_value=20, value=0)
                    
                    invia_res = st.form_submit_button("Registra Risultato")
                    
                    if invia_res:
                        conn = get_connection()
                        if match_corrente['coppia1_id'] == coppia_id:
                            miei = g1_in
                            avv_gol = g2_in
                        else:
                            miei = g2_in
                            avv_gol = g1_in
                            
                        scarto = abs(miei - avv_gol)
                        
                        p1, p2 = 0, 0
                        if g1_in > g2_in:
                            p1 = 3 if scarto >= 2 else 2
                            p2 = 1 if scarto == 1 else 0
                        else:
                            p2 = 3 if scarto >= 2 else 2
                            p1 = 1 if scarto == 1 else 0
                            
                        conn.execute("UPDATE partite SET gol1 = ?, gol2 = ?, stato = 'completata', biliardino = NULL WHERE id = ?", (g1_in, g2_in, match_corrente['id']))
                        
                        conn.execute("UPDATE coppie SET punti = punti + ?, partite_giocate = partite_giocate + 1, gol_fatti = gol_fatti + ?, gol_subiti = gol_subiti + ? WHERE id = ?", 
                                     (p1, g1_in, g2_in, match_corrente['coppia1_id']))
                        conn.execute("UPDATE coppie SET punti = punti + ?, partite_giocate = partite_giocate + 1, gol_fatti = gol_fatti + ?, gol_subiti = gol_subiti + ? WHERE id = ?", 
                                     (p2, g2_in, g1_in, match_corrente['coppia2_id']))
                        
                        config = get_config()
                        num_bil = int(config.get('num_biliardini', 2))
                        
                        prossima = conn.execute("SELECT id FROM partite WHERE stato = 'da_giocare' LIMIT 1").fetchone()
                        if prossima:
                            occupati = [p['biliardino'] for p in conn.execute("SELECT biliardino FROM partite WHERE stato = 'in_corso'").fetchall() if p['biliardino']]
                            libero = 1
                            while libero in occupati:
                                libero += 1
                            if libero <= num_bil:
                                conn.execute("UPDATE partite SET stato = 'in_corso', biliardino = ? WHERE id = ?", (libero, prossima['id']))
                                
                        conn.commit()
                        conn.close()
                        st.success("Risultato salvato con successo!")
                        st.rerun()
            else:
                st.info("Al momento non hai partite in corso sul biliardino.")
                
            st.markdown("#### ⏳ Le tue prossime partite in coda:")
            if partite_attesa:
                for m in partite_attesa:
                    st.write(f"- {m['squadra1']} vs {m['squadra2']} (In attesa)")
            else:
                st.write("Hai completato tutte le partite dei gironi!")
                
            st.markdown(f"#### 🏆 Classifica Girone {girone}")
            df_class = pd.DataFrame([dict(c) for c in classifica])
            df_class['diff_reti'] = df_class['gol_fatti'] - df_class['gol_subiti']
            st.dataframe(df_class[['nome', 'punti', 'partite_giocate', 'diff_reti', 'gol_fatti']], use_container_width=True)
