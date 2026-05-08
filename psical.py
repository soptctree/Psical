import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pymysql

# --- CONFIGURACIÓN DE CONEXIÓN ---
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

def validar_login(usuario, clave):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        sql = "SELECT rol FROM usuarios WHERE username = %s AND password = %s"
        cursor.execute(sql, (usuario, clave))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0] # Retorna el Rol
        return None
    except Exception as e:
        st.error(f"Error en login: {e}")
        return None
    finally:
        if 'conn' in locals() and conn:
            conn.close()

# --- CONTROL DE SESIÓN ---
if "rol" not in st.session_state:
    st.session_state.rol = None
if "usuario_nom" not in st.session_state:
    st.session_state.usuario_nom = ""

# --- PANTALLA DE LOGIN ---
if st.session_state.rol is None:
    st.title("🧠 Psical: Acceso")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar al Sistema"):
            rol_encontrado = validar_login(u, p)
            if rol_encontrado:
                st.session_state.rol = rol_encontrado
                st.session_state.usuario_nom = u  # Guardamos el nombre para el panel admin
                st.success(f"Bienvenido {u}")
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- FUNCIONES DE MÓDULOS ---
def modulo_admin_usuarios():
    st.title("⚙️ Panel de Administración Maestro")
    st.info(f"Sesión iniciada como: {st.session_state.usuario_nom} (Administrador)")
    # ... (aquí va el resto de tu código de gestión de usuarios que ya tienes) ...

# --- NAVEGACIÓN UNIFICADA (BARRA LATERAL) ---
with st.sidebar:
    st.title("📌 Menú Psical")
    st.write(f"Usuario: **{st.session_state.usuario_nom}**")
    
    # Opciones básicas para todos
    opciones = ["Agenda Diaria", "Agendar Cita", "Pacientes y Expedientes"]
    
    # Si es Admin, agregamos la opción extra
    if st.session_state.rol == "Admin":
        opciones.append("Panel Admin")
    
    menu = st.radio("Ir a:", opciones)
    
    st.divider()
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.rol = None
        st.session_state.usuario_nom = ""
        st.rerun()

# --- LÓGICA DE VISUALIZACIÓN DE MÓDULOS ---
if menu == "Panel Admin":
    modulo_admin_usuarios()

# --- MÓDULO 2: AGENDAR CITA ---
elif menu == "Agendar Cita":
    st.subheader("📅 Programar Sesión")
    df_p = obtener_pacientes()
    if df_p.empty: st.warning("Crea un paciente primero.")
    else:
        with st.form("form_agendar", clear_on_submit=True):
            p_id = st.selectbox("Paciente", options=df_p['id_paciente'].tolist(),
                               format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}")
            c1, c2, c3 = st.columns(3)
            fecha = c1.date_input("Fecha")
            h_i = c2.time_input("Inicio", value=time(7,0))
            h_f = c3.time_input("Fin", value=time(7,30))
            
            if st.form_submit_button("Confirmar Cita"):
                if h_i >= h_f: st.error("La hora de fin debe ser posterior.")
                elif verificar_disponibilidad(fecha, h_i, h_f):
                    conn = conectar_db(); cursor = conn.cursor()
                    cursor.execute("INSERT INTO citas (id_paciente, fecha, hora_inicio, hora_fin) VALUES (%s,%s,%s,%s)", (p_id, fecha, h_i, h_f))
                    conn.commit(); conn.close()
                    st.success("✅ ¡Cita guardada!"); st.balloons()
                    t_sleep.sleep(1.5); st.rerun()
                else: st.error("❌ Horario ocupado.")

