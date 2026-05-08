import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
import time as t_sleep
import pymysql

# --- 1. CONFIGURACIÓN DE CONEXIÓN ---
def conectar_db():
    return pymysql.connect(
        host="gateway01.us-east-1.prod.aws.tidbcloud.com",
        port=4000,
        user="469gCJra1a7NKDL.root",
        password="5EuBdxr4tEuzvzMp",
        database="psical_db",
        autocommit=True,
        ssl={'ca': '/etc/ssl/certs/ca-certificates.crt'}
    )

# --- 2. FUNCIONES DE LÓGICA ---
def obtener_pacientes():
    try:
        conn = conectar_db()
        df = pd.read_sql("SELECT id_paciente, nombre, IFNULL(cedula, 'S/N') as cedula FROM pacientes", conn)
        conn.close()
        return df
    except: return pd.DataFrame(columns=['id_paciente', 'nombre', 'cedula'])

def verificar_disponibilidad(fecha, h_i, h_f):
    conn = conectar_db()
    query = f"SELECT id_cita FROM citas WHERE fecha='{fecha}' AND estado!='Cancelada'"
    df = pd.read_sql(query, conn)
    conn.close()
    return df.empty # Simplificado para el ejemplo, mantén tu lógica de traslape si la tienes

# --- 3. CONTROL DE SESIÓN ---
if "rol" not in st.session_state: st.session_state.rol = None
if "usuario_nom" not in st.session_state: st.session_state.usuario_nom = ""

if st.session_state.rol is None:
    st.title("🧠 Psical: Acceso")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar"):
            # Lógica de login aquí...
            st.session_state.rol = "Admin" # Ejemplo
            st.session_state.usuario_nom = u
            st.rerun()
    st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("📌 Menú Psical")
    st.write(f"Usuario: **{st.session_state.usuario_nom}**")
    opciones = ["Agenda Diaria", "Agendar Cita", "Pacientes y Expedientes"]
    if st.session_state.rol == "Admin": opciones.append("Panel Admin")
    menu = st.radio("Ir a:", opciones)

# --- 5. MÓDULO: AGENDA DIARIA (RESTAURADO SEGÚN TU CAPTURA) ---
if menu == "Agenda Diaria":
    st.subheader("📋 Control Operativo del Día")
    fecha_agenda = st.date_input("Ver día:", value=datetime.now())
    
    conn = conectar_db()
    query = f"""
        SELECT c.id_cita, c.hora_inicio, c.hora_fin, p.nombre, p.cedula, c.estado 
        FROM citas c JOIN pacientes p ON c.id_paciente = p.id_paciente 
        WHERE c.fecha = '{fecha_agenda}' ORDER BY c.hora_inicio ASC
    """
    df_citas = pd.read_sql(query, conn)
    conn.close()

    # --- MAPA DE DISPONIBILIDAD (Lo que se veía en tu imagen) ---
    st.write("### 🕒 Mapa de Disponibilidad")
    horas_dia = pd.date_range(start="07:00", end="17:00", freq="30min").time
    cols = st.columns(6)
    
    for i, h in enumerate(horas_dia):
        # Lógica para verificar si la hora está ocupada
        is_ocupado = any((row['hora_inicio'] <= h < row['hora_fin']) for _, row in df_citas.iterrows() if row['estado'] != 'Cancelada')
        
        with cols[i % 6]:
            if is_ocupado:
                st.error(f"{h.strftime('%H:%M')}")
            else:
                st.success(f"{h.strftime('%H:%M')}")

    st.divider()
    st.write("### ⏳ Horarios Reservados")
    for _, row in df_citas.iterrows():
        if row['estado'] != 'Cancelada':
            st.warning(f"**Ocupado de {row['hora_inicio']} a {row['hora_f']}** | Paciente: {row['nombre']}")

    st.divider()
    st.write("### 📝 Detalle y Asistencia")
    for _, row in df_citas.iterrows():
        with st.expander(f"⏰ {row['hora_inicio']} - {row['hora_fin']} | 👤 {row['nombre']} ({row['estado']})"):
            # Aquí irían tus botones de "Asistió", "Canceló", etc.
            st.write(f"Cédula: {row['cedula']}")

# --- LOS DEMÁS MÓDULOS (Agendar, Pacientes) SIGUEN AQUÍ ---

