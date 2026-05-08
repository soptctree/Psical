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

# --- 2. FUNCIONES DE APOYO (DEFINIR ANTES DE USAR) ---
def validar_login(usuario, clave):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        sql = "SELECT rol FROM usuarios WHERE username = %s AND password = %s"
        cursor.execute(sql, (usuario, clave))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    except Exception as e:
        st.error(f"Error en login: {e}")
        return None
    finally:
        if 'conn' in locals() and conn: conn.close()

def obtener_pacientes():
    try:
        conn = conectar_db()
        df = pd.read_sql("SELECT id_paciente, nombre, IFNULL(cedula, 'S/N') as cedula FROM pacientes", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=['id_paciente', 'nombre', 'cedula'])

def verificar_disponibilidad(fecha, h_inicio, h_fin):
    try:
        conn = conectar_db()
        query = f"""
        SELECT id_cita FROM citas WHERE fecha = '{fecha}' AND estado != 'Cancelada'
        AND (('{h_inicio}' >= hora_inicio AND '{h_inicio}' < hora_fin) OR
             ('{h_fin}' > hora_inicio AND '{h_fin}' <= hora_fin) OR
             (hora_inicio >= '{h_inicio}' AND hora_inicio < '{h_fin}'))
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df.empty
    except: return False

# --- 3. MÓDULOS ESPECÍFICOS ---
def modulo_admin_usuarios():
    st.title("⚙️ Panel de Administración Maestro")
    st.info(f"Sesión iniciada como: {st.session_state.usuario_nom} (Administrador)")
    conn = conectar_db()
    try:
        st.write("### 👥 Usuarios en el Sistema")
        df_users = pd.read_sql("SELECT id_usuario, username, rol FROM usuarios", conn)
        st.dataframe(df_users, use_container_width=True)
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.write("### ➕ Registrar Nuevo")
            with st.form("nuevo_user_form"):
                n_user = st.text_input("Nombre de Usuario:")
                n_pass = st.text_input("Contraseña:", type="password")
                n_rol = st.selectbox("Asignar Rol:", ["Psicologo", "Admin"])
                if st.form_submit_button("Crear Cuenta"):
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s)", (n_user, n_pass, n_rol))
                    st.success("Usuario creado."); st.rerun()
        with col2:
            st.write("### 🔑 Resetear Clave")
            with st.form("reset_pass_form"):
                user_sel = st.selectbox("Usuario:", options=df_users['username'].tolist())
                new_pass = st.text_input("Nueva Contraseña:", type="password")
                if st.form_submit_button("Actualizar"):
                    cursor = conn.cursor()
                    cursor.execute("UPDATE usuarios SET password = %s WHERE username = %s", (new_pass, user_sel))
                    st.success("Clave actualizada.")
    except Exception as e: st.error(f"Error: {e}")
    finally: conn.close()

# --- 4. CONTROL DE SESIÓN ---
if "rol" not in st.session_state: st.session_state.rol = None
if "usuario_nom" not in st.session_state: st.session_state.usuario_nom = ""

if st.session_state.rol is None:
    st.title("🧠 Psical: Acceso")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar al Sistema"):
            rol_encontrado = validar_login(u, p)
            if rol_encontrado:
                st.session_state.rol = rol_encontrado
                st.session_state.usuario_nom = u
                st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. NAVEGACIÓN (SIDEBAR) ---
with st.sidebar:
    st.title("📌 Menú Psical")
    st.write(f"Usuario: **{st.session_state.usuario_nom}**")
    opciones = ["Agenda Diaria", "Agendar Cita", "Pacientes y Expedientes"]
    if st.session_state.rol == "Admin": opciones.append("Panel Admin")
    menu = st.radio("Ir a:", opciones)
    st.divider()
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.rol = None
        st.rerun()

# --- 6. LÓGICA DE MÓDULOS ---
if menu == "Panel Admin":
    modulo_admin_usuarios()

elif menu == "Agenda Diaria":
    st.subheader("📋 Control Operativo del Día")
    fecha_agenda = st.date_input("Ver día:", value=datetime.now())
    conn = conectar_db()
    query = f"""
        SELECT c.id_cita, c.hora_inicio, c.hora_fin, p.nombre, c.estado 
        FROM citas c JOIN pacientes p ON c.id_paciente = p.id_paciente 
        WHERE c.fecha = '{fecha_agenda}' ORDER BY c.hora_inicio ASC
    """
    df_agenda = pd.read_sql(query, conn)
    st.dataframe(df_agenda, use_container_width=True)
    conn.close()

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