# --- MÓDULO 3: PACIENTES Y EXPEDIENTES ---
elif menu == "Pacientes y Expedientes":
    st.subheader("🏥 Expediente Clínico")
    tab1, tab2, tab3 = st.tabs(["Registrar Paciente", "Historial Médico", "Nueva Consulta"])

    with tab1:
        with st.form("reg_p"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nombre Completo")
            id_c = c2.text_input("Cédula")
            t = c1.text_input("Teléfono")
            m = c2.text_input("Correo")
            r = st.text_area("Antecedentes")
            if st.form_submit_button("Guardar"):
                conn = conectar_db(); cursor = conn.cursor()
                cursor.execute("INSERT INTO pacientes (nombre, cedula, telefono, correo, referencia) VALUES (%s,%s,%s,%s,%s)", 
                             (n, id_c if id_c else None, t, m, r))
                conn.commit(); conn.close(); st.success("Registrado.")

    with tab2:
        st.write("### 📜 Historial de Sesiones Psicológicas")
        df_p = obtener_pacientes()
        
        p_id_hist = st.selectbox("Seleccionar Paciente:", options=df_p['id_paciente'].tolist(),
                                 format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}", 
                                 key="hist_psic")
        
        conn = conectar_db()
        # Seleccionamos TODOS los nuevos campos de la tabla historiales
        query_h = f"""
            SELECT fecha, estado_animo, nivel_ansiedad, calidad_sueno, riesgo_valoracion, 
                   obs_conductuales, sintomas, diagnostico, recomendaciones 
            FROM historiales WHERE id_paciente={p_id_hist} ORDER BY fecha DESC
        """
        try:
            df_h = pd.read_sql(query_h, conn)
            
            if df_h.empty:
                st.info("El paciente no tiene consultas registradas aún.")
            else:
                for _, row in df_h.iterrows():
                    with st.expander(f"📅 Sesión: {row['fecha']}"):
                        # --- FILA 1: INDICADORES (Visualización rápida) ---
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Ánimo", row['estado_animo'])
                        c2.metric("Ansiedad", row['nivel_ansiedad'])
                        c3.metric("Sueño", row['calidad_sueno'])
                        
                        # Alerta roja si el riesgo es alto
                        if row['riesgo_valoracion'] in ['Alto', 'Moderado']:
                            c4.error(f"⚠️ Riesgo: {row['riesgo_valoracion']}")
                        else:
                            c4.success(f"Riesgo: {row['riesgo_valoracion']}")

                        st.divider()

                        # --- FILA 2: CONTENIDO TEXTUAL ---
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown(f"**🗣️ Motivo de Consulta:**\n{row['sintomas']}")
                            st.markdown(f"**👁️ Observaciones:**\n{row['obs_conductuales']}")
                        
                        with col_b:
                            st.markdown(f"**🧠 Intervención/Evolución:**\n{row['diagnostico']}")
                            st.markdown(f"**📝 Tareas y Acuerdos:**\n{row['recomendaciones']}")
                            
        except Exception as e:
            st.error(f"Error al cargar el historial: {e}")
        finally:
            conn.close()


    with tab3:
        # --- TAB 3: NUEVA EVALUACIÓN PSICOLÓGICA ---
        st.write("### 🧠 Registro de Evolución Psicológica")
        df_p = obtener_pacientes()

        if df_p.empty:
            st.warning("No hay pacientes registrados.")
        else:
            p_id = st.selectbox(
                "Paciente:", 
                options=df_p['id_paciente'].tolist(),
                format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}", 
                key="cons_psic"
            )
            
            conn = conectar_db()
            # Solo mostramos citas donde asistió y no tiene historial aún
            query_citas = f"""
                SELECT id_cita, fecha 
                FROM citas 
                WHERE id_paciente={p_id} AND estado='Asistió' 
                AND id_cita NOT IN (SELECT id_cita FROM historiales)
            """
            
            try:
                c_libres = pd.read_sql(query_citas, conn)
                
                if c_libres.empty:
                    st.info("ℹ️ No hay sesiones pendientes de informe para este paciente.")
                else:
                    with st.form("f_psical_completo"):
                        cita_sel = st.selectbox(
                            "Seleccionar Sesión:", 
                            options=c_libres['id_cita'].tolist(),
                            format_func=lambda x: f"Fecha: {c_libres[c_libres['id_cita']==x]['fecha'].values[0]}"
                        )
                        
                        # --- FILA 1: EXAMEN MENTAL RÁPIDO ---
                        st.markdown("#### 📊 Indicadores de la Sesión")
                        col1, col2, col3, col4 = st.columns(4)
                        animo = col1.selectbox("Ánimo", ["Eutímico", "Ansioso", "Bajo", "Irritable", "Lábil"])
                        ansiedad = col2.selectbox("Ansiedad", ["Nula", "Baja", "Moderada", "Alta"])
                        sueno = col3.selectbox("Sueño", ["Reparador", "Insomnio", "Hipersomnio"])
                        riesgo = col4.selectbox("Riesgo", ["Nulo", "Bajo", "Moderado", "Alto"])
                        
                        # --- FILA 2: ÁREAS DE TEXTO ---
                        st.markdown("---")
                        motivo = st.text_area("Motivo de Consulta / Notas del Paciente", placeholder="¿Qué temas trajo el paciente hoy?")
                        obs_cond = st.text_area("Observaciones Conductuales", placeholder="Apariencia, contacto visual, lenguaje no verbal...")
                        evolucion = st.text_area("Impresión Clínica e Intervención", placeholder="Análisis técnico y técnicas aplicadas...")
                        tareas = st.text_area("Tareas y Acuerdos", placeholder="Actividades para la siguiente sesión...")
                        
                        # Botón de guardado
                        if st.form_submit_button("Guardar Evolución en Psical"):
                            fecha_c = str(c_libres[c_libres['id_cita']==cita_sel]['fecha'].values[0])
                            cursor = conn.cursor()
                            
                            sql = """INSERT INTO historiales 
                                     (id_paciente, id_cita, fecha, estado_animo, nivel_ansiedad, calidad_sueno, 
                                      riesgo_valoracion, obs_conductuales, sintomas, diagnostico, recomendaciones) 
                                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                            
                            valores = (p_id, cita_sel, fecha_c, animo, ansiedad, sueno, riesgo, obs_cond, motivo, evolucion, tareas)
                            
                            cursor.execute(sql, valores)
                            conn.commit()
                            st.success("✅ Evolución guardada exitosamente.")
                            t_sleep.sleep(1.5)
                            st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                conn.close()
