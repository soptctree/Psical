import streamlit as st
import pandas as pd
from datetime import datetime, time
from datetime import datetime, timedelta
import time as t_sleep
import pymysql  # Usamos pymysql directamente para mayor estabilidad en la nube

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Psical - Gestión Clínica", layout="wide")

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

def obtener_pacientes():
    try:
        conn = conectar_db()
        df = pd.read_sql("SELECT id_paciente, nombre, IFNULL(cedula, 'S/N') as cedula FROM pacientes", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame(columns=['id_paciente', 'nombre', 'cedula'])

def verificar_disponibilidad(fecha, h_inicio, h_fin):
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

# --- NAVEGACIÓN ---
st.title("🧠 Psical: Gestión de Citas")
menu = st.sidebar.radio("Navegación", ["Agenda Diaria", "Agendar Cita", "Pacientes y Expedientes"])

# --- MÓDULO 1: AGENDA DIARIA ---
if menu == "Agenda Diaria":
    st.subheader("📋 Control Operativo del Día")
    fecha_agenda = st.date_input("Ver día:", value=datetime.now())
    
    conn = conectar_db()
    query = f"""
        SELECT c.id_cita, c.hora_inicio, c.hora_fin, p.nombre, IFNULL(p.cedula, 'S/N') as cedula, c.estado 
        FROM citas c JOIN pacientes p ON c.id_paciente = p.id_paciente 
        WHERE c.fecha = '{fecha_agenda}' ORDER BY c.hora_inicio ASC
    """
    try:
        df_todas = pd.read_sql(query, conn)
        df_activas = df_todas[df_todas['estado'] != 'Cancelada']
        
        # --- 1. MAPA DE DISPONIBILIDAD (Semáforo) ---
        st.write("### 🕒 Mapa de Disponibilidad")
        horas_dia = pd.date_range(start="07:00", end="17:00", freq="30min").time
        cols = st.columns(10)
        
        for i, h in enumerate(horas_dia):
            ocupado = False
            if not df_activas.empty:
                for _, r in df_activas.iterrows():
                    inicio = (datetime.min + r['hora_inicio']).time() if isinstance(r['hora_inicio'], timedelta) else r['hora_inicio']
                    fin = (datetime.min + r['hora_fin']).time() if isinstance(r['hora_fin'], timedelta) else r['hora_fin']
                    if h >= inicio and h < fin:
                        ocupado = True
                        break
            with cols[i % 10]:
                if ocupado: st.error(f"{h.strftime('%H:%M')}")
                else: st.success(f"{h.strftime('%H:%M')}")

        st.divider()

        # --- 2. RANGOS OCUPADOS ---
        if not df_activas.empty:
            st.write("### ⏳ Horarios Reservados")
            for _, row in df_activas.iterrows():
                h_i_obj = (datetime.min + row['hora_inicio']).time() if isinstance(row['hora_inicio'], timedelta) else row['hora_inicio']
                h_f_obj = (datetime.min + row['hora_fin']).time() if isinstance(row['hora_fin'], timedelta) else row['hora_fin']
                h_i, h_f = h_i_obj.strftime('%H:%M'), h_f_obj.strftime('%H:%M')
                
                st.warning(f"**Ocupado de {h_i} a {h_f}** | Paciente: {row['nombre']} (ID: {row['cedula']})")
        else:
            st.info("🎉 Todo el día está libre. No hay rangos ocupados.")

        st.divider()

        # --- 3. DETALLE Y ASISTENCIA (Lo que faltaba) ---
        st.write("### 📝 Detalle y Asistencia")
        if df_todas.empty:
            st.info("No hay pacientes registrados para esta fecha.")
        else:
            for _, row in df_todas.iterrows():
                # Formateo de hora para el título del expander
                h_i_obj = (datetime.min + row['hora_inicio']).time() if isinstance(row['hora_inicio'], timedelta) else row['hora_inicio']
                h_f_obj = (datetime.min + row['hora_fin']).time() if isinstance(row['hora_fin'], timedelta) else row['hora_fin']
                time_range = f"{h_i_obj.strftime('%H:%M')} - {h_f_obj.strftime('%H:%M')}"
                
                with st.expander(f"⏰ {time_range} | 👤 {row['nombre']} ({row['estado']})"):
                    st.write(f"**Cédula/ID:** {row['cedula']}")
                    
                    # Selección de nuevo estado
                    lista_estados = ["Pendiente", "Asistió", "Ausente", "Cancelada"]
                    idx_actual = lista_estados.index(row['estado']) if row['estado'] in lista_estados else 0
                    
                    nuevo_estado = st.selectbox("Actualizar estado:", lista_estados, index=idx_actual, key=f"upd_{row['id_cita']}")
                    
                    if st.button("Guardar Cambio", key=f"btn_{row['id_cita']}"):
                        cursor = conn.cursor()
                        cursor.execute("UPDATE citas SET estado = %s WHERE id_cita = %s", (nuevo_estado, row['id_cita']))
                        conn.commit()
                        st.success(f"Estado de {row['nombre']} actualizado a {nuevo_estado}")
                        t_sleep.sleep(1)
                        st.rerun()

    except Exception as e:
        st.error(f"Error en Agenda: {e}")
    finally:
        conn.close()

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
        df_p = obtener_pacientes()
        if not df_p.empty:
            sel_p = st.selectbox("Seleccionar Paciente:", options=df_p['id_paciente'].tolist(),
                               format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}")
            if sel_p:
                conn = conectar_db()
                query_h = f"SELECT * FROM historiales WHERE id_paciente = {sel_p} ORDER BY fecha DESC"
                df_hist = pd.read_sql(query_h, conn)
                conn.close()
                if df_hist.empty: st.info("Sin historial.")
                else:
                    for _, row in df_hist.iterrows():
                        with st.expander(f"🩺 Consulta: {row['fecha']}"):
                            st.write(f"**Diagnóstico:** {row['diagnostico']}")

    with tab3:
        st.write("### 📝 Nueva Evaluación Médica")
        df_p = obtener_pacientes()
        if not df_p.empty:
            p_id = st.selectbox("Paciente:", options=df_p['id_paciente'].tolist(),
                              format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}", key="cons_doc")
            
            conn = conectar_db()
            # Corrección: Aseguramos que la consulta SQL no falle si p_id es nulo
            query_libres = f"SELECT id_cita, fecha FROM citas WHERE id_paciente={p_id} AND estado='Asistió' AND id_cita NOT IN (SELECT id_cita FROM historiales)"
            c_libres = pd.read_sql(query_libres, conn)
            
            if c_libres.empty:
                st.warning("No hay citas marcadas como 'Asistió' pendientes de informe.")
            else:
                with st.form("f_medico"):
                    cita_sel = st.selectbox("Cita del día:", options=c_libres['id_cita'].tolist(),
                                          format_func=lambda x: f"Fecha: {c_libres[c_libres['id_cita']==x]['fecha'].values[0]}")
                    peso = st.number_input("Peso (kg)", step=0.1)
                    presion = st.text_input("Presión")
                    dia = st.text_area("Diagnóstico")
                    if st.form_submit_button("Guardar Consulta"):
                        cursor = conn.cursor()
                        cursor.execute("""INSERT INTO historiales (id_paciente, id_cita, fecha, peso, presion_arterial, diagnostico) 
                                          VALUES (%s,%s,%s,%s,%s,%s)""", 
                                       (p_id, cita_sel, str(datetime.now().date()), peso, presion, dia))
                        conn.commit(); conn.close()
                        st.success("✅ Guardado."); t_sleep.sleep(1); st.rerun()