elif menu == "Agendar Cita":
    st.subheader("📅 Programar Sesión")
    df_p = obtener_pacientes()
    if df_p.empty: st.warning("Crea un paciente primero.")
    else:
        with st.form("form_agendar"):
            p_id = st.selectbox("Paciente", options=df_p['id_paciente'].tolist(),
                               format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}")
            c1, c2, c3 = st.columns(3)
            fecha = c1.date_input("Fecha")
            h_i = c2.time_input("Inicio", value=time(7,0))
            h_f = c3.time_input("Fin", value=time(7,30))
            if st.form_submit_button("Confirmar Cita"):
                if h_i < h_f and verificar_disponibilidad(fecha, h_i, h_f):
                    conn = conectar_db(); cursor = conn.cursor()
                    cursor.execute("INSERT INTO citas (id_paciente, fecha, hora_inicio, hora_fin) VALUES (%s,%s,%s,%s)", (p_id, fecha, h_i, h_f))
                    st.success("✅ Cita guardada!"); st.balloons(); t_sleep.sleep(1); st.rerun()
                else: st.error("Horario no disponible o inválido.")

elif menu == "Pacientes y Expedientes":
    st.subheader("🏥 Expediente Clínico")
    t1, t2, t3 = st.tabs(["Registrar Paciente", "Historial", "Nueva Evaluación"])
    with t1:
        with st.form("reg_p"):
            n = st.text_input("Nombre Completo"); id_c = st.text_input("Cédula")
            t = st.text_input("Teléfono"); m = st.text_input("Correo")
            r = st.text_area("Antecedentes")
            if st.form_submit_button("Guardar"):
                conn = conectar_db(); cursor = conn.cursor()
                cursor.execute("INSERT INTO pacientes (nombre, cedula, telefono, correo, referencia) VALUES (%s,%s,%s,%s,%s)", (n, id_c, t, m, r))
                st.success("Paciente registrado.")
    with t2:
        df_p = obtener_pacientes()
        p_sel = st.selectbox("Paciente:", options=df_p['id_paciente'].tolist(), format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}", key="h1")
        df_h = pd.read_sql(f"SELECT * FROM historiales WHERE id_paciente={p_sel} ORDER BY fecha DESC", conectar_db())
        for _, row in df_h.iterrows():
            with st.expander(f"📅 Sesión: {row['fecha']}"):
                st.write(f"**Motivo:** {row['sintomas']}")
                st.write(f"**Evolución:** {row['diagnostico']}")
    with t3:
        df_p = obtener_pacientes()
        p_id = st.selectbox("Paciente:", options=df_p['id_paciente'].tolist(), format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}", key="e1")
        conn = conectar_db()
        c_libres = pd.read_sql(f"SELECT id_cita, fecha FROM citas WHERE id_paciente={p_id} AND estado='Asistió' AND id_cita NOT IN (SELECT id_cita FROM historiales)", conn)
        if c_libres.empty: st.info("Sin sesiones pendientes de informe.")
        else:
            with st.form("f_eval"):
                cita_sel = st.selectbox("Sesión:", options=c_libres['id_cita'].tolist(), format_func=lambda x: f"Fecha: {c_libres[c_libres['id_cita']==x]['fecha'].values[0]}")
                col1, col2 = st.columns(2)
                animo = col1.selectbox("Ánimo", ["Eutímico", "Ansioso", "Bajo", "Irritable"])
                riesgo = col2.selectbox("Riesgo", ["Nulo", "Bajo", "Moderado", "Alto"])
                motivo = st.text_area("Notas del Paciente")
                evolucion = st.text_area("Impresión Clínica")
                if st.form_submit_button("Guardar Evolución"):
                    f_c = str(c_libres[c_libres['id_cita']==cita_sel]['fecha'].values[0])
                    cursor = conn.cursor()
                    sql = "INSERT INTO historiales (id_paciente, id_cita, fecha, estado_animo, riesgo_valoracion, sintomas, diagnostico) VALUES (%s,%s,%s,%s,%s,%s,%s)"
                    cursor.execute(sql, (p_id, cita_sel, f_c, animo, riesgo, motivo, evolucion))
                    st.success("✅ Guardado."); t_sleep.sleep(1); st.rerun()
        conn.close()
